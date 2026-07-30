"""Safely replace a fresh PostgreSQL database with data from SQLite.

The command is a read-only preflight unless both ``--execute`` and
``--confirm REPLACE_TARGET`` are supplied. The PostgreSQL replacement runs
inside one transaction, so a failed copy does not leave a partial migration.
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import MetaData, Table, create_engine, func, inspect, select, text
from sqlalchemy.engine import Connection, Engine, URL, make_url

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.config import settings
from app.database import Base
from app.models import *  # noqa: F403 - register every model in Base.metadata


CONFIRMATION = "REPLACE_TARGET"
IGNORED_TABLES = {"alembic_version", "sqlite_sequence"}
EXCLUDED_DATA_TABLES = {"refresh_tokens"}
BATCH_SIZE = 500


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Preflight or migrate a Materials DMP SQLite database to PostgreSQL."
        )
    )
    parser.add_argument(
        "--source",
        type=Path,
        required=True,
        help="Path to the source materials_dmp.db file.",
    )
    parser.add_argument(
        "--target-url",
        help=(
            "PostgreSQL URL. Defaults to DATABASE_URL or the configured "
            "POSTGRES_* settings."
        ),
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Perform the transaction after preflight checks.",
    )
    parser.add_argument(
        "--confirm",
        help=f"Required with --execute; must equal {CONFIRMATION}.",
    )
    return parser.parse_args(argv)


def to_sync_postgres_url(value: str) -> URL:
    """Convert a supported PostgreSQL URL to SQLAlchemy's sync psycopg driver."""
    url = make_url(value)
    if url.get_backend_name() != "postgresql":
        raise ValueError("The target URL must use PostgreSQL")
    return url.set(drivername="postgresql+psycopg")


def expected_table_names(metadata: MetaData = Base.metadata) -> set[str]:
    return set(metadata.tables)


def local_schema_head() -> str:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    head = ScriptDirectory.from_config(config).get_current_head()
    if head is None:
        raise RuntimeError("The application has no Alembic head revision")
    return head


def database_revision(connection: Connection) -> str | None:
    tables = set(inspect(connection).get_table_names())
    if "alembic_version" not in tables:
        return None
    return connection.execute(
        text("SELECT version_num FROM alembic_version LIMIT 1")
    ).scalar_one_or_none()


def validate_table_set(connection: Connection, label: str) -> None:
    actual = set(inspect(connection).get_table_names()) - IGNORED_TABLES
    expected = expected_table_names()
    missing = expected - actual
    extra = actual - expected
    if missing or extra:
        details: list[str] = []
        if missing:
            details.append(f"missing: {', '.join(sorted(missing))}")
        if extra:
            details.append(f"unexpected: {', '.join(sorted(extra))}")
        raise RuntimeError(f"{label} schema does not match the application ({'; '.join(details)})")


def validate_revisions(source: Connection, target: Connection) -> str:
    expected = local_schema_head()
    source_revision = database_revision(source)
    target_revision = database_revision(target)
    if source_revision != expected:
        raise RuntimeError(
            f"SQLite revision is {source_revision or 'missing'}, expected {expected}. "
            "Run the local database migrations first."
        )
    if target_revision != expected:
        raise RuntimeError(
            f"PostgreSQL revision is {target_revision or 'missing'}, expected {expected}. "
            "Run python -m scripts.init_roles against PostgreSQL first."
        )
    return expected


def validate_sqlite_foreign_keys(source_path: Path) -> None:
    connection = sqlite3.connect(f"file:{source_path.as_posix()}?mode=ro", uri=True)
    try:
        violations = connection.execute("PRAGMA foreign_key_check").fetchmany(10)
    finally:
        connection.close()
    if violations:
        formatted = "; ".join(str(item) for item in violations)
        raise RuntimeError(f"SQLite foreign-key violations found: {formatted}")


def row_counts(
    connection: Connection,
    tables: Iterable[Table] | None = None,
) -> dict[str, int]:
    selected = tables or Base.metadata.sorted_tables
    return {
        table.name: connection.execute(
            select(func.count()).select_from(table)
        ).scalar_one()
        for table in selected
    }


