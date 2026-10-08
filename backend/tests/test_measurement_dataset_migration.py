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


def test_measurement_dataset_migration_upgrade_and_downgrade(tmp_path: Path, monkeypatch):
    backend_root = Path(__file__).resolve().parents[1]
    database_path = tmp_path / "measurement-dataset-migration.db"
    async_database_url = f"sqlite+aiosqlite:///{database_path.as_posix()}"
    sync_database_url = f"sqlite:///{database_path.as_posix()}"
    config = _alembic_config(backend_root)
    monkeypatch.setattr(Settings, "database_url", property(lambda _settings: async_database_url))

    command.upgrade(config, "0008")
    command.upgrade(config, "0009")
    assert _current_revision(sync_database_url) == "0009"

    engine = create_engine(sync_database_url)
    try:
        inspector = inspect(engine)
        assert {"measurement_datasets", "measurement_points"}.issubset(inspector.get_table_names())
        assert {column["name"] for column in inspector.get_columns("measurement_datasets")} >= {
            "characterization_id", "name", "x_name", "x_unit", "series_schema", "provenance", "row_count"
        }
        assert {column["name"] for column in inspector.get_columns("measurement_points")} >= {
            "dataset_id", "sequence", "x_value", "values"
        }
    finally:
        engine.dispose()

    command.downgrade(config, "0008")
    engine = create_engine(sync_database_url)
    try:
        tables = inspect(engine).get_table_names()
        assert "measurement_datasets" not in tables
        assert "measurement_points" not in tables
    finally:
        engine.dispose()
