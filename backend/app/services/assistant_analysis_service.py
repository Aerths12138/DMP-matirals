"""Deterministic, permission-scoped measurement analysis for the AI assistant.

The language model may choose this tool, but never supplies executable SQL. The
queries, unit handling, quality checks, and statistics all run here so an analysis
can be reproduced and audited independently of a model response.
"""

from __future__ import annotations

import json
import math
import statistics
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import material_visibility_condition
from app.models.material import Material
from app.models.property import Property
from app.models.test import Test, TestMeasurement
from app.models.user import User


MAX_ANALYSIS_RECORDS = 500
MAX_PROVENANCE_RECORDS = 50
MAX_OUTLIERS = 20
MAX_GROUPS = 50
ALLOWED_SOURCES = {"all", "properties", "tests"}
ALLOWED_GROUPS = {"material", "test_method", "condition", "none"}

# (dimension, display unit, multiplier to convert the original value.)
# Unknown units deliberately stay separate instead of being guessed or converted.
UNIT_CONVERSIONS: dict[str, tuple[str, str, float]] = {
    "pa": ("pressure", "MPa", 1e-6),
    "kpa": ("pressure", "MPa", 1e-3),
    "mpa": ("pressure", "MPa", 1.0),
    "gpa": ("pressure", "MPa", 1_000.0),
    "s/m": ("conductivity", "S/m", 1.0),
    "s/cm": ("conductivity", "S/m", 100.0),
    "ohmm": ("resistivity", "ohm*m", 1.0),
    "ωm": ("resistivity", "ohm*m", 1.0),
    "ohmcm": ("resistivity", "ohm*m", 0.01),
    "ωcm": ("resistivity", "ohm*m", 0.01),
    "w/mk": ("thermal_conductivity", "W/(m*K)", 1.0),
    "w/(m*k)": ("thermal_conductivity", "W/(m*K)", 1.0),
    "w/(m·k)": ("thermal_conductivity", "W/(m*K)", 1.0),
    "ev": ("energy", "eV", 1.0),
    "%": ("percent", "%", 1.0),
}


def _bad_request(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail)


def _parse_uuid_list(value: Any) -> list[uuid.UUID]:
    if value in (None, []):
        return []
    if not isinstance(value, list) or len(value) > 20:
        raise _bad_request("material_ids must be an array of at most 20 UUIDs")
    try:
        return [uuid.UUID(str(item)) for item in value]
    except (TypeError, ValueError, AttributeError):
        raise _bad_request("material_ids must contain valid UUIDs") from None


def _parse_optional_uuid(value: Any, field_name: str) -> uuid.UUID | None:
    if value in (None, ""):
        return None
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError, AttributeError):
        raise _bad_request(f"{field_name} must be a valid UUID") from None


def _normalise_unit(unit: str | None) -> tuple[str, str, float]:
    compact = (
        (unit or "")
        .strip()
        .lower()
        .replace(" ", "")
        .replace("Ω", "ω")
        .replace("·", "")
        .replace("*", "")
    )
    aliases = {
        "w/(mk)": "w/(m*k)",
    }
    compact = aliases.get(compact, compact)
    if compact in UNIT_CONVERSIONS:
        return UNIT_CONVERSIONS[compact]
    if not compact:
        return ("unitless", "无单位", 1.0)
    return (f"raw:{compact}", (unit or "").strip(), 1.0)


def _conditions_label(conditions: dict[str, Any]) -> str:
    if not conditions:
        return "未记录条件"
    return json.dumps(conditions, ensure_ascii=False, sort_keys=True, default=str)


