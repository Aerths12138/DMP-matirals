"""AI assistant safety and permission tests."""

import json
import uuid

import httpx
import pytest
from fastapi import HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.models.analysis import AnalysisResult
from app.models.audit import AuditLog
from app.models.characterization import Characterization
from app.models.data_standard import MetadataTemplate
from app.models.experiment import Experiment
from app.models.material import Material
from app.models.permission import Permission, Role
from app.models.processing import ProcessingMethod
from app.models.project import Project, ProjectMember
from app.models.property import Property
from app.models.sample import Sample
from app.models.test import (
    Test as MaterialTest,
    TestMeasurement as MaterialTestMeasurement,
)
from app.models.user import User
from app.services import assistant_service
from app.utils.security import create_access_token


CHAT_URL = "/api/v1/assistant/chat"
HISTORY_URL = "/api/v1/assistant/history"
CONFIRM_URL = "/api/v1/assistant/actions/confirm"
BACKUPS_URL = "/api/v1/assistant/backups"
AUDIT_URL = "/api/v1/audit-logs"


async def _create_admin_headers(api, suffix: str):
    async with api.session_factory() as session:
        role = Role(name="admin", description="Administrator")
        user = User(
            username=f"assistant_admin_{suffix}",
            email=f"assistant-admin-{suffix}@example.com",
            hashed_password="unused",
            is_active=True,
            is_approved=True,
            role=role,
        )
        session.add(user)
        await session.commit()
        return {"Authorization": f"Bearer {create_access_token(user.id)}"}


async def _create_ai_data_manager(api, suffix: str):
    required_codes = {
        "material:read",
        "property:read",
        "property:create",
        "property:update",
        "property:delete",
        "characterization:read",
        "characterization:create",
        "characterization:update",
        "characterization:delete",
    }
    async with api.session_factory() as session:
        permissions = (
            await session.execute(
                select(Permission).where(Permission.codename.in_(required_codes))
            )
        ).scalars().all()
        by_code = {permission.codename: permission for permission in permissions}
        for codename in required_codes - set(by_code):
            permission = Permission(codename=codename)
            session.add(permission)
            by_code[codename] = permission

        role = Role(
            name=f"ai_data_manager_{suffix}",
            permissions=list(by_code.values()),
        )
        user = User(
            username=f"ai_data_manager_{suffix}",
            email=f"ai-data-manager-{suffix}@example.com",
            hashed_password="unused",
            is_active=True,
            is_approved=True,
            role=role,
        )
        session.add(user)
        await session.flush()
        project = Project(name=f"AI Data Project {suffix}", owner_id=user.id)
        session.add(project)
        await session.flush()
        session.add(
            ProjectMember(project_id=project.id, user_id=user.id, role="owner")
        )
        material = Material(
            name=f"AI Alloy {suffix}",
            material_type="metal",
            project_id=project.id,
            created_by=user.id,
        )
        experiment = Experiment(
            project_id=project.id,
            name=f"AI Experiment {suffix}",
            owner_id=user.id,
        )
        session.add_all([material, experiment])
        await session.flush()
        sample = Sample(
            experiment_id=experiment.id,
            material_id=material.id,
            sample_code=f"AI-SAMPLE-{suffix}",
            created_by=user.id,
        )
        session.add(sample)
        await session.commit()
        return (
            {"Authorization": f"Bearer {create_access_token(user.id)}"},
            {
                "user": user.id,
                "project": project.id,
                "material": material.id,
                "experiment": experiment.id,
                "sample": sample.id,
            },
        )


@pytest.mark.asyncio
async def test_assistant_requires_llm_configuration(api, monkeypatch):
    monkeypatch.setattr(settings, "LLM_BASE_URL", None)
    monkeypatch.setattr(settings, "LLM_API_KEY", None)
    monkeypatch.setattr(settings, "DEEPSEEK_API_KEY", None)

    response = await api.client.post(
        CHAT_URL,
        headers=api.headers["researcher"],
        json={"messages": [{"role": "user", "content": "你好"}]},
    )

    assert response.status_code == 503
    assert "LLM_BASE_URL" in response.json()["detail"]


@pytest.mark.asyncio
async def test_llm_timeout_has_specific_gateway_error(monkeypatch):
    class TimeoutClient:
        def __init__(self, **kwargs):
            assert kwargs["timeout"] == 150

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return False

        async def post(self, *args, **kwargs):
            raise httpx.ReadTimeout("model response timed out")

    monkeypatch.setattr(settings, "LLM_API_KEY", "test-key")
    monkeypatch.setattr(settings, "LLM_TIMEOUT_SECONDS", 150)
    monkeypatch.setattr(assistant_service.httpx, "AsyncClient", TimeoutClient)

    with pytest.raises(HTTPException) as exc_info:
        await assistant_service.request_llm(
            [{"role": "user", "content": "分析这段长文本"}],
            None,
        )

    assert exc_info.value.status_code == 504
    assert "150 秒" in exc_info.value.detail
    assert "分段发送" in exc_info.value.detail


@pytest.mark.asyncio
async def test_llm_connection_error_has_actionable_gateway_error(monkeypatch):
    class ConnectClient:
        def __init__(self, **kwargs):
            assert kwargs["trust_env"] is False

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return False

        async def post(self, *args, **kwargs):
            raise httpx.ConnectError("network is unavailable")

    monkeypatch.setattr(settings, "LLM_API_KEY", "test-key")
    monkeypatch.setattr(settings, "LLM_PROXY", None)
    monkeypatch.setattr(settings, "DEEPSEEK_PROXY", None)
    monkeypatch.setattr(assistant_service.httpx, "AsyncClient", ConnectClient)

    with pytest.raises(HTTPException) as exc_info:
        await assistant_service.request_llm(
            [{"role": "user", "content": "查询材料"}],
            None,
        )

    assert exc_info.value.status_code == 503
    assert "大模型服务" in exc_info.value.detail
    assert "LLM_PROXY" in exc_info.value.detail


@pytest.mark.asyncio
async def test_llm_length_stop_returns_actionable_message(monkeypatch):
    class LengthResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "choices": [
                    {
                        "finish_reason": "length",
                        "message": {"role": "assistant", "content": ""},
                    }
                ]
            }

    class LengthClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return False

        async def post(self, *args, **kwargs):
            return LengthResponse()

    monkeypatch.setattr(settings, "LLM_API_KEY", "test-key")
    monkeypatch.setattr(assistant_service.httpx, "AsyncClient", LengthClient)

    message = await assistant_service.request_llm(
        [{"role": "user", "content": "生成一份长报告"}],
        None,
    )

    assert "输出达到长度上限" in message["content"]
    assert "分段发送" in message["content"]


@pytest.mark.asyncio
async def test_assistant_returns_plain_answer(api, monkeypatch):
    async def fake_llm(messages, tools):
        return {"role": "assistant", "content": "这是测试回答。"}

    monkeypatch.setattr(assistant_service, "request_llm", fake_llm)
    response = await api.client.post(
        CHAT_URL,
        headers=api.headers["researcher"],
        json={
            "messages": [{"role": "user", "content": "什么是形状记忆合金？"}],
            "context_path": "/materials",
        },
    )

    assert response.status_code == 200
    assert response.json()["message"] == "这是测试回答。"
    assert response.json()["pending_actions"] == []


