from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine, inspect

from app.config import Settings


def _alembic_config(backend_root: Path) -> Config:
    config = Config(str(backend_root / "alembic.ini"))
    config.set_main_option("script_location", str(backend_root / "alembic"))
    return config


def _current_revision(database_url: str) -> str | None:
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            return MigrationContext.configure(connection).get_current_revision()
    finally:
        engine.dispose()


def test_assistant_conversation_migration_upgrade_and_downgrade(
    tmp_path: Path,
    monkeypatch,
):
    backend_root = Path(__file__).resolve().parents[1]
    database_path = tmp_path / "assistant-conversation-migration.db"
    async_database_url = f"sqlite+aiosqlite:///{database_path.as_posix()}"
    sync_database_url = f"sqlite:///{database_path.as_posix()}"
    config = _alembic_config(backend_root)

    monkeypatch.setattr(
        Settings,
        "database_url",
        property(lambda _settings: async_database_url),
    )

    command.upgrade(config, "0007")
    assert _current_revision(sync_database_url) == "0007"

    engine = create_engine(sync_database_url)
    try:
        assert "assistant_conversations" not in inspect(engine).get_table_names()
    finally:
        engine.dispose()

    command.upgrade(config, "0008")
    assert _current_revision(sync_database_url) == "0008"

    engine = create_engine(sync_database_url)
    try:
        inspector = inspect(engine)
        assert "assistant_conversations" in inspector.get_table_names()
        assert {column["name"] for column in inspector.get_columns("assistant_conversations")} == {
            "id",
            "user_id",
            "messages",
            "created_at",
            "updated_at",
        }
        indexes = {
            index["name"]: index
            for index in inspector.get_indexes("assistant_conversations")
        }
        assert indexes["ix_assistant_conversations_user_id"]["column_names"] == [
            "user_id"
        ]
        assert indexes["ix_assistant_conversations_user_id"]["unique"] == 1
        assert indexes["ix_assistant_conversations_updated_at"]["unique"] == 0
    finally:
        engine.dispose()

    command.downgrade(config, "0007")
    assert _current_revision(sync_database_url) == "0007"

    engine = create_engine(sync_database_url)
    try:
        assert "assistant_conversations" not in inspect(engine).get_table_names()
    finally:
        engine.dispose()
