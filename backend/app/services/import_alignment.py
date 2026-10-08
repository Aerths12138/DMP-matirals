"""Safe, deterministic alignment helpers for material import previews."""

import math
import re
import unicodedata
from typing import Any

from fastapi import HTTPException


ALLOWED_MAPPING_TARGETS = {
    "name",
    "material_type",
    "formula_string",
    "hill_formula",
    "aliases",
    "description",
    "test_name",
    "test_method",
    "property",
    "condition",
    "result",
    "ignore",
}

_FIXED_HEADER_ALIASES = {
    "\u540d\u79f0": "name",
    "\u6750\u6599\u540d\u79f0": "name",
    "\u6837\u54c1\u540d\u79f0": "name",
    "name": "name",
    "material": "name",
    "\u7c7b\u578b": "material_type",
    "\u6750\u6599\u7c7b\u578b": "material_type",
    "\u5206\u7c7b": "material_type",
    "type": "material_type",
    "materialtype": "material_type",
    "\u5316\u5b66\u5f0f": "formula_string",
    "\u5206\u5b50\u5f0f": "formula_string",
    "formula": "formula_string",
    "formulastring": "formula_string",
    "hill\u516c\u5f0f": "hill_formula",
    "hillformula": "hill_formula",
    "\u522b\u540d": "aliases",
    "aliases": "aliases",
    "\u63cf\u8ff0": "description",
    "\u8bf4\u660e": "description",
    "description": "description",
    "\u6d4b\u8bd5\u540d\u79f0": "test_name",
    "\u5b9e\u9a8c\u540d\u79f0": "test_name",
    "testname": "test_name",
    "\u6d4b\u8bd5\u65b9\u6cd5": "test_method",
    "\u8bd5\u9a8c\u65b9\u6cd5": "test_method",
    "testmethod": "test_method",
}

_CONDITION_KEYWORDS = {
    "\u6e29\u5ea6", "temperature", "temp",
    "\u9891\u7387", "frequency", "freq",
    "\u6e7f\u5ea6", "humidity",
    "\u65f6\u95f4", "time", "duration",
    "\u538b\u529b", "pressure",
    "\u7535\u538b", "voltage",
    "\u7535\u6d41", "current",
    "ph",
    "\u6d53\u5ea6", "concentration",
    "\u6c14\u6c1b", "atmosphere",
    "\u5347\u6e29\u901f\u7387", "heatingrate",
    "\u4fdd\u6e29\u65f6\u95f4", "holdingtime",
    "\u5e94\u53d8\u7387", "strainrate",
    "\u8f7d\u8377", "load",
}

_MATERIAL_TYPE_ALIASES = {
    "metal": "metal",
    "\u91d1\u5c5e": "metal",
    "\u5408\u91d1": "metal",
    "alloy": "metal",
    "polymer": "polymer",
    "\u805a\u5408\u7269": "polymer",
    "\u9ad8\u5206\u5b50": "polymer",
    "ceramic": "ceramic",
    "\u9676\u74f7": "ceramic",
    "composite": "composite",
    "\u590d\u5408\u6750\u6599": "composite",
    "\u590d\u6750": "composite",
    "battery": "battery",
    "\u7535\u6c60": "battery",
    "\u9502\u7535\u6c60": "battery",
    "other": "other",
    "\u5176\u4ed6": "other",
}

_SUPERSCRIPT_TRANSLATION = str.maketrans(
    {
        "\u2070": "0",
        "\u00b9": "1",
        "\u00b2": "2",
        "\u00b3": "3",
        "\u2074": "4",
        "\u2075": "5",
        "\u2076": "6",
        "\u2077": "7",
        "\u2078": "8",
        "\u2079": "9",
        "\u207a": "+",
        "\u207b": "-",
    }
)
_DECIMAL_PATTERN = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)"
_STANDARD_NUMBER = re.compile(rf"^{_DECIMAL_PATTERN}(?:[eE][+-]?\d+)?$")
_TIMES_TEN_NUMBER = re.compile(
    rf"^({_DECIMAL_PATTERN})\s*[xX\u00d7*\u00b7]\s*10\s*(?:\^)?\s*([+-]?\d+)$"
)


def _normalized_token(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).strip().lower()
    return re.sub(r"[\s_\-]+", "", normalized)


def _base_header(value: str) -> str:
    return re.sub(r"_\d+$", "", value.strip())


def _validate_import_data(headers: Any, rows: Any) -> None:
    if not isinstance(headers, list) or not headers or len(headers) > 100:
        raise HTTPException(status_code=422, detail="headers must contain 1-100 columns")
    if any(not isinstance(header, str) or not header.strip() for header in headers):
        raise HTTPException(status_code=422, detail="headers must be non-empty strings")
    if len(set(headers)) != len(headers):
        raise HTTPException(status_code=422, detail="headers must be unique")
    if not isinstance(rows, list) or len(rows) > 500:
        raise HTTPException(
            status_code=422,
            detail="rows must be an array with at most 500 items",
        )
    if any(not isinstance(row, list) or len(row) > len(headers) for row in rows):
        raise HTTPException(
            status_code=422,
            detail="each row must not exceed the header width",
        )