@pytest.mark.asyncio
async def test_measurement_analysis_returns_reproducible_unit_safe_card(api, monkeypatch):
    headers, ids = await _create_ai_data_manager(api, "measurement_analysis")
    async with api.session_factory() as session:
        session.add_all(
            [
                Property(
                    material_id=ids["material"],
                    property_type="mechanical",
                    property_name="tensile_strength",
                    value_number=10.0,
                    unit="MPa",
                    conditions={"temperature": "25 C"},
                    test_method="ASTM-D638",
                    is_validated=True,
                ),
                Property(
                    material_id=ids["material"],
                    property_type="mechanical",
                    property_name="tensile_strength",
                    value_number=0.011,
                    unit="GPa",
                    conditions={"temperature": "25 C"},
                    test_method="ASTM-D638",
                    is_validated=True,
                ),
                Property(
                    material_id=ids["material"],
                    property_type="mechanical",
                    property_name="tensile_strength",
                    value_number=12.0,
                    unit="MPa",
                    conditions={"temperature": "25 C"},
                    test_method="ASTM-D638",
                    is_validated=True,
                ),
                Property(
                    material_id=ids["material"],
                    property_type="mechanical",
                    property_name="tensile_strength",
                    value_number=100.0,
                    unit="MPa",
                    conditions={"temperature": "25 C"},
                    test_method="ASTM-D638",
                    is_validated=True,
                ),
            ]
        )
        await session.commit()

    async def fake_llm(messages, tools):
        if messages[-1]["role"] == "tool":
            tool_result = json.loads(messages[-1]["content"])
            assert tool_result["ok"] is True
            assert tool_result["data"]["query_plan"]["engine"].startswith(
                "permission-scoped"
            )
            return {"role": "assistant", "content": "已按材料汇总，并保留了质量提示。"}
        assert "analyze_measurements" in {
            item["function"]["name"] for item in (tools or [])
        }
        return {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "measurement-analysis",
                    "type": "function",
                    "function": {
                        "name": "analyze_measurements",
                        "arguments": json.dumps(
                            {
                                "property_name": "tensile_strength",
                                "source": "properties",
                                "material_ids": [str(ids["material"])],
                                "group_by": "material",
                                "validated_only": True,
                            }
                        ),
                    },
                }
            ],
        }

    monkeypatch.setattr(assistant_service, "request_llm", fake_llm)
    response = await api.client.post(
        CHAT_URL,
        headers=headers,
        json={"messages": [{"role": "user", "content": "比较拉伸强度并检查异常值"}]},
    )

    assert response.status_code == 200, response.text
    cards = response.json()["analysis_cards"]
    assert len(cards) == 1
    card = cards[0]
    assert card["quality"]["numeric_records"] == 4
    assert card["quality"]["outlier_count"] == 1
    assert card["groups"][0]["unit"] == "MPa"
    assert card["groups"][0]["mean"] == 33.25
    assert len(card["provenance"]["record_references"]) == 4


@pytest.mark.asyncio
async def test_measurement_analysis_respects_private_project_visibility(api, monkeypatch):
    owner_headers, owner_ids = await _create_ai_data_manager(api, "analysis_owner")
    reader_headers, _reader_ids = await _create_ai_data_manager(api, "analysis_reader")
    async with api.session_factory() as session:
        session.add(
            Property(
                material_id=owner_ids["material"],
                property_type="thermal",
                property_name="private_conductivity",
                value_number=42.0,
                unit="W/(m*K)",
                is_validated=True,
            )
        )
        await session.commit()

    async def fake_llm(messages, tools):
        if messages[-1]["role"] == "tool":
            return {"role": "assistant", "content": "分析完成。"}
        return {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "private-analysis",
                    "type": "function",
                    "function": {
                        "name": "analyze_measurements",
                        "arguments": json.dumps(
                            {
                                "property_name": "private_conductivity",
                                "source": "properties",
                            }
                        ),
                    },
                }
            ],
        }

    monkeypatch.setattr(assistant_service, "request_llm", fake_llm)
    response = await api.client.post(
        CHAT_URL,
        headers=reader_headers,
        json={"messages": [{"role": "user", "content": "分析私有导热率"}]},
    )

    assert response.status_code == 200, response.text
    card = response.json()["analysis_cards"][0]
    assert card["quality"]["records_returned"] == 0
    assert card["provenance"]["record_references"] == []
    assert owner_headers != reader_headers


@pytest.mark.asyncio
async def test_assistant_history_is_persisted_and_user_scoped(api, monkeypatch):
    async def fake_llm(messages, tools):
        return {"role": "assistant", "content": "这是保存后的回答。"}

    monkeypatch.setattr(assistant_service, "request_llm", fake_llm)
    response = await api.client.post(
        CHAT_URL,
        headers=api.headers["researcher"],
        json={"messages": [{"role": "user", "content": "请记住这个问题"}]},
    )
    assert response.status_code == 200

    history = await api.client.get(HISTORY_URL, headers=api.headers["researcher"])
    assert history.status_code == 200
    assert history.json()["messages"] == [
        {"role": "user", "content": "请记住这个问题"},
        {"role": "assistant", "content": "这是保存后的回答。"},
    ]
    assert history.json()["updated_at"] is not None

    other_history = await api.client.get(HISTORY_URL, headers=api.headers["viewer"])
    assert other_history.status_code == 200
    assert other_history.json() == {"messages": [], "updated_at": None}

    cleared = await api.client.delete(HISTORY_URL, headers=api.headers["researcher"])
    assert cleared.status_code == 204
    history_after_clear = await api.client.get(
        HISTORY_URL,
        headers=api.headers["researcher"],
    )
    assert history_after_clear.json() == {"messages": [], "updated_at": None}


@pytest.mark.asyncio
async def test_read_tool_respects_private_project_visibility(api, monkeypatch):
    async with api.session_factory() as session:
        private_project = Project(name="Secret Project", owner_id=api.user_ids["researcher"])
        session.add(private_project)
        await session.flush()
        session.add(
            ProjectMember(
                project_id=private_project.id,
                user_id=api.user_ids["researcher"],
                role="owner",
            )
        )
        session.add(
            Material(
                name="Secret Alloy",
                material_type="metal",
                project_id=private_project.id,
                created_by=api.user_ids["researcher"],
            )
        )
        await session.commit()

    captured_tool_result = {}

    async def fake_llm(messages, tools):
        if messages[-1]["role"] == "tool":
            captured_tool_result.update(json.loads(messages[-1]["content"]))
            return {"role": "assistant", "content": "查询完成。"}
        return {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call_list",
                    "type": "function",
                    "function": {
                        "name": "list_materials",
                        "arguments": json.dumps({"search": "Secret"}),
                    },
                }
            ],
        }

    monkeypatch.setattr(assistant_service, "request_llm", fake_llm)
    response = await api.client.post(
        CHAT_URL,
        headers=api.headers["outsider"],
        json={"messages": [{"role": "user", "content": "查找 Secret 材料"}]},
    )

    assert response.status_code == 200
    assert captured_tool_result["ok"] is True
    assert captured_tool_result["data"]["items"] == []


@pytest.mark.asyncio
async def test_create_requires_confirmation_and_token_is_single_use(api, monkeypatch):
    admin_headers = await _create_admin_headers(api, "success_audit")

    async def fake_llm(messages, tools):
        if tools is None:
            return {"role": "assistant", "content": "请确认新增材料。"}
        return {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call_create",
                    "type": "function",
                    "function": {
                        "name": "create_material",
                        "arguments": json.dumps(
                            {
                                "name": "AI Created Alloy",
                                "material_type": "metal",
                                "formula_string": "FeNi",
                            }
                        ),
                    },
                }
            ],
        }

    monkeypatch.setattr(assistant_service, "request_llm", fake_llm)
    chat_response = await api.client.post(
        CHAT_URL,
        headers=api.headers["researcher"],
        json={"messages": [{"role": "user", "content": "新增 FeNi 材料"}]},
    )
    assert chat_response.status_code == 200
    pending = chat_response.json()["pending_actions"]
    assert len(pending) == 1
    assert pending[0]["summary"] == "新增材料“AI Created Alloy”"

    async with api.session_factory() as session:
        count_before = await session.scalar(
            select(func.count(Material.id)).where(Material.name == "AI Created Alloy")
        )
    assert count_before == 0

    token = pending[0]["token"]
    async with api.session_factory() as session:
        researcher = await session.get(User, api.user_ids["researcher"])
        payload = assistant_service.decode_action_token(token, researcher)
        action_id = uuid.UUID(payload["jti"])

    confirm_response = await api.client.post(
        CONFIRM_URL,
        headers=api.headers["researcher"],
        json={"token": token},
    )
    assert confirm_response.status_code == 200
    assert confirm_response.headers["x-request-id"] == str(action_id)
    assert confirm_response.json()["request_id"] == str(action_id)
    assert confirm_response.json()["data"]["name"] == "AI Created Alloy"

    audit_response = await api.client.get(
        AUDIT_URL,
        params={"request_id": str(action_id)},
        headers=admin_headers,
    )
    assert audit_response.status_code == 200, audit_response.text
    assert audit_response.json()["total"] == 1
    audit_item = audit_response.json()["items"][0]
    assert audit_item["request_id"] == str(action_id)
    assert audit_item["action"] == "CREATE"
    serialized_audit = json.dumps(audit_response.json())
    assert token not in serialized_audit
    assert "AI Created Alloy" not in serialized_audit
    assert "FeNi" not in serialized_audit

    async with api.session_factory() as session:
        count_after = await session.scalar(
            select(func.count(Material.id)).where(Material.name == "AI Created Alloy")
        )
    assert count_after == 1

    replay_response = await api.client.post(
        CONFIRM_URL,
        headers=api.headers["researcher"],
        json={"token": token},
    )
    assert replay_response.status_code == 409


