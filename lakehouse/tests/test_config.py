from __future__ import annotations

import os
import unittest
from datetime import datetime
from unittest.mock import patch

from lakehouse.jobs.config import PipelineConfig, parse_bool, require_identifier
from lakehouse.jobs.sql_utils import jdbc_source_query, merge_statement


class PipelineConfigTests(unittest.TestCase):
    def test_defaults_create_local_development_configuration(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            config = PipelineConfig.from_env(batch_id="batch-1")

        self.assertEqual(config.batch_id, "batch-1")
        self.assertEqual(config.catalog, "lakehouse")
        self.assertEqual(config.warehouse_uri, "file:///warehouse")
        self.assertEqual(config.table("gold", "project_kpis"), "lakehouse.gold.project_kpis")
        self.assertFalse(config.fail_on_quality_errors)

    def test_environment_overrides_are_applied(self) -> None:
        with patch.dict(
            os.environ,
            {
                "LAKEHOUSE_CATALOG": "materials",
                "ICEBERG_WAREHOUSE_URI": "s3://research/warehouse/",
                "SPARK_MASTER_URL": "spark://cluster:7077",
                "DMP_FAIL_ON_QUALITY_ERRORS": "yes",
            },
            clear=True,
        ):
            config = PipelineConfig.from_env(batch_id="batch-2")

        self.assertEqual(config.catalog, "materials")
        self.assertEqual(config.warehouse_uri, "s3://research/warehouse")
        self.assertEqual(config.spark_master_url, "spark://cluster:7077")
        self.assertTrue(config.fail_on_quality_errors)

    def test_identifiers_reject_sql_fragments(self) -> None:
        for value in ("Gold", "gold.table", "gold;drop", "1gold", ""):
            with self.subTest(value=value), self.assertRaises(ValueError):
                require_identifier(value, field_name="test")

    def test_boolean_parser_is_strict(self) -> None:
        self.assertTrue(parse_bool("ON"))
        self.assertFalse(parse_bool("0"))
        with self.assertRaises(ValueError):
            parse_bool("sometimes")


class SqlGenerationTests(unittest.TestCase):
    def test_incremental_jdbc_query_uses_watermark(self) -> None:
        query = jdbc_source_query(
            "materials",
            watermark_column="updated_at",
            watermark=datetime(2026, 1, 2, 3, 4, 5),
        )
        self.assertEqual(
            query,
            "(SELECT * FROM \"materials\" WHERE \"updated_at\" > "
            "TIMESTAMP '2026-01-02 03:04:05.000000') AS source_rows",
        )

    def test_merge_statement_is_idempotent_upsert(self) -> None:
        statement = merge_statement(
            "lakehouse.bronze.materials",
            "incoming_materials",
            key_columns=("id",),
        )
        self.assertIn("target.id = source.id", statement)
        self.assertIn("WHEN MATCHED THEN UPDATE SET *", statement)
        self.assertIn("WHEN NOT MATCHED THEN INSERT *", statement)


if __name__ == "__main__":
    unittest.main()

