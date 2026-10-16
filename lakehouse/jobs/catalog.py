from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from lakehouse.jobs.config import PipelineConfig


@dataclass(frozen=True)
class SourceTable:
    name: str
    watermark_column: str
    key_columns: tuple[str, ...] = ("id",)


# Users and authentication tables are deliberately excluded from the analytical lake.
SOURCE_TABLES: tuple[SourceTable, ...] = (
    SourceTable("projects", "updated_at"),
    SourceTable("materials", "updated_at"),
    SourceTable("experiments", "updated_at"),
    SourceTable("samples", "updated_at"),
    SourceTable("processing_methods", "updated_at"),
    SourceTable("characterizations", "updated_at"),
    SourceTable("properties", "updated_at"),
    SourceTable("measurement_datasets", "updated_at"),
    SourceTable("measurement_points", "updated_at"),
    SourceTable("files", "created_at"),
    SourceTable("analysis_results", "created_at"),
)


def bootstrap_catalog(spark: Any, config: PipelineConfig) -> None:
    for namespace in ("bronze", "silver", "gold", "ops"):
        spark.sql(f"CREATE NAMESPACE IF NOT EXISTS {config.catalog}.{namespace}")

    spark.sql(
        f"""
        CREATE TABLE IF NOT EXISTS {config.table('ops', 'etl_watermarks')} (
            source_table STRING,
            watermark TIMESTAMP,
            batch_id STRING,
            row_count BIGINT,
            updated_at TIMESTAMP
        )
        USING iceberg
        TBLPROPERTIES ('format-version'='2')
        """
    )
    spark.sql(
        f"""
        CREATE TABLE IF NOT EXISTS {config.table('ops', 'pipeline_events')} (
            batch_id STRING,
            stage STRING,
            object_name STRING,
            status STRING,
            row_count BIGINT,
            message STRING,
            recorded_at TIMESTAMP
        )
        USING iceberg
        PARTITIONED BY (days(recorded_at))
        TBLPROPERTIES ('format-version'='2')
        """
    )


def append_pipeline_event(
    spark: Any,
    config: PipelineConfig,
    *,
    stage: str,
    object_name: str,
    status: str,
    row_count: int = 0,
    message: str = "",
) -> None:
    from pyspark.sql.types import (
        LongType,
        StringType,
        StructField,
        StructType,
        TimestampType,
    )

    schema = StructType(
        [
            StructField("batch_id", StringType(), False),
            StructField("stage", StringType(), False),
            StructField("object_name", StringType(), False),
            StructField("status", StringType(), False),
            StructField("row_count", LongType(), False),
            StructField("message", StringType(), False),
            StructField("recorded_at", TimestampType(), False),
        ]
    )
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    frame = spark.createDataFrame(
        [
            (
                config.batch_id,
                stage,
                object_name,
                status,
                int(row_count),
                message[:4000],
                now,
            )
        ],
        schema=schema,
    )
    frame.writeTo(config.table("ops", "pipeline_events")).append()