@pytest.mark.asyncio
async def test_audit_failure_is_observable_and_rolls_back_write(
    api,
    monkeypatch,
    caplog,
):
    sensitive_name = "Sensitive Audit Failure Alloy"
    sensitive_formula = "SecretFormula42"

    async def fake_llm(messages, tools):
        if tools is None:
            return {"role": "assistant", "content": "Please confirm."}
        return {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call_audit_failure",
                    "type": "function",
                    "function": {
                        "name": "create_material",
                        "arguments": json.dumps(
                            {
                                "name": sensitive_name,
                                "material_type": "metal",
                                "formula_string": sensitive_formula,
                            }
                        ),
                    },
                }
            ],
        }

    monkeypatch.setattr(assistant_service, "request_llm", fake_llm)
    preview = await api.client.post(
        CHAT_URL,
        headers=api.headers["researcher"],
        json={"messages": [{"role": "user", "content": "Create material"}]},
    )
    token = preview.json()["pending_actions"][0]["token"]
    async with api.session_factory() as session:
        researcher = await session.get(User, api.user_ids["researcher"])
        action_id = uuid.UUID(
            assistant_service.decode_action_token(token, researcher)["jti"]
        )

    original_flush = AsyncSession.flush

    async def fail_audit_flush(session, objects=None):
        if any(isinstance(item, AuditLog) for item in session.new):
            raise RuntimeError(
                f"simulated audit failure {token} {sensitive_name} {sensitive_formula}"
            )
        return await original_flush(session, objects)

    monkeypatch.setattr(AsyncSession, "flush", fail_audit_flush)
    caplog.set_level("ERROR", logger="app.api.v1.assistant")

    confirmed = await api.client.post(
        CONFIRM_URL,
        headers=api.headers["researcher"],
        json={"token": token},
    )
    assert confirmed.status_code == 503
    assert confirmed.headers["x-request-id"] == str(action_id)

    async with api.session_factory() as session:
        material_count = await session.scalar(
            select(func.count(Material.id)).where(Material.name == sensitive_name)
        )
        audit_count = await session.scalar(
            select(func.count(AuditLog.id)).where(AuditLog.request_id == action_id)
        )
    assert material_count == 0
    assert audit_count == 0

    record = next(
        item
        for item in caplog.records
        if item.getMessage() == "AI assistant audit persistence failed"
    )
    assert record.request_id == str(action_id)
    assert record.audit_stage == "action_execution"
    assert record.error_type == "RuntimeError"
    assert token not in caplog.text
    assert sensitive_name not in caplog.text
    assert sensitive_formula not in caplog.text


@pytest.mark.asyncio
async def test_viewer_cannot_prepare_create_action(api, monkeypatch):
    calls = 0

    async def fake_llm(messages, tools):
        nonlocal calls
        calls += 1
        if calls == 1:
            advertised_tools = {
                definition["function"]["name"] for definition in tools
            }
            assert "list_materials" in advertised_tools
            assert "create_material" not in advertised_tools
            assert "update_material" not in advertised_tools
            return {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_denied",
                        "type": "function",
                        "function": {
                            "name": "create_material",
                            "arguments": json.dumps(
                                {"name": "Denied", "material_type": "metal"}
                            ),
                        },
                    }
                ],
            }
        assert json.loads(messages[-1]["content"])["status"] == 403
        return {"role": "assistant", "content": "你没有新增材料的权限。"}

    monkeypatch.setattr(assistant_service, "request_llm", fake_llm)
    response = await api.client.post(
        CHAT_URL,
        headers=api.headers["viewer"],
        json={"messages": [{"role": "user", "content": "新增材料"}]},
    )

    assert response.status_code == 200
    assert response.json()["pending_actions"] == []
    assert "没有" in response.json()["message"]


@pytest.mark.asyncio
async def test_project_editor_can_update_material_through_assistant(api, monkeypatch):
    async with api.session_factory() as session:
        project = Project(name="Editor Project", owner_id=api.user_ids["researcher"])
        session.add(project)
        await session.flush()
        session.add_all(
            [
                ProjectMember(
                    project_id=project.id,
                    user_id=api.user_ids["researcher"],
                    role="owner",
                ),
                ProjectMember(
                    project_id=project.id,
                    user_id=api.user_ids["outsider"],
                    role="editor",
                ),
            ]
        )
        material = Material(
            name="Editable Alloy",
            material_type="metal",
            project_id=project.id,
            created_by=api.user_ids["researcher"],
        )
        session.add(material)
        await session.commit()
        material_id = str(material.id)

    async def fake_llm(messages, tools):
        if tools is None:
            return {"role": "assistant", "content": "请确认修改。"}
        return {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call_editor_update",
                    "type": "function",
                    "function": {
                        "name": "update_material",
                        "arguments": json.dumps(
                            {
                                "material_id": material_id,
                                "changes": {"description": "Updated by editor"},
                            }
                        ),
                    },
                }
            ],
        }

    monkeypatch.setattr(assistant_service, "request_llm", fake_llm)
    preview = await api.client.post(
        CHAT_URL,
        headers=api.headers["outsider"],
        json={"messages": [{"role": "user", "content": "修改材料说明"}]},
    )
    assert preview.status_code == 200
    assert len(preview.json()["pending_actions"]) == 1

    confirmed = await api.client.post(
        CONFIRM_URL,
        headers=api.headers["outsider"],
        json={"token": preview.json()["pending_actions"][0]["token"]},
    )
    assert confirmed.status_code == 200

    async with api.session_factory() as session:
        updated = await session.get(Material, material.id)
        assert updated.description == "Updated by editor"


@pytest.mark.asyncio
async def test_project_viewer_cannot_update_material(api, monkeypatch):
    async with api.session_factory() as session:
        project = Project(name="Viewer Project", owner_id=api.user_ids["researcher"])
        session.add(project)
        await session.flush()
        session.add_all(
            [
                ProjectMember(
                    project_id=project.id,
                    user_id=api.user_ids["researcher"],
                    role="owner",
                ),
                ProjectMember(
                    project_id=project.id,
                    user_id=api.user_ids["outsider"],
                    role="viewer",
                ),
            ]
        )
        material = Material(
            name="Read Only Alloy",
            material_type="metal",
            project_id=project.id,
            created_by=api.user_ids["researcher"],
        )
        session.add(material)
        await session.commit()
        material_id = str(material.id)

    calls = 0

    async def fake_llm(messages, tools):
        nonlocal calls
        calls += 1
        if calls == 1:
            advertised_tools = {
                definition["function"]["name"] for definition in tools
            }
            assert "update_material" in advertised_tools
            return {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_viewer_update",
                        "type": "function",
                        "function": {
                            "name": "update_material",
                            "arguments": json.dumps(
                                {
                                    "material_id": material_id,
                                    "changes": {"description": "Should fail"},
                                }
                            ),
                        },
                    }
                ],
            }
        tool_result = json.loads(messages[-1]["content"])
        assert tool_result["status"] == 403
        return {"role": "assistant", "content": "你只有查看权限。"}

    monkeypatch.setattr(assistant_service, "request_llm", fake_llm)
    response = await api.client.post(
        CHAT_URL,
        headers=api.headers["outsider"],
        json={"messages": [{"role": "user", "content": "修改材料"}]},
    )
    assert response.status_code == 200
    assert response.json()["pending_actions"] == []

    async with api.session_factory() as session:
        unchanged = await session.get(Material, material.id)
        assert unchanged.description is None


