"""Windows portable entry point for the Materials DMP application."""

from __future__ import annotations

import asyncio
import os
import secrets
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path


PORTABLE_CONFIG_KEYS = {
    "LLM_BASE_URL",
    "LLM_MODEL",
    "LLM_API_KEY",
    "LLM_PROXY",
    "LLM_TIMEOUT_SECONDS",
    "LLM_MAX_TOKENS",
    "LLM_TEMPERATURE",
    "LLM_MAX_TOOL_ROUNDS",
    "LLM_THINKING_MODE",
    "LLM_EXTRA_BODY",
    "PORT",
}


def portable_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def _load_portable_config(root: Path) -> None:
    config_path = root / "LLM_CONFIG.env"
    if not config_path.is_file():
        return
    for raw_line in config_path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key in PORTABLE_CONFIG_KEYS and value:
            os.environ.setdefault(key, value)


def configure_portable_environment(root: Path) -> None:
    root = root.resolve()
    data_root = root / "data"
    storage_root = data_root / "storage"
    data_root.mkdir(parents=True, exist_ok=True)
    storage_root.mkdir(parents=True, exist_ok=True)

    secret_path = data_root / "secret.key"
    if secret_path.is_file():
        secret_key = secret_path.read_text(encoding="utf-8").strip()
    else:
        secret_key = secrets.token_urlsafe(48)
        secret_path.write_text(secret_key, encoding="utf-8")

    _load_portable_config(root)
    os.environ.setdefault("USE_SQLITE", "true")
    os.environ.setdefault("SQLITE_PATH", str(data_root / "materials_dmp.db"))
    os.environ.setdefault("STORAGE_BACKEND", "local")
    os.environ.setdefault("STORAGE_ROOT", str(storage_root))
    os.environ.setdefault("SECRET_KEY", secret_key)
    os.environ.setdefault(
        "CORS_ORIGINS",
        '["http://127.0.0.1:8000","http://localhost:8000"]',
    )
    os.environ.setdefault("NO_PROXY", "127.0.0.1,localhost")


def mount_portable_frontend(app, web_root: Path) -> None:
    from fastapi.responses import FileResponse

    web_root = web_root.resolve()
    index_path = web_root / "index.html"
    if not index_path.is_file():
        raise RuntimeError(f"Portable frontend is missing: {index_path}")

    @app.get("/{requested_path:path}", include_in_schema=False)
    async def portable_frontend(requested_path: str):
        candidate = (web_root / requested_path).resolve()
        if candidate.is_relative_to(web_root) and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(index_path)


async def initialize_portable_database() -> None:
    import app.models  # noqa: F401
    from app.database import Base, engine
    from scripts.init_roles import init as init_roles
    from scripts.seed_data import seed as seed_demo_data

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    await init_roles()
    await seed_demo_data()


def _open_browser_when_ready(port: int) -> None:
    for _ in range(60):
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                webbrowser.open(f"http://127.0.0.1:{port}")
                return
        except OSError:
            time.sleep(0.25)


def main() -> None:
    root = portable_root()
    os.chdir(root)
    configure_portable_environment(root)
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    from app.main import app
    import uvicorn

    mount_portable_frontend(app, root / "web")
    asyncio.run(initialize_portable_database())

    port = int(os.getenv("PORT", "8000"))
    if not 1 <= port <= 65535:
        raise ValueError("PORT must be between 1 and 65535")

    print("=" * 54)
    print(f"Materials DMP: http://127.0.0.1:{port}")
    print("Default login: admin / admin123")
    print("Close this window to stop the platform.")
    print("=" * 54)
    threading.Thread(
        target=_open_browser_when_ready,
        args=(port,),
        daemon=True,
    ).start()
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")


if __name__ == "__main__":
    main()
