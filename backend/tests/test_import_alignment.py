"""AI-assisted material import alignment tests."""

import json

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.permission import Permission, Role
from app.models.user import User
from app.services import assistant_service
from app.services.import_alignment import parse_numeric_text


ALIGN_URL = "/api/v1/assistant/import/align"
CHAT_URL = "/api/v1/assistant/chat"


async def _grant_import_permission(api, user_id):
    async with api.session_factory() as session:
        user = await session.scalar(
            select(User)
            .options(selectinload(User.role).selectinload(Role.permissions))
            .where(User.id == user_id)
        )
        permission = await session.scalar(
            select(Permission).where(Permission.codename == "import:create")
        )
        if permission is None:
            permission = Permission(codename="import:create")
            session.add(permission)
            await session.flush()
        if permission not in user.role.permissions:
            user.role.permissions.append(permission)
        await session.commit()


def test_scientific_notation_parser_is_strict():
    assert parse_numeric_text("1.23E-4") == pytest.approx(0.000123)
    assert parse_numeric_text("3\u00d710\u207b\u00b3") == pytest.approx(0.003)
    assert parse_numeric_text("1.2 x 10^-5") == pytest.approx(0.000012)
    assert parse_numeric_text("1,234.5") == pytest.approx(1234.5)
    assert parse_numeric_text("1.2 MPa") is None
    assert parse_numeric_text("C10H8") is None


@pytest.mark.asyncio
async def test_import_alignment_endpoint_maps_and_normalizes(api):
    await _grant_import_permission(api, api.user_ids["researcher"])
    response = await api.client.post(
        ALIGN_URL,
        headers=api.headers["researcher"],
        json={
            "headers": [
                "\u540d\u79f0",
                "\u6750\u6599\u7c7b\u578b",
                "\u7535\u5bfc\u7387",
                "\u6e29\u5ea6",
                "\u6279\u6b21\u8bf4\u660e",
            ],
            "rows": [
                ["\u6837\u54c1 A", "\u91d1\u5c5e", "1.2E-4", "25", "\u9996\u6279"],
                ["\u6837\u54c1 B", "\u805a\u5408\u7269", "3\u00d710\u207b\u00b3", "30", "\u590d\u6d4b"],
                ["\u6837\u54c1 C"],
            ],
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["mapping"] == {
        "\u540d\u79f0": "name",
        "\u6750\u6599\u7c7b\u578b": "material_type",
        "\u7535\u5bfc\u7387": "result",
        "\u6e29\u5ea6": "condition",
        "\u6279\u6b21\u8bf4\u660e": "property",
    }
    assert data["normalized_rows"][0] == [
        "\u6837\u54c1 A", "metal", 0.00012, "25", "\u9996\u6279"
    ]
    assert data["normalized_rows"][1] == [
        "\u6837\u54c1 B", "polymer", 0.003, "30", "\u590d\u6d4b"
    ]
    assert data["normalized_rows"][2] == ["\u6837\u54c1 C", "", "", "", ""]
    assert data["conversion_count"] == 4


@pytest.mark.asyncio
async def test_import_alignment_endpoint_rejects_overwide_rows(api):
    await _grant_import_permission(api, api.user_ids["researcher"])
    response = await api.client.post(
        ALIGN_URL,
        headers=api.headers["researcher"],
        json={"headers": ["name"], "rows": [["sample A", "discarded"]]},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "each row must not exceed the header width"


@pytest.mark.asyncio
async def test_semantic_import_alignment_rejects_overwide_rows(api):
    await _grant_import_permission(api, api.user_ids["researcher"])
    async with api.session_factory() as session:
        user = await session.scalar(
            select(User)
            .options(selectinload(User.role).selectinload(Role.permissions))
            .where(User.id == api.user_ids["researcher"])
        )

        with pytest.raises(HTTPException) as exc_info:
            await assistant_service.execute_read_tool(
                "align_import_data",
                {"headers": ["name"], "rows": [["sample A", "discarded"]]},
                session,
                user,
            )

    assert exc_info.value.status_code == 422
    assert exc_info.value.detail == "each row must not exceed the header width"


@pytest.mark.asyncio
async def test_import_alignment_requires_import_permission(api):
    response = await api.client.post(
        ALIGN_URL,
        headers=api.headers["viewer"],
        json={"headers": ["\u540d\u79f0"], "rows": [["\u6837\u54c1 A"]]},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_assistant_can_call_import_alignment_semantically(api, monkeypatch):
    await _grant_import_permission(api, api.user_ids["researcher"])
    captured_result = {}

    async def fake_llm(messages, tools):
        if messages[-1]["role"] == "tool":
            captured_result.update(json.loads(messages[-1]["content"])["data"])
            return {"role": "assistant", "content": "Alignment preview is ready."}
        advertised = {item["function"]["name"] for item in tools}
        assert "align_import_data" in advertised
        return {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call_align_import",
                    "type": "function",
                    "function": {
                        "name": "align_import_data",
                        "arguments": json.dumps(
                            {
                                "headers": ["\u540d\u79f0", "\u7535\u5bfc\u7387"],
                                "rows": [["\u6837\u54c1 A", "2.5\u00d710\u207b\u2074"]],
                            }
                        ),
                    },
                }
            ],
        }

    monkeypatch.setattr(assistant_service, "request_llm", fake_llm)
    response = await api.client.post(
        CHAT_URL,
        headers=api.headers["researcher"],
        json={"messages": [{"role": "user", "content": "Align this import."}]},
    )

    assert response.status_code == 200
    assert response.json()["message"] == "Alignment preview is ready."
    assert response.json()["pending_actions"] == []
    assert captured_result["mapping"] == {
        "\u540d\u79f0": "name",
        "\u7535\u5bfc\u7387": "result",
    }
    assert captured_result["normalized_rows"] == [["\u6837\u54c1 A", 0.00025]]
