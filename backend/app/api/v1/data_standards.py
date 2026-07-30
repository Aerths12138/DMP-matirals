"""Project-scoped metadata template and unit endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import ensure_project_access, get_db, require_permission
from app.models.data_standard import MetadataTemplate, UnitDefinition
from app.models.user import User
from app.schemas.data_standard import (
    MetadataTemplateCreate,
    MetadataTemplateResponse,
    MetadataTemplateUpdate,
    UnitDefinitionCreate,
    UnitDefinitionResponse,
)
from app.services.metadata_validation import BUILTIN_UNITS, validate_template_fields

router = APIRouter(prefix="/data-standards", tags=["Data standards"])


async def _get_template(db: AsyncSession, template_id: uuid.UUID) -> MetadataTemplate:
    template = await db.get(MetadataTemplate, template_id)
    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Metadata template not found")
    return template


@router.get("/templates", response_model=list[MetadataTemplateResponse])
async def list_metadata_templates(
    project_id: uuid.UUID,
    entity_type: str | None = None,
    active_only: bool = True,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("experiment:read")),
):
    await ensure_project_access(db, current_user, project_id, "viewer")
    query = select(MetadataTemplate).where(MetadataTemplate.project_id == project_id)
    if entity_type is not None:
        if entity_type not in {"sample", "characterization"}:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid entity type")
        query = query.where(MetadataTemplate.entity_type == entity_type)
    if active_only:
        query = query.where(MetadataTemplate.is_active.is_(True))
    result = await db.execute(query.order_by(MetadataTemplate.entity_type, MetadataTemplate.name))
    return result.scalars().all()


@router.post(
    "/templates",
    response_model=MetadataTemplateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_metadata_template(
    body: MetadataTemplateCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("experiment:update")),
):
    await ensure_project_access(db, current_user, body.project_id, "editor")
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Template name cannot be empty")
    duplicate = (
        await db.execute(
            select(MetadataTemplate.id).where(
                MetadataTemplate.project_id == body.project_id,
                MetadataTemplate.entity_type == body.entity_type,
                MetadataTemplate.name == name,
            )
        )
    ).scalar_one_or_none()
    if duplicate is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Template name already exists")

    fields = [field.model_dump() for field in body.fields]
    await validate_template_fields(db, body.project_id, fields)
    template = MetadataTemplate(
        project_id=body.project_id,
        name=name,
        entity_type=body.entity_type,
        description=body.description,
        fields=fields,
        created_by=current_user.id,
    )
    db.add(template)
    await db.flush()
    await db.refresh(template)
    return template


@router.put("/templates/{template_id}", response_model=MetadataTemplateResponse)
async def update_metadata_template(
    template_id: uuid.UUID,
    body: MetadataTemplateUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("experiment:update")),
):
    template = await _get_template(db, template_id)
    await ensure_project_access(db, current_user, template.project_id, "editor")
    update_data = body.model_dump(exclude_unset=True)
    if "name" in update_data:
        update_data["name"] = update_data["name"].strip()
        if not update_data["name"]:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Template name cannot be empty")
    if body.fields is not None:
        update_data["fields"] = [field.model_dump() for field in body.fields]
        await validate_template_fields(db, template.project_id, update_data["fields"])
    for field, value in update_data.items():
        setattr(template, field, value)
    await db.flush()
    await db.refresh(template)
    return template


@router.get("/units", response_model=list[UnitDefinitionResponse])
async def list_units(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("experiment:read")),
):
    await ensure_project_access(db, current_user, project_id, "viewer")
    result = await db.execute(
        select(UnitDefinition)
        .where(
            UnitDefinition.project_id == project_id,
            UnitDefinition.is_active.is_(True),
        )
        .order_by(UnitDefinition.quantity_type, UnitDefinition.symbol)
    )
    builtins = [
        {
            "id": f"builtin:{unit['symbol']}",
            "project_id": None,
            **unit,
            "is_active": True,
            "is_builtin": True,
        }
        for unit in BUILTIN_UNITS
    ]
    custom = [
        {
            "id": str(unit.id),
            "project_id": unit.project_id,
            "symbol": unit.symbol,
            "name": unit.name,
            "quantity_type": unit.quantity_type,
            "description": unit.description,
            "is_active": unit.is_active,
            "is_builtin": False,
            "created_at": unit.created_at,
            "updated_at": unit.updated_at,
        }
        for unit in result.scalars().all()
    ]
    return builtins + custom


@router.post(
    "/units",
    response_model=UnitDefinitionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_unit(
    body: UnitDefinitionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("experiment:update")),
):
    await ensure_project_access(db, current_user, body.project_id, "editor")
    symbol = body.symbol.strip()
    name = body.name.strip()
    quantity_type = body.quantity_type.strip()
    if not symbol or not name or not quantity_type:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unit fields cannot be empty")
    if symbol in {unit["symbol"] for unit in BUILTIN_UNITS}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Unit already exists in the built-in catalog")
    duplicate = (
        await db.execute(
            select(UnitDefinition.id).where(
                UnitDefinition.project_id == body.project_id,
                UnitDefinition.symbol == symbol,
            )
        )
    ).scalar_one_or_none()
    if duplicate is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Unit symbol already exists")

    unit = UnitDefinition(
        project_id=body.project_id,
        symbol=symbol,
        name=name,
        quantity_type=quantity_type,
        description=body.description,
        created_by=current_user.id,
    )
    db.add(unit)
    await db.flush()
    await db.refresh(unit)
    return {
        "id": str(unit.id),
        "project_id": unit.project_id,
        "symbol": unit.symbol,
        "name": unit.name,
        "quantity_type": unit.quantity_type,
        "description": unit.description,
        "is_active": unit.is_active,
        "is_builtin": False,
        "created_at": unit.created_at,
        "updated_at": unit.updated_at,
    }
