from __future__ import annotations

from typing import Any

from lakehouse.jobs.config import PipelineConfig


def build_spark_session(config: PipelineConfig, *, app_name: str) -> Any:
    from pyspark.sql import SparkSession

    builder = (
        SparkSession.builder.appName(app_name)
        .master(config.spark_master_url)
        .config(
            "spark.sql.extensions",
            "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions",
        )
        .config(
            f"spark.sql.catalog.{config.catalog}",
            "org.apache.iceberg.spark.SparkCatalog",
        )
        .config(f"spark.sql.catalog.{config.catalog}.type", "hadoop")
        .config(
            f"spark.sql.catalog.{config.catalog}.warehouse",
            config.warehouse_uri,
        )
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.sql.adaptive.enabled", "true")
        .config("spark.sql.adaptive.coalescePartitions.enabled", "true")
        .config("spark.serializer", "org.apache.spark.serializer.KryoSerializer")
    )

    if config.warehouse_uri.startswith("s3://"):
        builder = builder.config(
            f"spark.sql.catalog.{config.catalog}.io-impl",
            "org.apache.iceberg.aws.s3.S3FileIO",
        )
        if config.s3_endpoint:
            builder = builder.config(
                f"spark.sql.catalog.{config.catalog}.s3.endpoint",
                config.s3_endpoint,
            )
        builder = builder.config(
            f"spark.sql.catalog.{config.catalog}.s3.path-style-access",
            str(config.s3_path_style_access).lower(),
        )
    if config.event_log_dir:
        builder = builder.config("spark.eventLog.enabled", "true").config(
            "spark.eventLog.dir", config.event_log_dir
        )

    spark = builder.getOrCreate()
    spark.sparkContext.setLogLevel("WARN")
    return spark