def parse_numeric_text(value: Any) -> float | None:
    """Parse a cell only when its entire content is an unambiguous number."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        return number if math.isfinite(number) else None

    text = unicodedata.normalize("NFKC", str(value)).strip()
    if not text:
        return None
    text = text.replace("\u2212", "-").replace("\u2013", "-").translate(
        _SUPERSCRIPT_TRANSLATION
    )
    if re.fullmatch(r"[+-]?\d{1,3}(?:,\d{3})+(?:\.\d+)?(?:[eE][+-]?\d+)?", text):
        text = text.replace(",", "")

    if _STANDARD_NUMBER.fullmatch(text):
        number = float(text)
        return number if math.isfinite(number) else None

    match = _TIMES_TEN_NUMBER.fullmatch(text)
    if match:
        number = float(match.group(1)) * (10 ** int(match.group(2)))
        return number if math.isfinite(number) else None
    return None


def _infer_mapping(
    headers: list[str], rows: list[list[Any]]
) -> tuple[dict[str, str], list[str]]:
    mapping: dict[str, str] = {}
    used_fixed_targets: set[str] = set()
    warnings: list[str] = []

    for index, header in enumerate(headers):
        token = _normalized_token(_base_header(header))
        target = _FIXED_HEADER_ALIASES.get(token)
        if target and target not in used_fixed_targets:
            mapping[header] = target
            used_fixed_targets.add(target)
            continue
        if any(keyword in token for keyword in _CONDITION_KEYWORDS):
            mapping[header] = "condition"
            continue

        samples = [
            row[index]
            for row in rows
            if index < len(row) and str(row[index]).strip()
        ][:50]
        numeric_count = sum(parse_numeric_text(value) is not None for value in samples)
        mapping[header] = (
            "result"
            if samples and numeric_count / len(samples) >= 0.6
            else "property"
        )

    if "name" not in mapping.values():
        for index, header in enumerate(headers):
            if mapping[header] != "property":
                continue
            samples = [
                row[index]
                for row in rows
                if index < len(row) and str(row[index]).strip()
            ][:50]
            text_ratio = sum(parse_numeric_text(value) is None for value in samples)
            if samples and text_ratio / len(samples) >= 0.8:
                mapping[header] = "name"
                warnings.append(
                    f"No explicit material name column was found; inferred '{header}' "
                    "from sample values. Please verify the mapping."
                )
                break
    if "name" not in mapping.values():
        warnings.append(
            "No material name column could be inferred safely. Select one manually."
        )
    return mapping, warnings


def align_import_data(headers: list[str], rows: list[list[Any]]) -> dict:
    """Align material-import columns and normalize safe numeric cells."""
    _validate_import_data(headers, rows)
    mapping, warnings = _infer_mapping(headers, rows)
    normalized_rows: list[list[str | float]] = []
    conversions: list[dict] = []
    conversion_count = 0
    unknown_material_types: set[str] = set()

    for row_index, row in enumerate(rows, start=1):
        normalized_row: list[str | float] = []
        for column_index, header in enumerate(headers):
            raw_value = row[column_index] if column_index < len(row) else ""
            target = mapping[header]
            normalized: str | float = (
                raw_value
                if isinstance(raw_value, (int, float)) and not isinstance(raw_value, bool)
                else str(raw_value or "").strip()
            )
            kind: str | None = None

            if target in {"property", "result"}:
                parsed = parse_numeric_text(raw_value)
                if parsed is not None:
                    normalized = parsed
                    if not isinstance(raw_value, (int, float)):
                        kind = "numeric_text"
            elif target == "material_type" and str(raw_value).strip():
                material_type = _MATERIAL_TYPE_ALIASES.get(
                    _normalized_token(str(raw_value))
                )
                if material_type is None:
                    material_type = "other"
                    unknown_material_types.add(str(raw_value).strip())
                normalized = material_type
                if normalized != str(raw_value).strip():
                    kind = "material_type"

            if kind:
                conversion_count += 1
                if len(conversions) < 200:
                    conversions.append(
                        {
                            "row": row_index,
                            "column": header,
                            "kind": kind,
                            "original": str(raw_value),
                            "normalized": normalized,
                        }
                    )
            normalized_row.append(normalized)
        normalized_rows.append(normalized_row)

    if unknown_material_types:
        values = ", ".join(sorted(unknown_material_types)[:5])
        warnings.append(
            f"Unknown material types were aligned to 'other': {values}"
        )
    if conversion_count > len(conversions):
        warnings.append(
            f"Applied {conversion_count} conversions; returned only the first "
            f"{len(conversions)} details."
        )

    return {
        "mapping": mapping,
        "normalized_rows": normalized_rows,
        "conversion_count": conversion_count,
        "conversions": conversions,
        "warnings": warnings,
    }