@pytest.mark.asyncio
async def test_confirmation_rechecks_project_membership(api, monkeypatch):
    admin_headers = await _create_admin_headers(api, "denial_audit")

    async with api.session_factory() as session:
        project = Project(name="Revoked Project", owner_id=api.user_ids["researcher"])
        session.add(project)
        await session.flush()
        session.add_all(
            [
                ProjectMember(
                    project_id=project.id,
                    user_id=api.user_ids["researcher"],
                    role="owner",
                ),
                ProjectMember(
                    project_id=project.id,
                    user_id=api.user_ids["outsider"],
                    role="editor",
                ),
            ]
        )
        material = Material(
            name="Revoked Alloy",
            material_type="metal",
            project_id=project.id,
            created_by=api.user_ids["researcher"],
        )
        session.add(material)
        await session.commit()
        material_id = str(material.id)
        project_id = project.id

    async def fake_llm(messages, tools):
        if tools is None:
            return {"role": "assistant", "content": "请确认修改。"}
        return {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call_revoked_update",
                    "type": "function",
                    "function": {
                        "name": "update_material",
                        "arguments": json.dumps(
                            {
                                "material_id": material_id,
                                "changes": {"description": "Must not be written"},
                            }
                        ),
                    },
                }
            ],
        }

    monkeypatch.setattr(assistant_service, "request_llm", fake_llm)
    preview = await api.client.post(
        CHAT_URL,
        headers=api.headers["outsider"],
        json={"messages": [{"role": "user", "content": "修改材料"}]},
    )
    token = preview.json()["pending_actions"][0]["token"]
    async with api.session_factory() as session:
        outsider = await session.get(User, api.user_ids["outsider"])
        payload = assistant_service.decode_action_token(token, outsider)
        action_id = uuid.UUID(payload["jti"])

    async with api.session_factory() as session:
        await session.execute(
            delete(ProjectMember).where(
                ProjectMember.project_id == project_id,
                ProjectMember.user_id == api.user_ids["outsider"],
            )
        )
        await session.commit()

    confirmed = await api.client.post(
        CONFIRM_URL,
        headers=api.headers["outsider"],
        json={"token": token},
    )
    assert confirmed.status_code == 403
    assert confirmed.headers["x-request-id"] == str(action_id)

    queried = await api.client.get(
        AUDIT_URL,
        params={"request_id": str(action_id)},
        headers=admin_headers,
    )
    assert queried.status_code == 200, queried.text
    assert queried.json()["total"] == 1
    assert queried.json()["items"][0]["request_id"] == str(action_id)
    serialized_query = json.dumps(queried.json())
    assert token not in serialized_query
    assert "Must not be written" not in serialized_query

    async with api.session_factory() as session:
        unchanged = await session.get(Material, material.id)
        assert unchanged.description is None
        denial = await session.scalar(
            select(AuditLog).where(
                AuditLog.request_id == action_id,
                AuditLog.action == "DENY",
            )
        )
        assert denial is not None
        assert denial.user_id == api.user_ids["outsider"]
        assert denial.entity_type == "material"
        assert denial.entity_id is None
        assert denial.changes == {
            "source": "ai_assistant",
            "stage": "confirmation",
            "tool": "update_material",
            "reason_code": "insufficient_project_access",
        }
        serialized_changes = json.dumps(denial.changes)
        assert token not in serialized_changes
        assert "Must not be written" not in serialized_changes


@pytest.mark.asyncio
async def test_search_only_returns_entity_types_allowed_by_global_role(api, monkeypatch):
    async with api.session_factory() as session:
        material_read = await session.scalar(
            select(Permission).where(Permission.codename == "material:read")
        )
        material_only_role = Role(
            name="material_only",
            permissions=[material_read],
        )
        scoped_user = User(
            username="material_only_user",
            email="material-only@example.com",
            hashed_password="unused",
            is_active=True,
            is_approved=True,
            role=material_only_role,
        )
        project = Project(name="Scoped Needle Project", owner_id=api.user_ids["researcher"])
        session.add_all([scoped_user, project])
        await session.flush()
        session.add_all(
            [
                ProjectMember(
                    project_id=project.id,
                    user_id=api.user_ids["researcher"],
                    role="owner",
                ),
                ProjectMember(
                    project_id=project.id,
                    user_id=scoped_user.id,
                    role="viewer",
                ),
                Material(
                    name="Scoped Needle Material",
                    material_type="metal",
                    project_id=project.id,
                    created_by=api.user_ids["researcher"],
                ),
            ]
        )
        await session.commit()
        scoped_headers = {
            "Authorization": f"Bearer {create_access_token(scoped_user.id)}"
        }

    captured_result = {}

    async def fake_llm(messages, tools):
        if messages[-1]["role"] == "tool":
            captured_result.update(json.loads(messages[-1]["content"])["data"])
            return {"role": "assistant", "content": "查询完成。"}
        advertised_tools = {
            definition["function"]["name"] for definition in tools
        }
        assert advertised_tools == {"search_data", "list_materials", "get_material"}
        return {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call_scoped_search",
                    "type": "function",
                    "function": {
                        "name": "search_data",
                        "arguments": json.dumps({"query": "Scoped Needle"}),
                    },
                }
            ],
        }

    monkeypatch.setattr(assistant_service, "request_llm", fake_llm)
    response = await api.client.post(
        CHAT_URL,
        headers=scoped_headers,
        json={"messages": [{"role": "user", "content": "搜索 Scoped Needle"}]},
    )
    assert response.status_code == 200
    assert {item["entity_type"] for item in captured_result["items"]} == {"material"}


@pytest.mark.asyncio
async def test_update_backup_can_be_restored_once(api, monkeypatch):
    async with api.session_factory() as session:
        material = Material(
            name="Versioned Alloy",
            material_type="metal",
            description="original description",
            created_by=api.user_ids["researcher"],
        )
        session.add(material)
        await session.commit()
        material_id = str(material.id)

    async def fake_llm(messages, tools):
        if tools is None:
            return {"role": "assistant", "content": "请确认修改。"}
        return {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call_versioned_update",
                    "type": "function",
                    "function": {
                        "name": "update_material",
                        "arguments": json.dumps(
                            {
                                "material_id": material_id,
                                "changes": {"description": "AI changed description"},
                            }
                        ),
                    },
                }
            ],
        }

    monkeypatch.setattr(assistant_service, "request_llm", fake_llm)
    preview = await api.client.post(
        CHAT_URL,
        headers=api.headers["researcher"],
        json={"messages": [{"role": "user", "content": "修改材料说明"}]},
    )
    confirmed = await api.client.post(
        CONFIRM_URL,
        headers=api.headers["researcher"],
        json={"token": preview.json()["pending_actions"][0]["token"]},
    )
    assert confirmed.status_code == 200
    backup = confirmed.json()["backup"]
    assert backup is not None
    assert backup["operation"] == "update"

    listed = await api.client.get(BACKUPS_URL, headers=api.headers["researcher"])
    assert listed.status_code == 200
    assert backup["id"] in {item["id"] for item in listed.json()}

    restored = await api.client.post(
        f"{BACKUPS_URL}/{backup['id']}/restore",
        headers=api.headers["researcher"],
    )
    assert restored.status_code == 200
    async with api.session_factory() as session:
        material = await session.get(Material, material.id)
        assert material.description == "original description"

    repeated = await api.client.post(
        f"{BACKUPS_URL}/{backup['id']}/restore",
        headers=api.headers["researcher"],
    )
    assert repeated.status_code == 409


@pytest.mark.asyncio
async def test_deleted_material_graph_can_be_restored(api, monkeypatch):
    async with api.session_factory() as session:
        permissions = (
            await session.execute(
                select(Permission).where(
                    Permission.codename.in_(
                        ["material:read", "material:create", "material:update"]
                    )
                )
            )
        ).scalars().all()
        delete_permission = Permission(codename="material:delete")
        deleter_role = Role(
            name="material_deleter",
            permissions=[*permissions, delete_permission],
        )
        deleter = User(
            username="material_deleter",
            email="material-deleter@example.com",
            hashed_password="unused",
            is_active=True,
            is_approved=True,
            role=deleter_role,
        )
        session.add(deleter)
        await session.flush()
        material = Material(
            name="Restorable Material",
            material_type="metal",
            created_by=deleter.id,
        )
        session.add(material)
        await session.flush()
        sample = Sample(
            sample_code="RESTORE-SAMPLE",
            material_id=material.id,
            created_by=deleter.id,
        )
        prop = Property(
            material_id=material.id,
            property_type="mechanical",
            property_name="strength",
            value_number=123.0,
            created_by=deleter.id,
        )
        test = MaterialTest(
            material_id=material.id,
            test_name="Restore test",
            created_by=deleter.id,
        )
        session.add_all([sample, prop, test])
        await session.flush()
        measurement = MaterialTestMeasurement(
            test_id=test.id,
            property_name="strength",
            value_number=123.0,
            unit="MPa",
        )
        session.add(measurement)
        await session.commit()
        ids = {
            "material": material.id,
            "sample": sample.id,
            "property": prop.id,
            "test": test.id,
            "measurement": measurement.id,
        }
        deleter_headers = {
            "Authorization": f"Bearer {create_access_token(deleter.id)}"
        }

    async def fake_llm(messages, tools):
        if tools is None:
            return {"role": "assistant", "content": "请确认删除。"}
        return {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call_delete_material_graph",
                    "type": "function",
                    "function": {
                        "name": "delete_material",
                        "arguments": json.dumps({"material_id": str(ids["material"])}),
                    },
                }
            ],
        }

    monkeypatch.setattr(assistant_service, "request_llm", fake_llm)
    preview = await api.client.post(
        CHAT_URL,
        headers=deleter_headers,
        json={"messages": [{"role": "user", "content": "删除材料"}]},
    )
    confirmed = await api.client.post(
        CONFIRM_URL,
        headers=deleter_headers,
        json={"token": preview.json()["pending_actions"][0]["token"]},
    )
    assert confirmed.status_code == 200
    backup_id = confirmed.json()["backup"]["id"]

    async with api.session_factory() as session:
        assert await session.get(Material, ids["material"]) is None
        assert await session.get(Property, ids["property"]) is None
        assert await session.get(MaterialTest, ids["test"]) is None
        linked_sample = await session.get(Sample, ids["sample"])
        assert linked_sample.material_id is None

    restored = await api.client.post(
        f"{BACKUPS_URL}/{backup_id}/restore",
        headers=deleter_headers,
    )
    assert restored.status_code == 200
    async with api.session_factory() as session:
        assert await session.get(Material, ids["material"]) is not None
        assert await session.get(Property, ids["property"]) is not None
        assert await session.get(MaterialTest, ids["test"]) is not None
        assert await session.get(MaterialTestMeasurement, ids["measurement"]) is not None
        linked_sample = await session.get(Sample, ids["sample"])
        assert linked_sample.material_id == ids["material"]


