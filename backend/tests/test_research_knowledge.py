"""Research-document RAG ingestion, citation, and ACL regression tests."""

import json

import pytest

from app.api.v1 import files as files_api
from app.services import assistant_service
from app.services.file_storage_service import LocalFileStorage


async def _create_project(api, name: str):
    response = await api.client.post(
        "/api/v1/projects",
        headers=api.headers["researcher"],
        json={"name": name},
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _upload_note(api, project_id: str, content: bytes):
    experiment = await api.client.post(
        "/api/v1/experiments",
        headers=api.headers["researcher"],
        json={"project_id": project_id, "name": "RAG source experiment"},
    )
    assert experiment.status_code == 201, experiment.text
    response = await api.client.post(
        "/api/v1/files/upload",
        params={
            "parent_type": "experiment",
            "parent_id": experiment.json()["id"],
            "file_type": "document",
            "description": "RAG source",
        },
        files={"file": ("electrolyte-notes.md", content, "text/markdown")},
        headers=api.headers["researcher"],
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.mark.asyncio
async def test_upload_indexes_text_and_assistant_returns_citations(api, monkeypatch, tmp_path):
    project = await _create_project(api, "RAG evidence project")
    monkeypatch.setattr(files_api, "storage", LocalFileStorage(tmp_path))
    upload = await _upload_note(
        api,
        project["id"],
        b"# LiFePO4 electrolyte study\n\nAt 25 C, the ionic conductivity was 9.8 mS/cm. The separator used was Celgard 2400.",
    )
    assert upload["knowledge"]["status"] == "ready"
    assert upload["knowledge"]["chunk_count"] >= 1

    captured = {}

    async def fake_llm(messages, tools):
        if messages[-1]["role"] == "tool":
            captured.update(json.loads(messages[-1]["content"]))
            return {"role": "assistant", "content": "已依据检索到的实验记录回答，并标明出处。"}
        assert "search_research_knowledge" in {
            item["function"]["name"] for item in tools
        }
        return {
            "role": "assistant",
            "content": None,
            "tool_calls": [{
                "id": "knowledge_search",
                "type": "function",
                "function": {
                    "name": "search_research_knowledge",
                    "arguments": json.dumps({"query": "ionic conductivity", "project_id": project["id"]}),
                },
            }],
        }

    monkeypatch.setattr(assistant_service, "request_llm", fake_llm)
    response = await api.client.post(
        "/api/v1/assistant/chat",
        headers=api.headers["researcher"],
        json={"messages": [{"role": "user", "content": "附件里电导率是多少？"}]},
    )
    assert response.status_code == 200, response.text
    assert captured["ok"] is True
    card = response.json()["knowledge_cards"][0]
    assert card["retrieval"]["engine"] == "permission-scoped lexical BM25"
    assert card["retrieval"]["semantic_embeddings"] is False
    assert card["items"][0]["citation"]["file_id"] == upload["id"]
    assert "9.8 mS/cm" in card["items"][0]["excerpt"]


@pytest.mark.asyncio
async def test_rag_never_returns_private_attachment_to_nonmember(api, monkeypatch, tmp_path):
    project = await _create_project(api, "RAG private project")
    monkeypatch.setattr(files_api, "storage", LocalFileStorage(tmp_path))
    await _upload_note(
        api,
        project["id"],
        b"Private result: the proprietary additive ZR-19 reached 99.2 percent retention.",
    )

    captured = {}

    async def fake_llm(messages, tools):
        if messages[-1]["role"] == "tool":
            captured.update(json.loads(messages[-1]["content"]))
            return {"role": "assistant", "content": "检索完成。"}
        return {
            "role": "assistant",
            "content": None,
            "tool_calls": [{
                "id": "private_search",
                "type": "function",
                "function": {
                    "name": "search_research_knowledge",
                    "arguments": json.dumps({"query": "proprietary additive"}),
                },
            }],
        }

    monkeypatch.setattr(assistant_service, "request_llm", fake_llm)
    response = await api.client.post(
        "/api/v1/assistant/chat",
        headers=api.headers["outsider"],
        json={"messages": [{"role": "user", "content": "查找添加剂信息"}]},
    )
    assert response.status_code == 200, response.text
    assert captured["ok"] is True
    assert captured["data"]["items"] == []
    assert response.json()["knowledge_cards"][0]["items"] == []