def order_self_references(
    table: Table,
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Put parents before children for single-column self-referencing rows."""
    primary_keys = list(table.primary_key.columns)
    if len(primary_keys) != 1 or not rows:
        return rows

    primary_key = primary_keys[0].name
    self_reference_columns = [
        column.name
        for column in table.columns
        if any(foreign_key.column.table is table for foreign_key in column.foreign_keys)
    ]
    if not self_reference_columns:
        return rows

    remaining = list(rows)
    remaining_ids = {row[primary_key] for row in remaining}
    ordered: list[dict[str, Any]] = []
    while remaining:
        ready = [
            row
            for row in remaining
            if all(
                row.get(column) is None
                or row.get(column) not in remaining_ids
                for column in self_reference_columns
            )
        ]
        if not ready:
            raise RuntimeError(
                f"Self-referencing cycle detected while ordering {table.name}"
            )
        ready_ids = {row[primary_key] for row in ready}
        ordered.extend(ready)
        remaining = [row for row in remaining if row[primary_key] not in ready_ids]
        remaining_ids -= ready_ids
    return ordered


def chunks(rows: Sequence[dict[str, Any]]) -> Iterable[Sequence[dict[str, Any]]]:
    for start in range(0, len(rows), BATCH_SIZE):
        yield rows[start : start + BATCH_SIZE]


def quote_table_list(connection: Connection, tables: Iterable[Table]) -> str:
    preparer = connection.dialect.identifier_preparer
    return ", ".join(preparer.format_table(table) for table in tables)


def reset_postgres_sequences(connection: Connection, tables: Iterable[Table]) -> None:
    preparer = connection.dialect.identifier_preparer
    for table in tables:
        primary_keys = list(table.primary_key.columns)
        if len(primary_keys) != 1:
            continue
        primary_key = primary_keys[0]
        try:
            python_type = primary_key.type.python_type
        except NotImplementedError:
            continue
        if not isinstance(python_type, type) or (
            python_type is not int
        ):
            continue
        table_name = table.fullname
        column_name = primary_key.name
        quoted_table = preparer.format_table(table)
        quoted_column = preparer.quote(column_name)
        sequence_name = connection.execute(
            text("SELECT pg_get_serial_sequence(:table_name, :column_name)"),
            {"table_name": table_name, "column_name": column_name},
        ).scalar_one_or_none()
        if sequence_name:
            connection.execute(
                text(
                    "SELECT setval(CAST(:sequence_name AS regclass), "
                    f"COALESCE(MAX({quoted_column}), 1), "
                    f"MAX({quoted_column}) IS NOT NULL) FROM {quoted_table}"
                ),
                {"sequence_name": sequence_name},
            )


def migrate(source: Connection, target_engine: Engine) -> dict[str, int]:
    tables = list(Base.metadata.sorted_tables)
    source_counts = row_counts(source, tables)
    expected_counts = dict(source_counts)
    for table_name in EXCLUDED_DATA_TABLES:
        expected_counts[table_name] = 0

    with target_engine.begin() as target:
        target.execute(
            text(
                f"TRUNCATE TABLE {quote_table_list(target, tables)} "
                "RESTART IDENTITY CASCADE"
            )
        )
        for table in tables:
            if table.name in EXCLUDED_DATA_TABLES:
                print(f"Skipped {table.name}: existing sessions are invalidated")
                continue

            rows = [
                dict(row)
                for row in source.execute(select(table)).mappings().all()
            ]
            rows = order_self_references(table, rows)
            for batch in chunks(rows):
                target.execute(table.insert(), list(batch))
            print(f"Copied {table.name}: {len(rows)}")

        reset_postgres_sequences(target, tables)
        target_counts = row_counts(target, tables)
        if target_counts != expected_counts:
            mismatches = [
                f"{name}: expected={expected_counts[name]}, target={target_counts.get(name)}"
                for name in expected_counts
                if expected_counts[name] != target_counts.get(name)
            ]
            raise RuntimeError("Row-count verification failed: " + "; ".join(mismatches))

    return expected_counts


def print_counts(title: str, counts: Mapping[str, int]) -> None:
    print(title)
    for name, count in counts.items():
        print(f"  {name}: {count}")
    print(f"  TOTAL: {sum(counts.values())}")


def build_source_engine(source_path: Path) -> Engine:
    resolved = source_path.expanduser().resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"SQLite source file not found: {resolved}")
    return create_engine(f"sqlite:///{resolved.as_posix()}")


def resolve_target_url(argument: str | None) -> URL:
    configured = argument or os.getenv("DATABASE_URL") or settings.database_url
    return to_sync_postgres_url(configured)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.execute and args.confirm != CONFIRMATION:
        raise SystemExit(
            f"--execute requires --confirm {CONFIRMATION}; target was not changed."
        )
    if not args.execute and args.confirm:
        raise SystemExit("--confirm is only valid together with --execute")

    source_path = args.source.expanduser().resolve()
    if not source_path.is_file():
        raise SystemExit(f"SQLite source file not found: {source_path}")
    validate_sqlite_foreign_keys(source_path)
    source_engine = build_source_engine(source_path)
    target_url = resolve_target_url(args.target_url)
    target_engine = create_engine(target_url, pool_pre_ping=True)

    try:
        with source_engine.connect() as source, target_engine.connect() as target:
            validate_table_set(source, "SQLite")
            validate_table_set(target, "PostgreSQL")
            revision = validate_revisions(source, target)
            source_counts = row_counts(source)
            target_counts = row_counts(target)
            print(f"Schema revision: {revision}")
            print(f"Target: {target_url.render_as_string(hide_password=True)}")
            print_counts("SQLite rows:", source_counts)
            print_counts("Current PostgreSQL rows:", target_counts)

        if not args.execute:
            print(
                "\nPreflight passed. No data was changed. To replace the target, "
                f"repeat with --execute --confirm {CONFIRMATION}."
            )
            return 0

        with source_engine.connect() as source:
            migrated_counts = migrate(source, target_engine)
        print_counts("Migration committed and verified:", migrated_counts)
        return 0
    finally:
        source_engine.dispose()
        target_engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
