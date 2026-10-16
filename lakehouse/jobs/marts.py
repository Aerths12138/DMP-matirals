from __future__ import annotations

from typing import Any

from lakehouse.jobs.catalog import append_pipeline_event
from lakehouse.jobs.config import PipelineConfig


def _replace_table(frame: Any, table_name: str) -> int:
    row_count = frame.count()
    frame.writeTo(table_name).using("iceberg").tableProperty(
        "format-version", "2"
    ).createOrReplace()
    return row_count


def build_marts(spark: Any, config: PipelineConfig) -> dict[str, int]:
    from pyspark.sql import functions as F

    bronze = lambda name: spark.table(config.table("bronze", name))
    projects = bronze("projects").alias("project")
    materials = bronze("materials").alias("material")
    experiments = bronze("experiments").alias("experiment")
    samples = bronze("samples").alias("sample")
    characterizations = bronze("characterizations").alias("characterization")
    properties = bronze("properties").alias("property")
    datasets = bronze("measurement_datasets").alias("dataset")
    points = bronze("measurement_points").alias("point")

    direct_project = projects.alias("direct_project")
    sample_project = projects.alias("sample_project")
    property_observations = (
        properties.join(
            materials,
            F.col("property.material_id") == F.col("material.id"),
            "left",
        )
        .join(
            samples,
            F.col("property.sample_id") == F.col("sample.id"),
            "left",
        )
        .join(
            experiments,
            F.col("sample.experiment_id") == F.col("experiment.id"),
            "left",
        )
        .join(
            direct_project,
            F.col("material.project_id") == F.col("direct_project.id"),
            "left",
        )
        .join(
            sample_project,
            F.col("experiment.project_id") == F.col("sample_project.id"),
            "left",
        )
        .select(
            F.col("property.id").cast("string").alias("observation_id"),
            F.coalesce(
                F.col("direct_project.id"), F.col("sample_project.id")
            ).cast("string").alias("project_id"),
            F.coalesce(
                F.col("direct_project.name"), F.col("sample_project.name")
            ).alias("project_name"),
            F.col("material.id").cast("string").alias("material_id"),
            F.col("material.name").alias("material_name"),
            F.col("material.material_type"),
            F.col("sample.id").cast("string").alias("sample_id"),
            F.col("sample.sample_code"),
            F.col("property.property_type"),
            F.col("property.property_name"),
            F.col("property.value_number"),
            F.col("property.value_text"),
            F.col("property.uncertainty"),
            F.col("property.unit"),
            F.col("property.conditions").cast("string").alias("conditions_json"),
            F.col("property.test_method"),
            F.col("property.source_type"),
            F.coalesce(F.col("property.is_validated"), F.lit(False)).alias(
                "is_validated"
            ),
            F.col("property.created_at").alias("observed_at"),
            F.lit(config.batch_id).alias("_batch_id"),
            F.current_timestamp().alias("_refreshed_at"),
        )
    )
    property_count = _replace_table(
        property_observations,
        config.table("silver", "material_property_observations"),
    )

    measurement_observations = (
        points.join(
            datasets,
            F.col("point.dataset_id") == F.col("dataset.id"),
            "inner",
        )
        .join(
            characterizations,
            F.col("dataset.characterization_id")
            == F.col("characterization.id"),
            "inner",
        )
        .join(
            samples,
            F.col("characterization.sample_id") == F.col("sample.id"),
            "left",
        )
        .join(
            materials,
            F.col("sample.material_id") == F.col("material.id"),
            "left",
        )
        .join(
            experiments,
            F.col("sample.experiment_id") == F.col("experiment.id"),
            "left",
        )
        .join(
            projects,
            F.coalesce(F.col("material.project_id"), F.col("experiment.project_id"))
            == F.col("project.id"),
            "left",
        )
        .select(
            F.col("point.id").cast("string").alias("measurement_point_id"),
            F.col("project.id").cast("string").alias("project_id"),
            F.col("project.name").alias("project_name"),
            F.col("material.id").cast("string").alias("material_id"),
            F.col("material.name").alias("material_name"),
            F.col("sample.id").cast("string").alias("sample_id"),
            F.col("sample.sample_code"),
            F.col("characterization.id").cast("string").alias(
                "characterization_id"
            ),
            F.col("characterization.technique"),
            F.col("dataset.id").cast("string").alias("dataset_id"),
            F.col("dataset.name").alias("dataset_name"),
            F.col("dataset.x_name"),
            F.col("dataset.x_unit"),
            F.col("point.sequence"),
            F.col("point.x_value"),
            F.col("point.values").cast("string").alias("values_json"),
            F.col("dataset.source_file_id").cast("string").alias(
                "source_file_id"
            ),
            F.lit(config.batch_id).alias("_batch_id"),
            F.current_timestamp().alias("_refreshed_at"),
        )
    )
    measurement_count = _replace_table(
        measurement_observations,
        config.table("silver", "measurement_observations"),
    )

    property_summary = (
        spark.table(config.table("silver", "material_property_observations"))
        .where(F.col("value_number").isNotNull())
        .groupBy(
            "project_id",
            "project_name",
            "material_type",
            "property_name",
            "unit",
            "test_method",
            "source_type",
        )
        .agg(
            F.count("observation_id").alias("observation_count"),
            F.countDistinct("material_id").alias("material_count"),
            F.avg("value_number").alias("mean_value"),
            F.stddev_samp("value_number").alias("stddev_value"),
            F.min("value_number").alias("min_value"),
            F.max("value_number").alias("max_value"),
            F.avg(F.col("is_validated").cast("double")).alias(
                "validated_ratio"
            ),
        )
        .withColumn("_batch_id", F.lit(config.batch_id))
        .withColumn("_refreshed_at", F.current_timestamp())
    )
    summary_count = _replace_table(
        property_summary, config.table("gold", "property_summary")
    )

    material_counts = materials.groupBy("project_id").agg(
        F.countDistinct("id").alias("material_count")
    )
    experiment_counts = experiments.groupBy("project_id").agg(
        F.countDistinct("id").alias("experiment_count")
    )
    sample_counts = (
        samples.join(
            experiments,
            F.col("sample.experiment_id") == F.col("experiment.id"),
            "left",
        )
        .groupBy(F.col("experiment.project_id").alias("project_id"))
        .agg(F.countDistinct("sample.id").alias("sample_count"))
    )
    characterization_counts = (
        characterizations.join(
            samples,
            F.col("characterization.sample_id") == F.col("sample.id"),
            "left",
        )
        .join(
            experiments,
            F.col("sample.experiment_id") == F.col("experiment.id"),
            "left",
        )
        .groupBy(F.col("experiment.project_id").alias("project_id"))
        .agg(
            F.countDistinct("characterization.id").alias(
                "characterization_count"
            )
        )
    )
    property_counts = (
        properties.join(
            materials,
            F.col("property.material_id") == F.col("material.id"),
            "left",
        )
        .groupBy(F.col("material.project_id").alias("project_id"))
        .agg(
            F.countDistinct("property.id").alias("property_count"),
            F.sum(
                F.when(F.col("property.is_validated") == True, 1).otherwise(0)
            ).alias("validated_property_count"),
        )
    )
    project_kpis = (
        projects.select(
            F.col("id").alias("project_id"),
            F.col("name").alias("project_name"),
            F.col("status").alias("project_status"),
        )
        .join(material_counts, "project_id", "left")
        .join(experiment_counts, "project_id", "left")
        .join(sample_counts, "project_id", "left")
        .join(characterization_counts, "project_id", "left")
        .join(property_counts, "project_id", "left")
        .fillna(
            0,
            subset=[
                "material_count",
                "experiment_count",
                "sample_count",
                "characterization_count",
                "property_count",
                "validated_property_count",
            ],
        )
        .withColumn("_batch_id", F.lit(config.batch_id))
        .withColumn("_refreshed_at", F.current_timestamp())
    )
    kpi_count = _replace_table(
        project_kpis, config.table("gold", "project_kpis")
    )

    results = {
        "silver.material_property_observations": property_count,
        "silver.measurement_observations": measurement_count,
        "gold.property_summary": summary_count,
        "gold.project_kpis": kpi_count,
    }
    for object_name, row_count in results.items():
        append_pipeline_event(
            spark,
            config,
            stage="mart",
            object_name=object_name,
            status="success",
            row_count=row_count,
        )
    return results

