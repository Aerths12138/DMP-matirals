"""Build deterministic, confirmation-only imports from uploaded Excel rows."""

import re
from typing import Any

from app.services.import_alignment import align_import_data


FIXED_FIELDS = {
    "name",
    "material_type",
    "formula_string",
    "hill_formula",
    "description",
}


def _base_header(header: str) -> str:
    return re.sub(r"_\d+$", "", header.strip())


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _property_value(value: Any) -> float | str:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return _clean_text(value)


def prepare_excel_import(import_data: dict[str, Any]) -> dict[str, Any]:
    """Align workbook rows and build payloads for the existing import endpoint."""
    headers = import_data["headers"]
    source_rows = import_data["rows"]
    alignment = align_import_data(headers, source_rows)
    mapping = alignment["mapping"]
    normalized_rows = alignment["normalized_rows"]
    blocking_errors: list[str] = []

    if "name" not in mapping.values():
        blocking_errors.append("无法可靠识别材料名称列，请先在数据导入页手动指定字段映射。")

    prepared_rows: list[dict[str, Any]] = []
    missing_name_rows: list[int] = []
    for row_number, row in enumerate(normalized_rows, start=2):
        material: dict[str, Any] = {
            "name": "",
            "material_type": "other",
            "properties": {},
        }
        aliases: list[str] = []
        test_info: dict[str, str] = {}
        conditions: dict[str, str] = {}
        measurements: dict[str, float | str] = {}

        for column_index, header in enumerate(headers):
            value = row[column_index] if column_index < len(row) else ""
            text = _clean_text(value)
            if not text:
                continue
            target = mapping[header]
            if target == "ignore":
                continue
            if target == "aliases":
                aliases.extend(
                    item.strip()
                    for item in re.split(r"[,;，；]", text)
                    if item.strip()
                )
            elif target in FIXED_FIELDS:
                material[target] = text
            elif target in {"test_name", "test_method"}:
                test_info[target] = text
            elif target == "condition":
                conditions[_base_header(header)] = text
            elif target == "result":
                measurements[_base_header(header)] = _property_value(value)
            elif target == "property":
                material["properties"][_base_header(header)] = _property_value(value)

        if not material["name"]:
            missing_name_rows.append(row_number)
            continue
        if aliases:
            material["aliases"] = ",".join(aliases)
        if measurements:
            material["tests"] = [
                {
                    "test_name": test_info.get("test_name", "导入测试"),
                    "test_method": test_info.get("test_method") or None,
                    "conditions": conditions,
                    "measurements": [
                        {
                            "property_name": name,
                            "value_number": value if isinstance(value, float) else None,
                            "value_text": value if isinstance(value, str) else None,
                            "unit": None,
                        }
                        for name, value in measurements.items()
                    ],
                }
            ]
        prepared_rows.append(material)

    if missing_name_rows:
        displayed = "、".join(str(item) for item in missing_name_rows[:10])
        suffix = "等" if len(missing_name_rows) > 10 else ""
        blocking_errors.append(f"源文件第 {displayed} 行{suffix}缺少材料名称，未生成可执行导入。")

    grouped: dict[str, dict[str, Any]] = {}
    if not blocking_errors:
        for row in prepared_rows:
            name = row["name"]
            existing = grouped.get(name)
            if existing is None:
                grouped[name] = row
                continue
            existing.setdefault("tests", []).extend(row.get("tests", []))
            existing["properties"].update(row.get("properties", {}))
            for field in FIXED_FIELDS - {"name"}:
                if not existing.get(field) and row.get(field):
                    existing[field] = row[field]

    import_rows = list(grouped.values()) if not blocking_errors else []
    if not source_rows:
        blocking_errors.append("工作表没有可导入的数据行。")

    warnings = list(alignment["warnings"])
    if import_data.get("sheet_count", 1) > 1:
        warnings.append(
            f"工作簿包含 {import_data['sheet_count']} 个工作表；本次只准备“{import_data['sheet_name']}”。"
        )

    return {
        "filename": import_data["filename"],
        "sheet_name": import_data["sheet_name"],
        "source_row_count": len(source_rows),
        "material_count": len(import_rows),
        "mapping": mapping,
        "normalized_rows": normalized_rows[:20],
        "normalized_rows_truncated": len(normalized_rows) > 20,
        "conversion_count": alignment["conversion_count"],
        "conversions": alignment["conversions"],
        "warnings": warnings,
        "blocking_errors": blocking_errors,
        "import_rows": import_rows,
    }
