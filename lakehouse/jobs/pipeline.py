from __future__ import annotations

import argparse
import json
import traceback

from lakehouse.jobs.catalog import append_pipeline_event, bootstrap_catalog
from lakehouse.jobs.config import PipelineConfig
from lakehouse.jobs.data_quality import run_data_quality
from lakehouse.jobs.demo_source import load_demo_source
from lakehouse.jobs.ingest_postgres import ingest_postgres
from lakehouse.jobs.marts import build_marts
from lakehouse.jobs.spark_session import build_spark_session


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Load Materials DMP data into an Apache Iceberg lakehouse"
    )
    parser.add_argument(
        "--source",
        choices=("demo", "postgres"),
        default="demo",
        help="Use deterministic demo data or the DMP PostgreSQL database",
    )
    parser.add_argument(
        "--full-refresh",
        action="store_true",
        help="Replace bronze snapshots instead of using stored watermarks",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = PipelineConfig.from_env()
    spark = build_spark_session(
        config, app_name=f"materials-dmp-lakehouse-{config.batch_id[:8]}"
    )
    result: dict[str, object] = {
        "batch_id": config.batch_id,
        "source": args.source,
    }
    try:
        bootstrap_catalog(spark, config)
        append_pipeline_event(
            spark,
            config,
            stage="pipeline",
            object_name="materials_dmp",
            status="started",
            message=f"source={args.source}; full_refresh={args.full_refresh}",
        )
        if args.source == "demo":
            result["bronze"] = load_demo_source(spark, config)
        else:
            result["bronze"] = ingest_postgres(
                spark, config, full_refresh=args.full_refresh
            )
        result["marts"] = build_marts(spark, config)
        result["quality"] = run_data_quality(spark, config)
        append_pipeline_event(
            spark,
            config,
            stage="pipeline",
            object_name="materials_dmp",
            status="success",
        )
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except Exception as exc:
        try:
            append_pipeline_event(
                spark,
                config,
                stage="pipeline",
                object_name="materials_dmp",
                status="failed",
                message=str(exc),
            )
        except Exception:
            traceback.print_exc()
        raise
    finally:
        spark.stop()


if __name__ == "__main__":
    raise SystemExit(main())