@pytest.mark.asyncio
async def test_deleted_project_graph_can_be_restored(api, monkeypatch):
    async with api.session_factory() as session:
        permissions = (
            await session.execute(
                select(Permission).where(
                    Permission.codename.in_(
                        ["experiment:read", "experiment:create", "experiment:update"]
                    )
                )
            )
        ).scalars().all()
        delete_permission = Permission(codename="experiment:delete")
        owner_role = Role(
            name="project_deleter",
            permissions=[*permissions, delete_permission],
        )
        owner = User(
            username="project_deleter",
            email="project-deleter@example.com",
            hashed_password="unused",
            is_active=True,
            is_approved=True,
            role=owner_role,
        )
        session.add(owner)
        await session.flush()
        project = Project(name="Restorable Project", owner_id=owner.id)
        session.add(project)
        await session.flush()
        membership = ProjectMember(project_id=project.id, user_id=owner.id, role="owner")
        template = MetadataTemplate(
            project_id=project.id,
            name="Restore template",
            entity_type="sample",
            fields=[],
            created_by=owner.id,
        )
        material = Material(
            name="Project-linked Material",
            material_type="metal",
            project_id=project.id,
            created_by=owner.id,
        )
        experiment = Experiment(
            project_id=project.id,
            name="Restore experiment",
            owner_id=owner.id,
        )
        session.add_all([membership, template, material, experiment])
        await session.flush()
        sample = Sample(
            experiment_id=experiment.id,
            material_id=material.id,
            metadata_template_id=template.id,
            sample_code="PROJECT-RESTORE-SAMPLE",
            created_by=owner.id,
        )
        session.add(sample)
        await session.flush()
        characterization = Characterization(
            sample_id=sample.id,
            technique="SEM",
            title="Restore characterization",
            metadata_template_id=template.id,
            created_by=owner.id,
        )
        session.add(characterization)
        await session.flush()
        analysis = AnalysisResult(
            characterization_id=characterization.id,
            analysis_type="restore_test",
            result_data={"ok": True},
            run_by=owner.id,
        )
        session.add(analysis)
        await session.commit()
        ids = {
            "project": project.id,
            "membership": membership.id,
            "template": template.id,
            "material": material.id,
            "experiment": experiment.id,
            "sample": sample.id,
            "characterization": characterization.id,
            "analysis": analysis.id,
        }
        owner_headers = {
            "Authorization": f"Bearer {create_access_token(owner.id)}"
        }

    async def fake_llm(messages, tools):
        if tools is None:
            return {"role": "assistant", "content": "请确认删除项目。"}
        return {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call_delete_project_graph",
                    "type": "function",
                    "function": {
                        "name": "delete_project",
                        "arguments": json.dumps({"project_id": str(ids["project"])}),
                    },
                }
            ],
        }

    monkeypatch.setattr(assistant_service, "request_llm", fake_llm)
    preview = await api.client.post(
        CHAT_URL,
        headers=owner_headers,
        json={"messages": [{"role": "user", "content": "删除项目"}]},
    )
    confirmed = await api.client.post(
        CONFIRM_URL,
        headers=owner_headers,
        json={"token": preview.json()["pending_actions"][0]["token"]},
    )
    assert confirmed.status_code == 200
    backup_id = confirmed.json()["backup"]["id"]

    async with api.session_factory() as session:
        assert await session.get(Project, ids["project"]) is None
        assert await session.get(Experiment, ids["experiment"]) is None
        linked_material = await session.get(Material, ids["material"])
        assert linked_material.project_id is None

    restored = await api.client.post(
        f"{BACKUPS_URL}/{backup_id}/restore",
        headers=owner_headers,
    )
    assert restored.status_code == 200
    async with api.session_factory() as session:
        assert await session.get(Project, ids["project"]) is not None
        assert await session.get(ProjectMember, ids["membership"]) is not None
        assert await session.get(MetadataTemplate, ids["template"]) is not None
        linked_material = await session.get(Material, ids["material"])
        assert linked_material.project_id == ids["project"]
        assert await session.get(Experiment, ids["experiment"]) is not None
        assert await session.get(Sample, ids["sample"]) is not None
        assert await session.get(Characterization, ids["characterization"]) is not None
        assert await session.get(AnalysisResult, ids["analysis"]) is not None


