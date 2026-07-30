"""Provider-neutral local LLM configuration tests."""

from sqlalchemy.engine import make_url

from app.config import Settings, settings
from app.services import assistant_service


def test_local_openai_compatible_server_does_not_require_api_key():
    local = Settings(
        _env_file=None,
        LLM_BASE_URL="http://llm.internal:8000/v1/",
        LLM_MODEL="local-tool-model",
        LLM_API_KEY=None,
        DEEPSEEK_API_KEY=None,
    )

    assert local.assistant_is_configured is True
    assert local.assistant_base_url == "http://llm.internal:8000/v1"
    assert local.assistant_model == "local-tool-model"
    assert local.assistant_api_key is None


def test_legacy_deepseek_configuration_remains_supported():
    legacy = Settings(
        _env_file=None,
        LLM_BASE_URL=None,
        LLM_MODEL=None,
        LLM_API_KEY=None,
        DEEPSEEK_API_KEY="legacy-key",
        DEEPSEEK_BASE_URL="https://legacy.example/v1/",
        DEEPSEEK_MODEL="legacy-model",
    )

    assert legacy.assistant_is_configured is True
    assert legacy.assistant_base_url == "https://legacy.example/v1"
    assert legacy.assistant_model == "legacy-model"
    assert legacy.assistant_api_key == "legacy-key"


def test_llm_payload_uses_optional_thinking_and_auth(monkeypatch):
    monkeypatch.setattr(settings, "LLM_MODEL", "local-tool-model")
    monkeypatch.setattr(settings, "LLM_API_KEY", None)
    monkeypatch.setattr(settings, "DEEPSEEK_API_KEY", None)
    monkeypatch.setattr(settings, "LLM_MAX_TOKENS", 2048)
    monkeypatch.setattr(settings, "LLM_TEMPERATURE", 0.1)
    monkeypatch.setattr(settings, "LLM_THINKING_MODE", None)
    monkeypatch.setattr(settings, "LLM_EXTRA_BODY", {"parallel_tool_calls": False})

    messages = [{"role": "user", "content": "查询材料"}]
    tools = [{"type": "function", "function": {"name": "list_materials"}}]
    payload = assistant_service._llm_request_payload(messages, tools)

    assert payload["model"] == "local-tool-model"
    assert payload["max_tokens"] == 2048
    assert payload["parallel_tool_calls"] is False
    assert "thinking" not in payload
    assert payload["tool_choice"] == "auto"
    assert "Authorization" not in assistant_service._llm_request_headers()

    monkeypatch.setattr(settings, "LLM_API_KEY", "internal-token")
    monkeypatch.setattr(settings, "LLM_THINKING_MODE", "disabled")
    payload = assistant_service._llm_request_payload(messages, None)

    assert payload["thinking"] == {"type": "disabled"}
    assert "tools" not in payload
    assert "tool_choice" not in payload
    assert assistant_service._llm_request_headers()["Authorization"] == (
        "Bearer internal-token"
    )


def test_postgres_credentials_with_url_characters_are_encoded():
    configured = Settings(
        _env_file=None,
        USE_SQLITE=False,
        POSTGRES_HOST="postgres.internal",
        POSTGRES_PORT=5432,
        POSTGRES_USER="material@operator",
        POSTGRES_PASSWORD="p@ss:/word",
        POSTGRES_DB="materials_dmp",
    )

    parsed = make_url(configured.database_url)

    assert parsed.username == "material@operator"
    assert parsed.password == "p@ss:/word"
    assert parsed.host == "postgres.internal"
    assert parsed.database == "materials_dmp"
