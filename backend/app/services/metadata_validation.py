"""Validation helpers for template-bound metadata."""

import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.data_standard import MetadataTemplate, UnitDefinition


BUILTIN_UNITS = [
    {"symbol": "K", "name": "开尔文", "quantity_type": "温度"},
    {"symbol": "°C", "name": "摄氏度", "quantity_type": "温度"},
    {"symbol": "s", "name": "秒", "quantity_type": "时间"},
    {"symbol": "min", "name": "分钟", "quantity_type": "时间"},
    {"symbol": "h", "name": "小时", "quantity_type": "时间"},
    {"symbol": "g", "name": "克", "quantity_type": "质量"},
    {"symbol": "mg", "name": "毫克", "quantity_type": "质量"},
    {"symbol": "m", "name": "米", "quantity_type": "长度"},
    {"symbol": "mm", "name": "毫米", "quantity_type": "长度"},
    {"symbol": "μm", "name": "微米", "quantity_type": "长度"},
    {"symbol": "nm", "name": "纳米", "quantity_type": "长度"},
    {"symbol": "Pa", "name": "帕", "quantity_type": "压力"},
    {"symbol": "MPa", "name": "兆帕", "quantity_type": "压力"},
    {"symbol": "GPa", "name": "吉帕", "quantity_type": "压力"},
    {"symbol": "W/(m·K)", "name": "瓦每米开尔文", "quantity_type": "热导率"},
    {"symbol": "S/cm", "name": "西门子每厘米", "quantity_type": "电导率"},
    {"symbol": "wt%", "name": "质量百分比", "quantity_type": "组成"},
    {"symbol": "at%", "name": "原子百分比", "quantity_type": "组成"},
]


async def get_metadata_template(
    db: AsyncSession,
    template_id: uuid.UUID,
    project_id: uuid.UUID,
    entity_type: str,
) -> MetadataTemplate:
    template = await db.get(MetadataTemplate, template_id)
    if template is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Metadata template not found",
        )
    if template.project_id != project_id or template.entity_type != entity_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Metadata template does not belong to this project or entity type",
        )
    if not template.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Metadata template is inactive",
        )
    return template


async def validate_template_fields(
    db: AsyncSession,
    project_id: uuid.UUID,
    fields: list[dict],
) -> None:
    keys = [field["key"] for field in fields]
    if len(set(keys)) != len(keys):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Metadata field keys must be unique",
        )

    units = {field.get("unit") for field in fields if field.get("unit")}
    if not units:
        return
    allowed = {unit["symbol"] for unit in BUILTIN_UNITS}
    result = await db.execute(
        select(UnitDefinition.symbol).where(
            UnitDefinition.project_id == project_id,
            UnitDefinition.is_active.is_(True),
        )
    )
    allowed.update(result.scalars().all())
    unknown = sorted(units - allowed)
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown controlled units: {', '.join(unknown)}",
        )


def validate_metadata(template: MetadataTemplate, metadata: dict) -> None:
    definitions = {field["key"]: field for field in template.fields}
    unknown = sorted(set(metadata) - set(definitions))
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown metadata fields: {', '.join(unknown)}",
        )

    for key, definition in definitions.items():
        value = metadata.get(key)
        if definition.get("required") and (value is None or value == ""):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Required metadata field is missing: {key}",
            )
        if value is None:
            continue

        value_type = definition.get("value_type", "string")
        valid_type = {
            "string": isinstance(value, str),
            "number": isinstance(value, (int, float)) and not isinstance(value, bool),
            "integer": isinstance(value, int) and not isinstance(value, bool),
            "boolean": isinstance(value, bool),
        }.get(value_type, False)
        if not valid_type:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid value type for metadata field: {key}",
            )

        options = definition.get("options") or []
        if options and value not in options:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Value for {key} must be one of the controlled options",
            )