@pytest.mark.asyncio
async def test_followup_delete_can_search_inspect_and_prepare_confirmation(api, monkeypatch):
    async with api.session_factory() as session:
        permissions = (
            await session.execute(
                select(Permission).where(
                    Permission.codename.in_(
                        ["material:read", "material:create", "material:update"]
                    )
                )
            )
        ).scalars().all()
        delete_permission = Permission(codename="material:delete")
        deleter_role = Role(
            name="followup_material_deleter",
            permissions=[*permissions, delete_permission],
        )
        deleter = User(
            username="followup_material_deleter",
            email="followup-material-deleter@example.com",
            hashed_password="unused",
            is_active=True,
            is_approved=True,
            role=deleter_role,
        )
        session.add(deleter)
        await session.flush()
        material = Material(
            name="齐鲁化工",
            material_type="other",
            created_by=deleter.id,
        )
        session.add(material)
        await session.commit()
        material_id = material.id
        deleter_headers = {
            "Authorization": f"Bearer {create_access_token(deleter.id)}"
        }

    calls = 0

    async def fake_llm(messages, tools):
        nonlocal calls
        calls += 1
        if calls == 1:
            return {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_followup_search",
                        "type": "function",
                        "function": {
                            "name": "search_data",
                            "arguments": json.dumps(
                                {"query": "齐鲁化工", "entity_type": "material"}
                            ),
                        },
                    }
                ],
            }
        if calls == 2:
            search_result = json.loads(messages[-1]["content"])
            assert search_result["ok"] is True
            assert search_result["data"]["items"][0]["id"] == str(material_id)
            return {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_followup_detail",
                        "type": "function",
                        "function": {
                            "name": "get_material",
                            "arguments": json.dumps({"material_id": str(material_id)}),
                        },
                    }
                ],
            }
        if calls == 3:
            detail_result = json.loads(messages[-1]["content"])
            assert detail_result["ok"] is True
            return {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_followup_delete",
                        "type": "function",
                        "function": {
                            "name": "delete_material",
                            "arguments": json.dumps({"material_id": str(material_id)}),
                        },
                    }
                ],
            }
        assert tools is None
        return {"role": "assistant", "content": "已生成删除预览，请确认。"}

    monkeypatch.setattr(assistant_service, "request_llm", fake_llm)
    response = await api.client.post(
        CHAT_URL,
        headers=deleter_headers,
        json={
            "messages": [
                {"role": "user", "content": "帮我查询“齐鲁”相关的数据"},
                {
                    "role": "assistant",
                    "content": "搜索到 1 条结果：材料“齐鲁化工”。需要我查看详细信息吗？",
                },
                {"role": "user", "content": "删除这个数据"},
            ]
        },
    )

    assert response.status_code == 200
    assert response.json()["message"] == "已生成删除预览，请确认。"
    pending = response.json()["pending_actions"]
    assert len(pending) == 1
    assert pending[0]["summary"] == "删除材料“齐鲁化工”"
    assert calls == 4

    async with api.session_factory() as session:
        assert await session.get(Material, material_id) is not None

    confirmed = await api.client.post(
        CONFIRM_URL,
        headers=deleter_headers,
        json={"token": pending[0]["token"]},
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["backup"]["operation"] == "delete"
    async with api.session_factory() as session:
        assert await session.get(Material, material_id) is None


@pytest.mark.asyncio
async def test_semantic_experiment_and_sample_tools_confirm_and_restore(api, monkeypatch):
    async with api.session_factory() as session:
        project = Project(
            name="Semantic Routing Project",
            owner_id=api.user_ids["researcher"],
        )
        session.add(project)
        await session.flush()
        session.add(
            ProjectMember(
                project_id=project.id,
                user_id=api.user_ids["researcher"],
                role="owner",
            )
        )
        await session.commit()
        project_id = project.id

    requested_tool = "create_experiment"
    requested_arguments = {
        "project_id": str(project_id),
        "name": "热处理对照实验",
        "description": "通过自然语言创建",
    }

    async def fake_llm(messages, tools):
        if tools is None:
            return {"role": "assistant", "content": "已生成操作预览，请确认。"}
        advertised = {item["function"]["name"] for item in tools}
        assert requested_tool in advertised
        return {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": f"call_{requested_tool}",
                    "type": "function",
                    "function": {
                        "name": requested_tool,
                        "arguments": json.dumps(requested_arguments),
                    },
                }
            ],
        }

    monkeypatch.setattr(assistant_service, "request_llm", fake_llm)
    experiment_preview = await api.client.post(
        CHAT_URL,
        headers=api.headers["researcher"],
        json={
            "messages": [
                {
                    "role": "user",
                    "content": "在语义路由项目中新建一个热处理对照实验",
                }
            ]
        },
    )
    assert experiment_preview.status_code == 200
    experiment_action = experiment_preview.json()["pending_actions"][0]
    assert experiment_action["tool_name"] == "create_experiment"
    assert experiment_action["entity_type"] == "experiment"

    async with api.session_factory() as session:
        assert await session.scalar(
            select(func.count(Experiment.id)).where(
                Experiment.name == "热处理对照实验"
            )
        ) == 0

    experiment_confirmed = await api.client.post(
        CONFIRM_URL,
        headers=api.headers["researcher"],
        json={"token": experiment_action["token"]},
    )
    assert experiment_confirmed.status_code == 200
    experiment_id = experiment_confirmed.json()["entity_id"]

    requested_tool = "create_sample"
    requested_arguments = {
        "experiment_id": experiment_id,
        "sample_code": "QL-SEM-001",
        "description": "原始样品说明",
        "mass_g": 1.25,
    }
    sample_preview = await api.client.post(
        CHAT_URL,
        headers=api.headers["researcher"],
        json={
            "messages": [
                {
                    "role": "user",
                    "content": "在刚才的实验中登记一个编号为 QL-SEM-001 的样品",
                }
            ]
        },
    )
    assert sample_preview.status_code == 200
    sample_action = sample_preview.json()["pending_actions"][0]
    assert sample_action["tool_name"] == "create_sample"
    assert sample_action["entity_type"] == "sample"

    sample_confirmed = await api.client.post(
        CONFIRM_URL,
        headers=api.headers["researcher"],
        json={"token": sample_action["token"]},
    )
    assert sample_confirmed.status_code == 200
    sample_id = sample_confirmed.json()["entity_id"]

    requested_tool = "update_sample"
    requested_arguments = {
        "sample_id": sample_id,
        "changes": {"description": "AI 修改后的样品说明"},
    }
    update_preview = await api.client.post(
        CHAT_URL,
        headers=api.headers["researcher"],
        json={
            "messages": [
                {"role": "user", "content": "把这个样品的说明改成 AI 修改后的样品说明"}
            ]
        },
    )
    assert update_preview.status_code == 200
    update_action = update_preview.json()["pending_actions"][0]
    assert update_action["tool_name"] == "update_sample"

    update_confirmed = await api.client.post(
        CONFIRM_URL,
        headers=api.headers["researcher"],
        json={"token": update_action["token"]},
    )
    assert update_confirmed.status_code == 200
    backup = update_confirmed.json()["backup"]
    assert backup["entity_type"] == "sample"
    assert backup["operation"] == "update"

    restored = await api.client.post(
        f"{BACKUPS_URL}/{backup['id']}/restore",
        headers=api.headers["researcher"],
    )
    assert restored.status_code == 200
    async with api.session_factory() as session:
        sample = await session.get(Sample, uuid.UUID(sample_id))
        assert sample.description == "原始样品说明"


@pytest.mark.asyncio
async def test_semantic_delete_experiment_restores_dependent_graph(api, monkeypatch):
    async with api.session_factory() as session:
        experiment_read = await session.scalar(
            select(Permission).where(Permission.codename == "experiment:read")
        )
        delete_permission = Permission(codename="experiment:delete")
        deleter_role = Role(
            name="semantic_experiment_deleter",
            permissions=[experiment_read, delete_permission],
        )
        deleter = User(
            username="semantic_experiment_deleter",
            email="semantic-experiment-deleter@example.com",
            hashed_password="unused",
            is_active=True,
            is_approved=True,
            role=deleter_role,
        )
        session.add(deleter)
        await session.flush()
        project = Project(name="Delete Experiment Project", owner_id=deleter.id)
        session.add(project)
        await session.flush()
        session.add(
            ProjectMember(project_id=project.id, user_id=deleter.id, role="owner")
        )
        material = Material(
            name="Experiment Restore Material",
            material_type="metal",
            project_id=project.id,
            created_by=deleter.id,
        )
        experiment = Experiment(
            project_id=project.id,
            name="可恢复实验",
            owner_id=deleter.id,
        )
        session.add_all([material, experiment])
        await session.flush()
        sample = Sample(
            experiment_id=experiment.id,
            material_id=material.id,
            sample_code="RESTORE-EXP-SAMPLE",
            created_by=deleter.id,
        )
        session.add(sample)
        await session.flush()
        processing = ProcessingMethod(
            sample_id=sample.id,
            method_type="annealing",
            created_by=deleter.id,
        )
        characterization = Characterization(
            sample_id=sample.id,
            technique="SEM",
            title="Restore SEM",
            created_by=deleter.id,
        )
        prop = Property(
            material_id=material.id,
            sample_id=sample.id,
            property_type="mechanical",
            property_name="strength",
            value_number=321.0,
            created_by=deleter.id,
        )
        session.add_all([processing, characterization, prop])
        await session.flush()
        analysis = AnalysisResult(
            characterization_id=characterization.id,
            analysis_type="feature_extraction",
            result_data={"ok": True},
            run_by=deleter.id,
        )
        session.add(analysis)
        await session.commit()
        ids = {
            "experiment": experiment.id,
            "sample": sample.id,
            "processing": processing.id,
            "characterization": characterization.id,
            "analysis": analysis.id,
            "property": prop.id,
        }
        deleter_headers = {
            "Authorization": f"Bearer {create_access_token(deleter.id)}"
        }

    async def fake_llm(messages, tools):
        if tools is None:
            return {"role": "assistant", "content": "请确认删除实验。"}
        assert "delete_experiment" in {
            item["function"]["name"] for item in tools
        }
        return {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call_semantic_delete_experiment",
                    "type": "function",
                    "function": {
                        "name": "delete_experiment",
                        "arguments": json.dumps(
                            {"experiment_id": str(ids["experiment"])}
                        ),
                    },
                }
            ],
        }

    monkeypatch.setattr(assistant_service, "request_llm", fake_llm)
    preview = await api.client.post(
        CHAT_URL,
        headers=deleter_headers,
        json={"messages": [{"role": "user", "content": "删除刚才那个实验"}]},
    )
    assert preview.status_code == 200
    action = preview.json()["pending_actions"][0]
    assert action["tool_name"] == "delete_experiment"

    confirmed = await api.client.post(
        CONFIRM_URL,
        headers=deleter_headers,
        json={"token": action["token"]},
    )
    assert confirmed.status_code == 200
    backup_id = confirmed.json()["backup"]["id"]
    async with api.session_factory() as session:
        assert await session.get(Experiment, ids["experiment"]) is None
        assert await session.get(Sample, ids["sample"]) is None
        prop = await session.get(Property, ids["property"])
        assert prop is not None

    restored = await api.client.post(
        f"{BACKUPS_URL}/{backup_id}/restore",
        headers=deleter_headers,
    )
    assert restored.status_code == 200
    async with api.session_factory() as session:
        assert await session.get(Experiment, ids["experiment"]) is not None
        assert await session.get(Sample, ids["sample"]) is not None
        assert await session.get(ProcessingMethod, ids["processing"]) is not None
        assert await session.get(Characterization, ids["characterization"]) is not None
        assert await session.get(AnalysisResult, ids["analysis"]) is not None
        prop = await session.get(Property, ids["property"])
        assert prop.sample_id == ids["sample"]


