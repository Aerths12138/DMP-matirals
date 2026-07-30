"""Unit tests for the guarded SQLite-to-PostgreSQL migration command."""

from pathlib import Path

import pytest
from sqlalchemy import Column, ForeignKey, Integer, MetaData, Table

from scripts.migrate_sqlite_to_postgres import (
    CONFIRMATION,
    EXCLUDED_DATA_TABLES,
    main,
    order_self_references,
    to_sync_postgres_url,
)


def test_postgres_url_is_converted_to_sync_driver_without_losing_credentials():
    converted = to_sync_postgres_url(
        "postgresql+asyncpg://material%40user:p%40ss%3Aword@db.internal/materials"
    )

    assert converted.drivername == "postgresql+psycopg"
    assert converted.username == "material@user"
    assert converted.password == "p@ss:word"
    assert converted.host == "db.internal"
    assert converted.database == "materials"


def test_non_postgres_target_is_rejected():
    with pytest.raises(ValueError, match="must use PostgreSQL"):
        to_sync_postgres_url("sqlite:///target.db")


def test_self_referencing_rows_are_ordered_parent_first():
    metadata = MetaData()
    nodes = Table(
        "nodes",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("parent_id", Integer, ForeignKey("nodes.id")),
    )
    rows = [
        {"id": 3, "parent_id": 2},
        {"id": 2, "parent_id": 1},
        {"id": 1, "parent_id": None},
    ]

    ordered = order_self_references(nodes, rows)

    assert [row["id"] for row in ordered] == [1, 2, 3]


def test_self_referencing_cycle_is_rejected():
    metadata = MetaData()
    nodes = Table(
        "nodes",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("parent_id", Integer, ForeignKey("nodes.id")),
    )

    with pytest.raises(RuntimeError, match="cycle"):
        order_self_references(
            nodes,
            [{"id": 1, "parent_id": 2}, {"id": 2, "parent_id": 1}],
        )


def test_execute_requires_explicit_confirmation(tmp_path: Path):
    missing_source = tmp_path / "source.db"

    with pytest.raises(SystemExit, match=f"--confirm {CONFIRMATION}"):
        main(["--source", str(missing_source), "--execute"])


def test_refresh_tokens_are_intentionally_not_migrated():
    assert EXCLUDED_DATA_TABLES == {"refresh_tokens"}
