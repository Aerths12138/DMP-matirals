import os

from fastapi import FastAPI
from fastapi.testclient import TestClient

import portable_entry


def test_portable_environment_uses_package_local_data(tmp_path, monkeypatch):
    monkeypatch.delenv("SQLITE_PATH", raising=False)
    monkeypatch.delenv("STORAGE_ROOT", raising=False)
    monkeypatch.delenv("SECRET_KEY", raising=False)

    portable_entry.configure_portable_environment(tmp_path)
    first_secret = os.environ["SECRET_KEY"]

    assert os.environ["SQLITE_PATH"] == str(tmp_path / "data" / "materials_dmp.db")
    assert os.environ["STORAGE_ROOT"] == str(tmp_path / "data" / "storage")
    assert len(first_secret) >= 40
    assert (tmp_path / "data" / "secret.key").read_text(encoding="utf-8") == first_secret

    monkeypatch.delenv("SECRET_KEY")
    portable_entry.configure_portable_environment(tmp_path)
    assert os.environ["SECRET_KEY"] == first_secret


def test_portable_spa_serves_routes_without_shadowing_api(tmp_path):
    web_root = tmp_path / "web"
    web_root.mkdir()
    (web_root / "index.html").write_text("portable-index", encoding="utf-8")
    (web_root / "download.txt").write_text("portable-download", encoding="utf-8")

    app = FastAPI()

    @app.get("/api/health")
    async def health():
        return {"status": "ok"}

    portable_entry.mount_portable_frontend(app, web_root)
    client = TestClient(app)

    assert client.get("/api/health").json() == {"status": "ok"}
    assert client.get("/assistant").text == "portable-index"
    assert client.get("/download.txt").text == "portable-download"