@pytest.mark.asyncio
async def test_exact_single_search_result_delete_skips_model_loop(api, monkeypatch):
    async with api.session_factory() as session:
        permissions = (
            await session.execute(
                select(Permission).where(
                    Permission.codename.in_(
                        ["material:read", "material:create", "material:update"]
                    )
                )
            )
        ).scalars().all()
        delete_permission = Permission(codename="material:delete")
        deleter_role = Role(
            name="contextual_material_deleter",
            permissions=[*permissions, delete_permission],
        )
        deleter = User(
            username="contextual_material_deleter",
            email="contextual-material-deleter@example.com",
            hashed_password="unused",
            is_active=True,
            is_approved=True,
            role=deleter_role,
        )
        session.add(deleter)
        await session.flush()
        material = Material(
            name="齐鲁化工",
            material_type="other",
            created_by=deleter.id,
        )
        session.add(material)
        await session.commit()
        material_id = material.id
        deleter_headers = {
            "Authorization": f"Bearer {create_access_token(deleter.id)}"
        }

    async def unexpected_llm(messages, tools):
        raise AssertionError("Contextual delete must not call the LLM")

    monkeypatch.setattr(
        assistant_service,
        "request_llm",
        unexpected_llm,
    )
    response = await api.client.post(
        CHAT_URL,
        headers=deleter_headers,
        json={
            "messages": [
                {"role": "user", "content": "帮我查询“齐鲁”相关的数据"},
                {
                    "role": "assistant",
                    "content": (
                        "搜索到 1 条结果：\n\n"
                        "**材料/物质**\n"
                        "- **名称：** 齐鲁化工\n"
                        "- **类型：** 材料\n"
                        "- **更新时间：** 2026-07-22\n\n"
                        "需要我查看这个材料的详细信息吗？"
                    ),
                },
                {"role": "user", "content": "删除这个数据"},
                {
                    "role": "assistant",
                    "content": "本次请求需要的步骤过多，请拆成更小的问题后重试。",
                },
                {"role": "user", "content": "删除这个数据"},
            ]
        },
    )

    assert response.status_code == 200
    assert "上一轮唯一结果" in response.json()["message"]
    pending = response.json()["pending_actions"]
    assert len(pending) == 1
    assert pending[0]["tool_name"] == "delete_material"
    assert pending[0]["summary"] == "删除材料“齐鲁化工”"

    async with api.session_factory() as session:
        assert await session.get(Material, material_id) is not None

    confirmed = await api.client.post(
        CONFIRM_URL,
        headers=deleter_headers,
        json={"token": pending[0]["token"]},
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["backup"]["operation"] == "delete"
    async with api.session_factory() as session:
        assert await session.get(Material, material_id) is None


@pytest.mark.asyncio
async def test_property_test_and_characterization_crud_tools(api, monkeypatch):
    headers, ids = await _create_ai_data_manager(api, "crud")
    next_call = {}

    async def fake_llm(messages, tools):
        if tools is None:
            return {"role": "assistant", "content": "请确认本次数据操作。"}
        advertised = {item["function"]["name"] for item in tools}
        assert next_call["tool"] in advertised
        return {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": f"call_{next_call['tool']}",
                    "type": "function",
                    "function": {
                        "name": next_call["tool"],
                        "arguments": json.dumps(next_call["arguments"]),
                    },
                }
            ],
        }

    monkeypatch.setattr(assistant_service, "request_llm", fake_llm)

    async def prepare_and_confirm(tool, arguments):
        next_call.update(tool=tool, arguments=arguments)
        preview = await api.client.post(
            CHAT_URL,
            headers=headers,
            json={"messages": [{"role": "user", "content": f"执行 {tool}"}]},
        )
        assert preview.status_code == 200, preview.text
        actions = preview.json()["pending_actions"]
        assert len(actions) == 1
        assert actions[0]["tool_name"] == tool
        confirmed = await api.client.post(
            CONFIRM_URL,
            headers=headers,
            json={"token": actions[0]["token"]},
        )
        assert confirmed.status_code == 200, confirmed.text
        return confirmed.json()

    created_property = await prepare_and_confirm(
        "create_property",
        {
            "material_id": str(ids["material"]),
            "sample_id": str(ids["sample"]),
            "property_type": "mechanical",
            "property_name": "tensile_strength",
            "value_number": 120.0,
            "unit": "MPa",
        },
    )
    created_test = await prepare_and_confirm(
        "create_test",
        {
            "material_id": str(ids["material"]),
            "test_name": "拉伸测试",
            "test_method": "GB/T 228.1",
            "measurements": [
                {
                    "property_name": "tensile_strength",
                    "value_number": 120.0,
                    "unit": "MPa",
                }
            ],
        },
    )
    created_characterization = await prepare_and_confirm(
        "create_characterization",
        {
            "sample_id": str(ids["sample"]),
            "technique": "SEM",
            "title": "断口形貌",
            "instrument": "SEM-01",
        },
    )

    assert created_property["backup"] is None
    assert created_test["backup"] is None
    assert created_characterization["backup"] is None
    property_id = created_property["entity_id"]
    test_id = created_test["entity_id"]
    characterization_id = created_characterization["entity_id"]

    updated_property = await prepare_and_confirm(
        "update_property",
        {"property_id": property_id, "changes": {"value_number": 130.0}},
    )
    updated_test = await prepare_and_confirm(
        "update_test",
        {"test_id": test_id, "changes": {"notes": "复测通过"}},
    )
    updated_characterization = await prepare_and_confirm(
        "update_characterization",
        {
            "characterization_id": characterization_id,
            "changes": {"status": "processed"},
        },
    )
    assert updated_property["backup"]["entity_type"] == "property"
    assert updated_test["backup"]["entity_type"] == "test"
    assert updated_characterization["backup"]["entity_type"] == "characterization"

    async with api.session_factory() as session:
        user = (
            await session.execute(
                select(User)
                .options(selectinload(User.role).selectinload(Role.permissions))
                .where(User.id == ids["user"])
            )
        ).scalar_one()
        listed_properties = await assistant_service.execute_read_tool(
            "list_properties",
            {"material_id": str(ids["material"])},
            session,
            user,
        )
        listed_tests = await assistant_service.execute_read_tool(
            "list_tests",
            {"material_id": str(ids["material"])},
            session,
            user,
        )
        listed_characterizations = await assistant_service.execute_read_tool(
            "list_characterizations",
            {"sample_id": str(ids["sample"])},
            session,
            user,
        )
        assert listed_properties["count"] == 1
        assert listed_tests["count"] == 1
        assert len(listed_tests["items"][0]["measurements"]) == 1
        assert listed_characterizations["count"] == 1
        assert (
            await assistant_service.execute_read_tool(
                "get_property", {"property_id": property_id}, session, user
            )
        )["value_number"] == 130.0
        assert (
            await assistant_service.execute_read_tool(
                "get_test", {"test_id": test_id}, session, user
            )
        )["notes"] == "复测通过"
        assert (
            await assistant_service.execute_read_tool(
                "get_characterization",
                {"characterization_id": characterization_id},
                session,
                user,
            )
        )["status"] == "processed"

    for result in (
        updated_property,
        updated_test,
        updated_characterization,
    ):
        restored = await api.client.post(
            f"{BACKUPS_URL}/{result['backup']['id']}/restore",
            headers=headers,
        )
        assert restored.status_code == 200, restored.text

    async with api.session_factory() as session:
        prop = await session.get(Property, uuid.UUID(property_id))
        test = await session.get(MaterialTest, uuid.UUID(test_id))
        characterization = await session.get(
            Characterization, uuid.UUID(characterization_id)
        )
        assert prop.value_number == 120.0
        assert test.notes is None
        assert characterization.status == "raw"


