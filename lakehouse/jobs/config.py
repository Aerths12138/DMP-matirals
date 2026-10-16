from __future__ import annotations

import os
import re
import uuid
from dataclasses import dataclass


_IDENTIFIER_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")


def require_identifier(value: str, *, field_name: str) -> str:
    """Restrict names interpolated into Spark SQL to safe identifiers."""
    if not _IDENTIFIER_PATTERN.fullmatch(value):
        raise ValueError(
            f"{field_name} must start with a lowercase letter and contain only "
            "lowercase letters, numbers, or underscores"
        )
    return value


def parse_bool(value: str | None, *, default: bool = False) -> bool:
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"Invalid boolean value: {value!r}")


@dataclass(frozen=True)
class PipelineConfig:
    batch_id: str
    catalog: str
    warehouse_uri: str
    spark_master_url: str
    jdbc_url: str
    jdbc_user: str
    jdbc_password: str
    jdbc_driver: str
    source_system: str
    fail_on_quality_errors: bool
    event_log_dir: str | None
    s3_endpoint: str | None
    s3_path_style_access: bool

    @classmethod
    def from_env(cls, *, batch_id: str | None = None) -> "PipelineConfig":
        catalog = require_identifier(
            os.getenv("LAKEHOUSE_CATALOG", "lakehouse"),
            field_name="LAKEHOUSE_CATALOG",
        )
        source_system = require_identifier(
            os.getenv("DMP_SOURCE_SYSTEM", "materials_dmp"),
            field_name="DMP_SOURCE_SYSTEM",
        )
        return cls(
            batch_id=batch_id or str(uuid.uuid4()),
            catalog=catalog,
            warehouse_uri=os.getenv(
                "ICEBERG_WAREHOUSE_URI", "file:///warehouse"
            ).rstrip("/"),
            spark_master_url=os.getenv("SPARK_MASTER_URL", "local[2]"),
            jdbc_url=os.getenv(
                "DMP_JDBC_URL", "jdbc:postgresql://postgres:5432/materials_dmp"
            ),
            jdbc_user=os.getenv("DMP_JDBC_USER", "materials"),
            jdbc_password=os.getenv("DMP_JDBC_PASSWORD", "materials_secret"),
            jdbc_driver=os.getenv("DMP_JDBC_DRIVER", "org.postgresql.Driver"),
            source_system=source_system,
            fail_on_quality_errors=parse_bool(
                os.getenv("DMP_FAIL_ON_QUALITY_ERRORS"), default=False
            ),
            event_log_dir=os.getenv("SPARK_EVENT_LOG_DIR") or None,
            s3_endpoint=os.getenv("ICEBERG_S3_ENDPOINT") or None,
            s3_path_style_access=parse_bool(
                os.getenv("ICEBERG_S3_PATH_STYLE_ACCESS"), default=False
            ),
        )

    def table(self, layer: str, name: str) -> str:
        return ".".join(
            (
                require_identifier(self.catalog, field_name="catalog"),
                require_identifier(layer, field_name="layer"),
                require_identifier(name, field_name="table"),
            )
        )

