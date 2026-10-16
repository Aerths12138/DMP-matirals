from __future__ import annotations

from datetime import datetime

from lakehouse.jobs.config import require_identifier


def jdbc_source_query(
    table: str,
    *,
    watermark_column: str | None = None,
    watermark: datetime | None = None,
) -> str:
    """Build a whitelisted PostgreSQL subquery for Spark's JDBC reader."""
    safe_table = require_identifier(table, field_name="source table")
    sql = f'SELECT * FROM "{safe_table}"'
    if watermark_column is not None and watermark is not None:
        safe_column = require_identifier(
            watermark_column, field_name="watermark column"
        )
        timestamp = watermark.isoformat(sep=" ", timespec="microseconds")
        sql += f' WHERE "{safe_column}" > TIMESTAMP \'{timestamp}\''
    return f"({sql}) AS source_rows"


def merge_statement(
    target_table: str,
    source_view: str,
    *,
    key_columns: tuple[str, ...] = ("id",),
) -> str:
    if len(target_table.split(".")) != 3:
        raise ValueError("target_table must use catalog.namespace.table form")
    for component in target_table.split("."):
        require_identifier(component, field_name="target table component")
    require_identifier(source_view, field_name="source view")
    if not key_columns:
        raise ValueError("At least one merge key is required")
    predicates = []
    for key in key_columns:
        safe_key = require_identifier(key, field_name="merge key")
        predicates.append(f"target.{safe_key} = source.{safe_key}")
    condition = " AND ".join(predicates)
    return (
        f"MERGE INTO {target_table} AS target "
        f"USING {source_view} AS source ON {condition} "
        "WHEN MATCHED THEN UPDATE SET * "
        "WHEN NOT MATCHED THEN INSERT *"
    )