@pytest.mark.asyncio
async def test_delete_property_test_and_characterization_restores_children(
    api, monkeypatch
):
    headers, ids = await _create_ai_data_manager(api, "delete_restore")
    async with api.session_factory() as session:
        prop = Property(
            material_id=ids["material"],
            sample_id=ids["sample"],
            property_type="mechanical",
            property_name="yield_strength",
            value_number=88.0,
            unit="MPa",
            created_by=ids["user"],
        )
        test = MaterialTest(
            material_id=ids["material"],
            test_name="压缩测试",
            created_by=ids["user"],
        )
        characterization = Characterization(
            sample_id=ids["sample"],
            technique="XRD",
            title="物相分析",
            operator_id=ids["user"],
            created_by=ids["user"],
        )
        session.add_all([prop, test, characterization])
        await session.flush()
        measurement = MaterialTestMeasurement(
            test_id=test.id,
            property_name="compressive_strength",
            value_number=210.0,
            unit="MPa",
        )
        analysis = AnalysisResult(
            characterization_id=characterization.id,
            analysis_type="phase_identification",
            result_data={"phase": "alpha"},
            run_by=ids["user"],
        )
        session.add_all([measurement, analysis])
        await session.commit()
        entity_ids = {
            "property": prop.id,
            "test": test.id,
            "characterization": characterization.id,
            "measurement": measurement.id,
            "analysis": analysis.id,
        }

    next_call = {}

    async def fake_llm(messages, tools):
        if tools is None:
            return {"role": "assistant", "content": "请确认删除。"}
        assert next_call["tool"] in {
            item["function"]["name"] for item in tools
        }
        return {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": f"call_{next_call['tool']}",
                    "type": "function",
                    "function": {
                        "name": next_call["tool"],
                        "arguments": json.dumps(next_call["arguments"]),
                    },
                }
            ],
        }

    monkeypatch.setattr(assistant_service, "request_llm", fake_llm)

    async def delete_and_restore(entity_type, child_model=None, child_id=None):
        tool = f"delete_{entity_type}"
        next_call.update(
            tool=tool,
            arguments={
                f"{entity_type}_id": str(entity_ids[entity_type])
            },
        )
        preview = await api.client.post(
            CHAT_URL,
            headers=headers,
            json={"messages": [{"role": "user", "content": f"删除 {entity_type}"}]},
        )
        assert preview.status_code == 200, preview.text
        action = preview.json()["pending_actions"][0]
        assert action["tool_name"] == tool
        confirmed = await api.client.post(
            CONFIRM_URL,
            headers=headers,
            json={"token": action["token"]},
        )
        assert confirmed.status_code == 200, confirmed.text
        assert confirmed.json()["backup"]["entity_type"] == entity_type
        model = {
            "property": Property,
            "test": MaterialTest,
            "characterization": Characterization,
        }[entity_type]
        async with api.session_factory() as session:
            assert await session.get(model, entity_ids[entity_type]) is None
            if child_model is not None:
                assert await session.get(child_model, child_id) is None
        restored = await api.client.post(
            f"{BACKUPS_URL}/{confirmed.json()['backup']['id']}/restore",
            headers=headers,
        )
        assert restored.status_code == 200, restored.text
        async with api.session_factory() as session:
            assert await session.get(model, entity_ids[entity_type]) is not None
            if child_model is not None:
                assert await session.get(child_model, child_id) is not None

    await delete_and_restore("property")
    await delete_and_restore(
        "test",
        MaterialTestMeasurement,
        entity_ids["measurement"],
    )
    await delete_and_restore(
        "characterization",
        AnalysisResult,
        entity_ids["analysis"],
    )


@pytest.mark.asyncio
async def test_independent_test_measurement_crud_and_rollback(api, monkeypatch):
    headers, ids = await _create_ai_data_manager(api, "measurement_crud")
    async with api.session_factory() as session:
        test = MaterialTest(
            material_id=ids["material"],
            test_name="循环测试",
            created_by=ids["user"],
        )
        session.add(test)
        await session.commit()
        test_id = test.id

    next_call = {}

    async def fake_llm(messages, tools):
        if tools is None:
            return {"role": "assistant", "content": "请确认测量值操作。"}
        assert next_call["tool"] in {
            item["function"]["name"] for item in tools
        }
        return {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": f"call_{next_call['tool']}",
                    "type": "function",
                    "function": {
                        "name": next_call["tool"],
                        "arguments": json.dumps(next_call["arguments"]),
                    },
                }
            ],
        }

    monkeypatch.setattr(assistant_service, "request_llm", fake_llm)

    async def prepare_and_confirm(tool, arguments):
        next_call.update(tool=tool, arguments=arguments)
        preview = await api.client.post(
            CHAT_URL,
            headers=headers,
            json={"messages": [{"role": "user", "content": f"执行 {tool}"}]},
        )
        assert preview.status_code == 200, preview.text
        action = preview.json()["pending_actions"][0]
        assert action["tool_name"] == tool
        confirmed = await api.client.post(
            CONFIRM_URL,
            headers=headers,
            json={"token": action["token"]},
        )
        assert confirmed.status_code == 200, confirmed.text
        return confirmed.json()

    created = await prepare_and_confirm(
        "create_test_measurement",
        {
            "test_id": str(test_id),
            "property_name": "疲劳寿命",
            "value_number": 10000,
            "unit": "cycles",
        },
    )
    assert created["entity_type"] == "test_measurement"
    assert created["backup"] is None
    measurement_id = created["entity_id"]

    async with api.session_factory() as session:
        user = (
            await session.execute(
                select(User)
                .options(selectinload(User.role).selectinload(Role.permissions))
                .where(User.id == ids["user"])
            )
        ).scalar_one()
        listed = await assistant_service.execute_read_tool(
            "list_test_measurements",
            {"test_id": str(test_id), "search": "疲劳"},
            session,
            user,
        )
        detail = await assistant_service.execute_read_tool(
            "get_test_measurement",
            {"measurement_id": measurement_id},
            session,
            user,
        )
        assert listed["count"] == 1
        assert detail["value_number"] == 10000

    updated = await prepare_and_confirm(
        "update_test_measurement",
        {
            "measurement_id": measurement_id,
            "changes": {"value_number": 12000, "unit": "cycles"},
        },
    )
    assert updated["backup"]["entity_type"] == "test_measurement"
    async with api.session_factory() as session:
        measurement = await session.get(
            MaterialTestMeasurement, uuid.UUID(measurement_id)
        )
        assert measurement.value_number == 12000

    restored_update = await api.client.post(
        f"{BACKUPS_URL}/{updated['backup']['id']}/restore",
        headers=headers,
    )
    assert restored_update.status_code == 200, restored_update.text
    async with api.session_factory() as session:
        measurement = await session.get(
            MaterialTestMeasurement, uuid.UUID(measurement_id)
        )
        assert measurement.value_number == 10000

    deleted = await prepare_and_confirm(
        "delete_test_measurement",
        {"measurement_id": measurement_id},
    )
    assert deleted["backup"]["operation"] == "delete"
    async with api.session_factory() as session:
        assert (
            await session.get(
                MaterialTestMeasurement, uuid.UUID(measurement_id)
            )
            is None
        )

    restored_delete = await api.client.post(
        f"{BACKUPS_URL}/{deleted['backup']['id']}/restore",
        headers=headers,
    )
    assert restored_delete.status_code == 200, restored_delete.text
    async with api.session_factory() as session:
        measurement = await session.get(
            MaterialTestMeasurement, uuid.UUID(measurement_id)
        )
        assert measurement is not None
        assert measurement.value_number == 10000


@pytest.mark.asyncio
async def test_test_measurement_read_respects_private_project(api, monkeypatch):
    _owner_headers, ids = await _create_ai_data_manager(
        api, "measurement_private"
    )
    async with api.session_factory() as session:
        test = MaterialTest(
            material_id=ids["material"],
            test_name="私有测试",
            created_by=ids["user"],
        )
        session.add(test)
        await session.flush()
        measurement = MaterialTestMeasurement(
            test_id=test.id,
            property_name="私有性能",
            value_number=42,
            unit="MPa",
        )
        session.add(measurement)

        read_permission = await session.scalar(
            select(Permission).where(Permission.codename == "property:read")
        )
        outsider_role = Role(
            name="measurement_private_outsider",
            permissions=[read_permission],
        )
        outsider = User(
            username="measurement_private_outsider",
            email="measurement-private-outsider@example.com",
            hashed_password="unused",
            is_active=True,
            is_approved=True,
            role=outsider_role,
        )
        session.add(outsider)
        await session.commit()
        measurement_id = measurement.id
        outsider_headers = {
            "Authorization": f"Bearer {create_access_token(outsider.id)}"
        }

    captured = {}

    async def fake_llm(messages, tools):
        if messages[-1]["role"] == "tool":
            captured.update(json.loads(messages[-1]["content"]))
            return {"role": "assistant", "content": "查询完成。"}
        assert "get_test_measurement" in {
            item["function"]["name"] for item in tools
        }
        return {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call_private_measurement",
                    "type": "function",
                    "function": {
                        "name": "get_test_measurement",
                        "arguments": json.dumps(
                            {"measurement_id": str(measurement_id)}
                        ),
                    },
                }
            ],
        }

    monkeypatch.setattr(assistant_service, "request_llm", fake_llm)
    response = await api.client.post(
        CHAT_URL,
        headers=outsider_headers,
        json={"messages": [{"role": "user", "content": "查看这个测量值"}]},
    )
    assert response.status_code == 200
    assert captured["ok"] is False
    assert captured["status"] == 403