def _percentile(sorted_values: list[float], fraction: float) -> float:
    if len(sorted_values) == 1:
        return sorted_values[0]
    position = (len(sorted_values) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return sorted_values[lower]
    return sorted_values[lower] + (sorted_values[upper] - sorted_values[lower]) * (position - lower)


def _summary(values: list[float]) -> dict[str, float | int | None]:
    if not values:
        return {"count": 0, "mean": None, "median": None, "min": None, "max": None, "std_dev": None}
    return {
        "count": len(values),
        "mean": round(statistics.fmean(values), 8),
        "median": round(statistics.median(values), 8),
        "min": round(min(values), 8),
        "max": round(max(values), 8),
        "std_dev": round(statistics.stdev(values), 8) if len(values) >= 2 else None,
    }


def _group_label(record: dict[str, Any], group_by: str, condition_key: str | None) -> str:
    if group_by == "material":
        return record["material_name"]
    if group_by == "test_method":
        return record["test_method"] or "未记录方法"
    if group_by == "condition":
        conditions = record["conditions"]
        if condition_key:
            return f"{condition_key}={conditions.get(condition_key, '未记录')}"
        return _conditions_label(conditions)
    return "全部记录"


def _record_reference(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "source": record["source"],
        "record_id": record["record_id"],
        "material_id": record["material_id"],
        "material_name": record["material_name"],
        "value": record["value"],
        "unit": record["unit"],
        "normalised_value": record["normalised_value"],
        "normalised_unit": record["normalised_unit"],
        "test_method": record["test_method"],
        "conditions": record["conditions"],
    }


def build_analysis_card(data: dict[str, Any]) -> dict[str, Any]:
    """Create the bounded presentation payload consumed by the assistant UI."""
    chart_points = [
        {"label": item["label"], "mean": item["mean"], "count": item["count"], "unit": item["unit"]}
        for item in data["groups"]
        if item["mean"] is not None
    ][:12]
    return {
        "analysis_id": str(uuid.uuid4()),
        "title": f"{data['query_plan']['property_name']} 科研测量分析",
        "metric": data["query_plan"]["property_name"],
        "groups": data["groups"],
        "quality": data["quality"],
        "provenance": data["provenance"],
        "query_plan": data["query_plan"],
        "limitations": data["limitations"],
        "chart": {
            "type": "mean_bar",
            "x_label": data["query_plan"]["group_by_label"],
            "y_label": "均值（按兼容单位分别展示）",
            "points": chart_points,
        },
    }


async def analyze_measurements(arguments: dict[str, Any], db: AsyncSession, current_user: User) -> dict[str, Any]:
    """Summarise numerical measurements without accepting arbitrary SQL."""
    property_name = str(arguments.get("property_name") or "").strip()
    if not property_name or len(property_name) > 200:
        raise _bad_request("property_name must be a non-empty string of at most 200 characters")
    source = str(arguments.get("source") or "all")
    group_by = str(arguments.get("group_by") or "material")
    if source not in ALLOWED_SOURCES:
        raise _bad_request("source must be all, properties, or tests")
    if group_by not in ALLOWED_GROUPS:
        raise _bad_request("group_by must be material, test_method, condition, or none")
    condition_key = arguments.get("condition_key")
    if condition_key is not None and (not isinstance(condition_key, str) or len(condition_key) > 100):
        raise _bad_request("condition_key must be a string of at most 100 characters")
    material_ids = _parse_uuid_list(arguments.get("material_ids"))
    project_id = _parse_optional_uuid(arguments.get("project_id"), "project_id")
    try:
        limit = int(arguments.get("limit", 200))
    except (TypeError, ValueError):
        raise _bad_request("limit must be an integer") from None
    if not 1 <= limit <= MAX_ANALYSIS_RECORDS:
        raise _bad_request(f"limit must be between 1 and {MAX_ANALYSIS_RECORDS}")
    validated_only = bool(arguments.get("validated_only", False))

    records: list[dict[str, Any]] = []
    truncated = False
    name_pattern = property_name.casefold()

    if source in {"all", "properties"}:
        statement = (
            select(Property, Material)
            .join(Material, Property.material_id == Material.id)
            .where(material_visibility_condition(current_user))
            .where(Property.property_name.ilike(property_name))
        )
        if material_ids:
            statement = statement.where(Property.material_id.in_(material_ids))
        if project_id:
            statement = statement.where(Material.project_id == project_id)
        if validated_only:
            statement = statement.where(Property.is_validated.is_(True))
        rows = (await db.execute(statement.order_by(Property.created_at.desc()).limit(limit + 1))).all()
        truncated = truncated or len(rows) > limit
        for prop, material in rows[:limit]:
            if prop.property_name.casefold() != name_pattern:
                continue
            dimension, normalised_unit, multiplier = _normalise_unit(prop.unit)
            value = prop.value_number
            normalised_value = value * multiplier if value is not None and math.isfinite(value) else None
            records.append({
                "source": "property", "record_id": str(prop.id), "material_id": str(material.id),
                "material_name": material.name, "value": value, "unit": prop.unit or "",
                "normalised_value": normalised_value, "normalised_unit": normalised_unit,
                "unit_dimension": dimension, "test_method": prop.test_method,
                "conditions": prop.conditions or {}, "is_validated": prop.is_validated,
                "created_at": prop.created_at.isoformat() if prop.created_at else "",
            })

    if source in {"all", "tests"}:
        statement = (
            select(TestMeasurement, Test, Material)
            .join(Test, TestMeasurement.test_id == Test.id)
            .join(Material, Test.material_id == Material.id)
            .where(material_visibility_condition(current_user))
            .where(TestMeasurement.property_name.ilike(property_name))
        )
        if material_ids:
            statement = statement.where(Test.material_id.in_(material_ids))
        if project_id:
            statement = statement.where(Material.project_id == project_id)
        rows = (await db.execute(statement.order_by(TestMeasurement.created_at.desc()).limit(limit + 1))).all()
        truncated = truncated or len(rows) > limit
        for measurement, test, material in rows[:limit]:
            if measurement.property_name.casefold() != name_pattern:
                continue
            dimension, normalised_unit, multiplier = _normalise_unit(measurement.unit)
            value = measurement.value_number
            normalised_value = value * multiplier if value is not None and math.isfinite(value) else None
            records.append({
                "source": "test_measurement", "record_id": str(measurement.id), "material_id": str(material.id),
                "material_name": material.name, "value": value, "unit": measurement.unit or "",
                "normalised_value": normalised_value, "normalised_unit": normalised_unit,
                "unit_dimension": dimension, "test_method": test.test_method,
                "conditions": test.conditions or {}, "is_validated": None,
                "created_at": measurement.created_at.isoformat() if measurement.created_at else "",
            })

    records.sort(key=lambda item: item["created_at"], reverse=True)
    if len(records) > limit:
        truncated = True
        records = records[:limit]

    numeric_records = [item for item in records if item["normalised_value"] is not None]
    missing_numeric_count = len(records) - len(numeric_records)
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for record in numeric_records:
        grouped[(_group_label(record, group_by, condition_key), record["unit_dimension"], record["normalised_unit"])].append(record)

    outliers: list[dict[str, Any]] = []
    groups: list[dict[str, Any]] = []
    groups_truncated = len(grouped) > MAX_GROUPS
    sorted_groups = sorted(grouped.items(), key=lambda item: item[0])[:MAX_GROUPS]
    for (label, _dimension, unit), group_records in sorted_groups:
        values = [item["normalised_value"] for item in group_records]
        summary = _summary(values)
        group_outliers: list[dict[str, Any]] = []
        if len(values) >= 4:
            sorted_values = sorted(values)
            q1, q3 = _percentile(sorted_values, 0.25), _percentile(sorted_values, 0.75)
            iqr = q3 - q1
            lower_bound, upper_bound = q1 - 1.5 * iqr, q3 + 1.5 * iqr
            for record in group_records:
                if record["normalised_value"] < lower_bound or record["normalised_value"] > upper_bound:
                    outlier = {**_record_reference(record), "lower_bound": round(lower_bound, 8), "upper_bound": round(upper_bound, 8)}
                    group_outliers.append(outlier)
                    if len(outliers) < MAX_OUTLIERS:
                        outliers.append(outlier)
        groups.append({"label": label, "unit": unit, **summary, "outlier_count": len(group_outliers)})

    units = sorted({item["normalised_unit"] for item in numeric_records})
    condition_variants = sorted({_conditions_label(item["conditions"]) for item in numeric_records})
    methods = sorted({item["test_method"] or "未记录方法" for item in numeric_records})
    limitations: list[str] = []
    if not records:
        limitations.append("未在当前权限范围内找到同名测量记录；没有据此推断材料性能。")
    if missing_numeric_count:
        limitations.append(f"有 {missing_numeric_count} 条记录缺少数值，未参与统计。")
    if len(units) > 1:
        limitations.append("检测到不兼容或未知单位；系统已按单位拆分统计，未将它们合并比较。")
    if len(condition_variants) > 1 and group_by != "condition":
        limitations.append("检测到多个实验条件；跨条件比较仅供探索，不能替代受控实验结论。")
    if len(methods) > 1 and group_by != "test_method":
        limitations.append("检测到多个测试方法；跨方法汇总可能引入系统性差异。")
    if len(numeric_records) < 4:
        limitations.append("有效数值少于 4 条，未执行 IQR 异常值判定。")
    if groups_truncated:
        limitations.append(f"分组数超过 {MAX_GROUPS}；界面仅显示前 {MAX_GROUPS} 个分组。")
    if truncated:
        limitations.append(f"结果已限制为前 {limit} 条记录；扩大范围前请缩小筛选条件或分批分析。")

    group_by_labels = {"material": "材料", "test_method": "测试方法", "condition": "实验条件", "none": "全部记录"}
    return {
        "query_plan": {
            "analysis_version": "measurement-summary-v1",
            "engine": "permission-scoped semantic query plan (no arbitrary SQL)",
            "property_name": property_name, "source": source,
            "project_id": str(project_id) if project_id else None,
            "material_ids": [str(item) for item in material_ids],
            "group_by": group_by, "group_by_label": group_by_labels[group_by],
            "condition_key": condition_key, "validated_only": validated_only, "limit": limit,
        },
        "quality": {
            "records_returned": len(records), "numeric_records": len(numeric_records),
            "missing_numeric_records": missing_numeric_count, "unit_groups": units,
            "condition_variants": len(condition_variants), "test_method_variants": len(methods),
            "outlier_count": len(outliers),
            "outlier_method": "IQR, 1.5 × IQR; only for groups with at least 4 numeric records",
            "truncated": truncated or groups_truncated,
        },
        "groups": groups,
        "outliers": outliers,
        "provenance": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "record_references": [_record_reference(item) for item in numeric_records[:MAX_PROVENANCE_RECORDS]],
            "record_references_truncated": len(numeric_records) > MAX_PROVENANCE_RECORDS,
        },
        "limitations": limitations,
    }
