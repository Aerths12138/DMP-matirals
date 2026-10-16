from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable

from lakehouse.jobs.catalog import (
    SOURCE_TABLES,
    SourceTable,
    append_pipeline_event,
)
from lakehouse.jobs.config import PipelineConfig
from lakehouse.jobs.sql_utils import jdbc_source_query, merge_statement


def _table_exists(spark: Any, table_name: str) -> bool:
    try:
        spark.table(table_name).limit(0).collect()
        return True
    except Exception as exc:  # Spark exception classes vary between supported releases.
        message = str(exc).lower()
        if "table_or_view_not_found" in message or "cannot be found" in message:
            return False
        raise


def _load_watermark(
    spark: Any, config: PipelineConfig, source_table: str
) -> datetime | None:
    rows = spark.sql(
        f"""
        SELECT MAX(watermark) AS watermark
        FROM {config.table('ops', 'etl_watermarks')}
        WHERE source_table = '{source_table}'
        """
    ).collect()
    return rows[0]["watermark"] if rows else None


def _store_watermark(
    spark: Any,
    config: PipelineConfig,
    *,
    source_table: str,
    watermark: datetime,
    row_count: int,
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
            StructField("source_table", StringType(), False),
            StructField("watermark", TimestampType(), False),
            StructField("batch_id", StringType(), False),
            StructField("row_count", LongType(), False),
            StructField("updated_at", TimestampType(), False),
        ]
    )
    frame = spark.createDataFrame(
        [(source_table, watermark, config.batch_id, int(row_count), datetime.utcnow())],
        schema=schema,
    )
    view_name = f"watermark_{source_table}"
    frame.createOrReplaceTempView(view_name)
    spark.sql(
        f"""
        MERGE INTO {config.table('ops', 'etl_watermarks')} AS target
        USING {view_name} AS source
        ON target.source_table = source.source_table
        WHEN MATCHED THEN UPDATE SET *
        WHEN NOT MATCHED THEN INSERT *
        """
    )


def _read_source(
    spark: Any,
    config: PipelineConfig,
    spec: SourceTable,
    watermark: datetime | None,
) -> Any:
    query = jdbc_source_query(
        spec.name,
        watermark_column=spec.watermark_column,
        watermark=watermark,
    )
    return (
        spark.read.format("jdbc")
        .option("url", config.jdbc_url)
        .option("dbtable", query)
        .option("user", config.jdbc_user)
        .option("password", config.jdbc_password)
        .option("driver", config.jdbc_driver)
        .option("fetchsize", "10000")
        .load()
    )


def ingest_postgres(
    spark: Any,
    config: PipelineConfig,
    *,
    full_refresh: bool = False,
    source_tables: Iterable[SourceTable] = SOURCE_TABLES,
) -> dict[str, int]:
    from pyspark import StorageLevel
    from pyspark.sql import functions as F

    results: dict[str, int] = {}
    for spec in source_tables:
        watermark = None if full_refresh else _load_watermark(
            spark, config, spec.name
        )
        source = _read_source(spark, config, spec, watermark)
        enriched = (
            source.withColumn("_batch_id", F.lit(config.batch_id))
            .withColumn("_ingested_at", F.current_timestamp())
            .withColumn("_source_system", F.lit(config.source_system))
            .persist(StorageLevel.MEMORY_AND_DISK)
        )
        try:
            row_count = enriched.count()
            results[spec.name] = row_count
            if row_count == 0:
                append_pipeline_event(
                    spark,
                    config,
                    stage="bronze",
                    object_name=spec.name,
                    status="skipped",
                    message="No source rows newer than the stored watermark",
                )
                continue

            target = config.table("bronze", spec.name)
            if full_refresh or not _table_exists(spark, target):
                enriched.writeTo(target).using("iceberg").tableProperty(
                    "format-version", "2"
                ).createOrReplace()
            else:
                view_name = f"incoming_{spec.name}"
                enriched.createOrReplaceTempView(view_name)
                spark.sql(
                    merge_statement(
                        target,
                        view_name,
                        key_columns=spec.key_columns,
                    )
                )

            next_watermark = enriched.select(
                F.max(F.col(spec.watermark_column)).alias("watermark")
            ).first()["watermark"]
            if next_watermark is not None:
                _store_watermark(
                    spark,
                    config,
                    source_table=spec.name,
                    watermark=next_watermark,
                    row_count=row_count,
                )
            append_pipeline_event(
                spark,
                config,
                stage="bronze",
                object_name=spec.name,
                status="success",
                row_count=row_count,
                message="full refresh" if full_refresh else "incremental merge",
            )
        except Exception as exc:
            append_pipeline_event(
                spark,
                config,
                stage="bronze",
                object_name=spec.name,
                status="failed",
                message=str(exc),
            )
            raise
        finally:
            enriched.unpersist()
    return results

