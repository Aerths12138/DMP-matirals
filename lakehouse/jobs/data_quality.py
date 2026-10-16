from __future__ import annotations

from typing import Any

from lakehouse.jobs.catalog import append_pipeline_event
from lakehouse.jobs.config import PipelineConfig


def _table_exists(spark: Any, table_name: str) -> bool:
    try:
        spark.table(table_name).limit(0).collect()
        return True
    except Exception as exc:
        message = str(exc).lower()
        if "table_or_view_not_found" in message or "cannot be found" in message:
            return False
        raise


def _issue_frame(
    frame: Any,
    *,
    batch_id: str,
    rule_name: str,
    severity: str,
    entity_type: str,
    id_column: str,
    message: Any,
) -> Any:
    from pyspark.sql import functions as F

    return frame.select(
        F.lit(batch_id).alias("batch_id"),
        F.lit(rule_name).alias("rule_name"),
        F.lit(severity).alias("severity"),
        F.lit(entity_type).alias("entity_type"),
        F.col(id_column).cast("string").alias("entity_id"),
        message.alias("message"),
        F.current_timestamp().alias("detected_at"),
    )


def run_data_quality(spark: Any, config: PipelineConfig) -> dict[str, int]:
    from functools import reduce

    from pyspark.sql import DataFrame, functions as F

    properties = spark.table(config.table("bronze", "properties"))
    materials = spark.table(config.table("bronze", "materials"))
    files = spark.table(config.table("bronze", "files"))
    datasets = spark.table(config.table("bronze", "measurement_datasets"))
    points = spark.table(config.table("bronze", "measurement_points"))

    issues = [
        _issue_frame(
            properties.where(
                F.col("value_number").isNull() & F.col("value_text").isNull()
            ),
            batch_id=config.batch_id,
            rule_name="property_requires_value",
            severity="error",
            entity_type="property",
            id_column="id",
            message=F.lit("Both numeric and text values are missing"),
        ),
        _issue_frame(
            properties.where(
                F.col("value_number").isNotNull()
                & (F.col("unit").isNull() | (F.trim(F.col("unit")) == ""))
            ),
            batch_id=config.batch_id,
            rule_name="numeric_property_requires_unit",
            severity="warning",
            entity_type="property",
            id_column="id",
            message=F.concat(
                F.lit("Numeric property has no unit: "), F.col("property_name")
            ),
        ),
        _issue_frame(
            files.where(
                F.col("checksum_sha256").isNull()
                | (F.length(F.col("checksum_sha256")) != 64)
            ),
            batch_id=config.batch_id,
            rule_name="file_requires_sha256",
            severity="warning",
            entity_type="file",
            id_column="id",
            message=F.lit("File checksum is missing or is not a SHA-256 digest"),
        ),
        _issue_frame(
            materials.where(F.col("project_id").isNull()),
            batch_id=config.batch_id,
            rule_name="material_should_belong_to_project",
            severity="warning",
            entity_type="material",
            id_column="id",
            message=F.lit("Material is not assigned to a project"),
        ),
    ]

    actual_points = points.groupBy("dataset_id").agg(
        F.count("id").alias("actual_row_count")
    )
    dataset_mismatches = datasets.join(
        actual_points, datasets.id == actual_points.dataset_id, "left"
    ).where(
        F.col("row_count") != F.coalesce(F.col("actual_row_count"), F.lit(0))
    )
    issues.append(
        _issue_frame(
            dataset_mismatches,
            batch_id=config.batch_id,
            rule_name="dataset_row_count_matches_points",
            severity="error",
            entity_type="measurement_dataset",
            id_column="id",
            message=F.concat(
                F.lit("Declared row_count="),
                F.col("row_count").cast("string"),
                F.lit(", actual="),
                F.coalesce(F.col("actual_row_count"), F.lit(0)).cast("string"),
            ),
        )
    )

    all_issues = reduce(
        lambda left, right: left.unionByName(right), issues
    ).cache()
    issue_count = all_issues.count()
    error_count = all_issues.where(F.col("severity") == "error").count()
    target = config.table("gold", "data_quality_issues")
    if _table_exists(spark, target):
        all_issues.writeTo(target).append()
    else:
        all_issues.writeTo(target).using("iceberg").tableProperty(
            "format-version", "2"
        ).partitionedBy(F.col("batch_id")).create()

    summary = (
        all_issues.groupBy("batch_id", "rule_name", "severity")
        .agg(F.count("entity_id").alias("issue_count"))
        .withColumn("recorded_at", F.current_timestamp())
    )
    summary_target = config.table("gold", "data_quality_summary")
    if _table_exists(spark, summary_target):
        summary.writeTo(summary_target).append()
    else:
        summary.writeTo(summary_target).using("iceberg").tableProperty(
            "format-version", "2"
        ).partitionedBy(F.col("batch_id")).create()
    all_issues.unpersist()

    append_pipeline_event(
        spark,
        config,
        stage="quality",
        object_name="data_quality_issues",
        status="failed" if error_count else "success",
        row_count=issue_count,
        message=f"errors={error_count}",
    )
    if config.fail_on_quality_errors and error_count:
        raise RuntimeError(
            f"Data quality gate failed with {error_count} error-level issue(s)"
        )
    return {"issues": issue_count, "errors": error_count}

