from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from lakehouse.jobs.catalog import append_pipeline_event
from lakehouse.jobs.config import PipelineConfig


def _replace_bronze(
    spark: Any,
    config: PipelineConfig,
    *,
    table_name: str,
    rows: list[dict[str, object]],
    schema: str,
) -> int:
    from pyspark.sql import functions as F

    frame = (
        spark.createDataFrame(rows, schema=schema)
        .withColumn("_batch_id", F.lit(config.batch_id))
        .withColumn("_ingested_at", F.current_timestamp())
        .withColumn("_source_system", F.lit("portfolio_demo"))
    )
    frame.writeTo(config.table("bronze", table_name)).using(
        "iceberg"
    ).tableProperty("format-version", "2").createOrReplace()
    append_pipeline_event(
        spark,
        config,
        stage="bronze",
        object_name=table_name,
        status="success",
        row_count=len(rows),
        message="deterministic portfolio demo data",
    )
    return len(rows)


def load_demo_source(spark: Any, config: PipelineConfig) -> dict[str, int]:
    """Create a small, deterministic source dataset for recruiter-friendly demos."""
    now = datetime(2026, 1, 15, 8, 0, 0)
    ids = {
        "project": "10000000-0000-0000-0000-000000000001",
        "experiment": "20000000-0000-0000-0000-000000000001",
        "material_a": "30000000-0000-0000-0000-000000000001",
        "material_b": "30000000-0000-0000-0000-000000000002",
        "sample_a": "40000000-0000-0000-0000-000000000001",
        "sample_b": "40000000-0000-0000-0000-000000000002",
        "char_a": "50000000-0000-0000-0000-000000000001",
        "dataset_a": "60000000-0000-0000-0000-000000000001",
        "file_a": "70000000-0000-0000-0000-000000000001",
    }
    definitions = {
        "projects": (
            [{"id": ids["project"], "name": "Battery materials demo", "status": "active", "created_at": now, "updated_at": now}],
            "id string, name string, status string, created_at timestamp, updated_at timestamp",
        ),
        "materials": (
            [
                {"id": ids["material_a"], "project_id": ids["project"], "name": "LLZO-A", "material_type": "ceramic", "formula_string": "Li7La3Zr2O12", "composition": json.dumps([{"element": "Li", "amount": 7}]), "created_at": now, "updated_at": now},
                {"id": ids["material_b"], "project_id": ids["project"], "name": "LLZO-B", "material_type": "ceramic", "formula_string": "Li6.4La3Zr1.4Ta0.6O12", "composition": json.dumps([{"element": "Ta", "amount": 0.6}]), "created_at": now, "updated_at": now},
            ],
            "id string, project_id string, name string, material_type string, formula_string string, composition string, created_at timestamp, updated_at timestamp",
        ),
        "experiments": (
            [{"id": ids["experiment"], "project_id": ids["project"], "name": "Sintering temperature screening", "status": "completed", "created_at": now, "updated_at": now}],
            "id string, project_id string, name string, status string, created_at timestamp, updated_at timestamp",
        ),
        "samples": (
            [
                {"id": ids["sample_a"], "experiment_id": ids["experiment"], "material_id": ids["material_a"], "sample_code": "LLZO-A-1100", "status": "characterizing", "created_at": now, "updated_at": now},
                {"id": ids["sample_b"], "experiment_id": ids["experiment"], "material_id": ids["material_b"], "sample_code": "LLZO-B-1150", "status": "characterizing", "created_at": now, "updated_at": now},
            ],
            "id string, experiment_id string, material_id string, sample_code string, status string, created_at timestamp, updated_at timestamp",
        ),
        "processing_methods": (
            [
                {"id": "41000000-0000-0000-0000-000000000001", "sample_id": ids["sample_a"], "material_id": ids["material_a"], "method_type": "sintering", "parameters": json.dumps({"temperature_c": 1100, "duration_h": 4}), "order_in_chain": 1, "created_at": now, "updated_at": now},
                {"id": "41000000-0000-0000-0000-000000000002", "sample_id": ids["sample_b"], "material_id": ids["material_b"], "method_type": "sintering", "parameters": json.dumps({"temperature_c": 1150, "duration_h": 4}), "order_in_chain": 1, "created_at": now, "updated_at": now},
            ],
            "id string, sample_id string, material_id string, method_type string, parameters string, order_in_chain int, created_at timestamp, updated_at timestamp",
        ),
        "characterizations": (
            [{"id": ids["char_a"], "sample_id": ids["sample_a"], "technique": "EIS", "instrument": "BioLogic VMP3", "parameters": json.dumps({"temperature_c": 25}), "status": "processed", "quality_flag": "good", "created_at": now, "updated_at": now}],
            "id string, sample_id string, technique string, instrument string, parameters string, status string, quality_flag string, created_at timestamp, updated_at timestamp",
        ),
        "properties": (
            [
                {"id": "80000000-0000-0000-0000-000000000001", "material_id": ids["material_a"], "sample_id": ids["sample_a"], "property_type": "electrical", "property_name": "ionic_conductivity", "value_number": 0.0012, "value_text": None, "uncertainty": 0.0001, "unit": "S/cm", "conditions": json.dumps({"temperature_c": 25}), "test_method": "EIS", "source_type": "experimental", "is_validated": True, "created_at": now, "updated_at": now},
                {"id": "80000000-0000-0000-0000-000000000002", "material_id": ids["material_b"], "sample_id": ids["sample_b"], "property_type": "electrical", "property_name": "ionic_conductivity", "value_number": 0.0018, "value_text": None, "uncertainty": 0.0002, "unit": "S/cm", "conditions": json.dumps({"temperature_c": 25}), "test_method": "EIS", "source_type": "experimental", "is_validated": False, "created_at": now, "updated_at": now},
            ],
            "id string, material_id string, sample_id string, property_type string, property_name string, value_number double, value_text string, uncertainty double, unit string, conditions string, test_method string, source_type string, is_validated boolean, created_at timestamp, updated_at timestamp",
        ),
        "measurement_datasets": (
            [{"id": ids["dataset_a"], "characterization_id": ids["char_a"], "source_file_id": ids["file_a"], "name": "Nyquist spectrum", "x_name": "frequency", "x_unit": "Hz", "series_schema": json.dumps([{"name": "z_real", "unit": "ohm"}, {"name": "z_imag", "unit": "ohm"}]), "provenance": json.dumps({"parser": "demo"}), "row_count": 3, "created_at": now, "updated_at": now}],
            "id string, characterization_id string, source_file_id string, name string, x_name string, x_unit string, series_schema string, provenance string, row_count int, created_at timestamp, updated_at timestamp",
        ),
        "measurement_points": (
            [
                {"id": f"61000000-0000-0000-0000-00000000000{index}", "dataset_id": ids["dataset_a"], "sequence": index, "x_value": frequency, "values": json.dumps({"z_real": real, "z_imag": imag}), "created_at": now, "updated_at": now}
                for index, (frequency, real, imag) in enumerate(((1000.0, 12.0, -3.0), (100.0, 15.0, -6.0), (10.0, 24.0, -2.0)), start=1)
            ],
            "id string, dataset_id string, sequence int, x_value double, values string, created_at timestamp, updated_at timestamp",
        ),
        "files": (
            [{"id": ids["file_a"], "parent_type": "characterization", "parent_id": ids["char_a"], "original_name": "llzo_a_eis.csv", "mime_type": "text/csv", "file_size_bytes": 512, "checksum_sha256": "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08", "file_type": "spreadsheet", "created_at": now}],
            "id string, parent_type string, parent_id string, original_name string, mime_type string, file_size_bytes long, checksum_sha256 string, file_type string, created_at timestamp",
        ),
        "analysis_results": (
            [{"id": "90000000-0000-0000-0000-000000000001", "characterization_id": ids["char_a"], "analysis_type": "equivalent_circuit_fit", "pipeline_name": "eis-fit", "model_name": "R-RQ", "model_version": "1.0", "result_data": json.dumps({"resistance_ohm": 11.8}), "quality_metrics": json.dumps({"r_squared": 0.997}), "source_file_id": ids["file_a"], "processing_time_ms": 850, "gpu_used": False, "is_latest": True, "previous_version_id": None, "created_at": now}],
            "id string, characterization_id string, analysis_type string, pipeline_name string, model_name string, model_version string, result_data string, quality_metrics string, source_file_id string, processing_time_ms int, gpu_used boolean, is_latest boolean, previous_version_id string, created_at timestamp",
        ),
    }

    return {
        name: _replace_bronze(
            spark,
            config,
            table_name=name,
            rows=rows,
            schema=schema,
        )
        for name, (rows, schema) in definitions.items()
    }
