"""Static checks for the production container deployment contract."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_production_backend_is_non_root_and_has_no_reload():
    dockerfile = _read("backend/Dockerfile.production")

    assert "USER appuser" in dockerfile
    assert "--workers" in dockerfile
    assert "--reload" not in dockerfile


def test_production_compose_uses_postgres_and_persistent_storage():
    compose = _read("compose.production.yml")

    assert 'USE_SQLITE: "false"' in compose
    assert "condition: service_completed_successfully" in compose
    assert "postgres_data:/var/lib/postgresql/data" in compose
    assert "materials_storage:/data/materials-dmp/storage" in compose
    assert "LLM_BASE_URL:" in compose
    assert "\n  redis:" not in compose


def test_frontend_uses_same_origin_api_proxy():
    nginx = _read("frontend/nginx.conf")

    assert "location /api/" in nginx
    assert "proxy_pass http://backend:8000;" in nginx
    assert "try_files $uri $uri/ /index.html;" in nginx


def test_production_example_has_no_real_secrets():
    env_example = _read(".env.production.example")

    assert "CHANGE_ME_LONG_RANDOM_SECRET" in env_example
    assert "CHANGE_ME_LONG_DATABASE_PASSWORD" in env_example
    assert "sk-" not in env_example
    assert "admin123" not in env_example


def test_intranet_guide_documents_guarded_database_migration():
    guide = _read("INTRANET_DEPLOY.md")

    assert "python -m scripts.migrate_sqlite_to_postgres" in guide
    assert "--execute --confirm REPLACE_TARGET" in guide
    assert "refresh_tokens" in guide
    assert "/data/materials-dmp/storage" in guide
    assert "down -v" in guide
