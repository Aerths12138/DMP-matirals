"""Property CRUD and bulk import endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, distinct, exists, func, or_, select, true
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    ensure_material_access,
    get_db,
    material_visibility_condition,
    require_permission,
)
from app.models.experiment import Experiment
from app.models.material import Material
from app.models.project import ProjectMember
from app.models.property import Property
from app.models.sample import Sample
from app.models.user import User
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.property import (
    PropertyBulkCreate,
    PropertyComparisonResponse,
    PropertyCreate,
    PropertyResponse,
    PropertyUpdate,
    SamplePropertyComparisonResponse,
)

router = APIRouter(prefix="/properties", tags=["Properties"])


async def _get_material(db: AsyncSession, material_id: uuid.UUID) -> Material:
    material = (
        await db.execute(select(Material).where(Material.id == material_id))
    ).scalar_one_or_none()
    if material is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Material not found",
        )
    return material


async def _get_property(db: AsyncSession, property_id: uuid.UUID) -> Property:
    prop = (
        await db.execute(select(Property).where(Property.id == property_id))
    ).scalar_one_or_none()
    if prop is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property not found",
        )
    return prop


async def _ensure_property_access(
    db: AsyncSession,
    current_user: User,
    prop: Property,
    minimum_role: str,
) -> None:
    material = await _get_material(db, prop.material_id)
    await ensure_material_access(db, current_user, material, minimum_role)


@router.get("", response_model=PaginatedResponse[PropertyResponse])
async def list_properties(
    pagination: PaginationParams = Depends(),
    material_id: uuid.UUID | None = None,
    property_type: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("property:read")),
):
    """List properties attached to materials visible to the current user."""
    query = select(Property)
    if material_id is not None:
        material = await _get_material(db, material_id)
        await ensure_material_access(db, current_user, material, "viewer")
        query = query.where(Property.material_id == material_id)
    else:
        query = query.join(Material).where(
            material_visibility_condition(current_user)
        )
    if property_type:
        query = query.where(Property.property_type == property_type)

    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0
    offset = (pagination.page - 1) * pagination.size
    result = await db.execute(
        query.order_by(Property.created_at.desc()).offset(offset).limit(pagination.size)
    )

    return PaginatedResponse(
        items=result.scalars().all(),
        total=total,
        page=pagination.page,
        size=pagination.size,
        pages=(total + pagination.size - 1) // pagination.size if total else 0,
    )


@router.get("/names")
async def list_property_names(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("property:read")),
):
    """Return property names used by visible materials."""
    result = await db.execute(
        select(distinct(Property.property_name))
        .join(Material)
        .where(material_visibility_condition(current_user))
        .order_by(Property.property_name)
    )
    return {"names": [row[0] for row in result.all()]}


@router.get("/compare", response_model=PropertyComparisonResponse)
async def compare_properties(
    material_ids: list[uuid.UUID] = Query(..., min_length=2, max_length=12),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("property:read")),
):
    """Return the latest numeric value per material, property name, and unit."""
    unique_ids = list(dict.fromkeys(material_ids))
    if len(unique_ids) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Select at least two different materials",
        )

    material_rows = (
        await db.execute(
            select(Material).where(
                Material.id.in_(unique_ids),
                material_visibility_condition(current_user),
            )
        )
    ).scalars().all()
    material_by_id = {material.id: material for material in material_rows}
    if len(material_by_id) != len(unique_ids):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="One or more materials were not found",
        )

    partition = (
        Property.material_id,
        Property.property_name,
        func.coalesce(Property.unit, ""),
    )
    ranked = (
        select(
            Property.id.label("id"),
            Property.material_id.label("material_id"),
            Property.sample_id.label("sample_id"),
            Property.property_type.label("property_type"),
            Property.property_name.label("property_name"),
            Property.value_number.label("value_number"),
            Property.uncertainty.label("uncertainty"),
            Property.unit.label("unit"),
            Property.conditions.label("conditions"),
            Property.test_method.label("test_method"),
            Property.created_at.label("created_at"),
            func.count().over(partition_by=partition).label("measurement_count"),
            func.row_number()
            .over(
                partition_by=partition,
                order_by=(Property.created_at.desc(), Property.id.desc()),
            )
            .label("row_number"),
        )
        .join(Material, Material.id == Property.material_id)
        .where(
            Property.material_id.in_(unique_ids),
            Property.value_number.is_not(None),
            material_visibility_condition(current_user),
        )
        .subquery()
    )
    measurement_rows = (
        await db.execute(
            select(ranked)
            .where(ranked.c.row_number == 1)
            .order_by(ranked.c.property_name, ranked.c.unit, ranked.c.material_id)
        )
    ).mappings().all()

    return {
        "materials": [
            {
                "id": material.id,
                "name": material.name,
                "material_type": material.material_type,
                "project_id": material.project_id,
            }
            for material_id in unique_ids
            for material in [material_by_id[material_id]]
        ],
        "measurements": [
            {key: value for key, value in row.items() if key != "row_number"}
            for row in measurement_rows
        ],
    }


@router.get("/sample-compare", response_model=SamplePropertyComparisonResponse)
async def compare_sample_properties(
    sample_ids: list[uuid.UUID] = Query(..., min_length=2, max_length=12),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("property:read")),
):
    """Return the latest numeric value per sample, property name, and unit."""
    unique_ids = list(dict.fromkeys(sample_ids))
    if len(unique_ids) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Select at least two different samples",
        )

    is_admin = current_user.role is not None and current_user.role.name == "admin"
    sample_visible = true() if is_admin else or_(
        and_(
            Sample.experiment_id.is_(None),
            Sample.created_by == current_user.id,
        ),
        exists().where(
            ProjectMember.project_id == Experiment.project_id,
            ProjectMember.user_id == current_user.id,
        ),
    )
    sample_rows = (
        await db.execute(
            select(
                Sample,
                Experiment.project_id.label("project_id"),
                Material.name.label("material_name"),
            )
            .outerjoin(Experiment, Experiment.id == Sample.experiment_id)
            .outerjoin(Material, Material.id == Sample.material_id)
            .where(Sample.id.in_(unique_ids), sample_visible)
        )
    ).all()
    sample_by_id = {
        sample.id: (sample, project_id, material_name)
        for sample, project_id, material_name in sample_rows
    }
    if len(sample_by_id) != len(unique_ids):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="One or more samples were not found",
        )

    partition = (
        Property.sample_id,
        Property.property_name,
        func.coalesce(Property.unit, ""),
    )
    ranked = (
        select(
            Property.id.label("id"),
            Property.material_id.label("material_id"),
            Property.sample_id.label("sample_id"),
            Property.property_type.label("property_type"),
            Property.property_name.label("property_name"),
            Property.value_number.label("value_number"),
            Property.uncertainty.label("uncertainty"),
            Property.unit.label("unit"),
            Property.conditions.label("conditions"),
            Property.test_method.label("test_method"),
            Property.created_at.label("created_at"),
            func.count().over(partition_by=partition).label("measurement_count"),
            func.row_number()
            .over(
                partition_by=partition,
                order_by=(Property.created_at.desc(), Property.id.desc()),
            )
            .label("row_number"),
        )
        .join(Sample, Sample.id == Property.sample_id)
        .outerjoin(Experiment, Experiment.id == Sample.experiment_id)
        .where(
            Property.sample_id.in_(unique_ids),
            Property.value_number.is_not(None),
            sample_visible,
        )
        .subquery()
    )
    measurement_rows = (
        await db.execute(
            select(ranked)
            .where(ranked.c.row_number == 1)
            .order_by(ranked.c.property_name, ranked.c.unit, ranked.c.sample_id)
        )
    ).mappings().all()

    return {
        "samples": [
            {
                "id": sample.id,
                "sample_code": sample.sample_code,
                "batch_number": sample.batch_number,
                "material_id": sample.material_id,
                "material_name": material_name,
                "experiment_id": sample.experiment_id,
                "project_id": project_id,
                "form": sample.form,
                "status": sample.status,
            }
            for sample_id in unique_ids
            for sample, project_id, material_name in [sample_by_id[sample_id]]
        ],
        "measurements": [
            {key: value for key, value in row.items() if key != "row_number"}
            for row in measurement_rows
        ],
    }


@router.post("", response_model=PropertyResponse, status_code=status.HTTP_201_CREATED)
async def create_property(
    body: PropertyCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("property:create")),
):
    material = await _get_material(db, body.material_id)
    await ensure_material_access(db, current_user, material, "editor")

    prop = Property(
        **body.model_dump(exclude={"metadata_"}),
        metadata_=body.metadata_,
        created_by=current_user.id,
    )
    db.add(prop)
    await db.flush()
    await db.refresh(prop)
    return prop


@router.get("/{property_id}", response_model=PropertyResponse)
async def get_property(
    property_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("property:read")),
):
    prop = await _get_property(db, property_id)
    await _ensure_property_access(db, current_user, prop, "viewer")
    return prop


@router.put("/{property_id}", response_model=PropertyResponse)
async def update_property(
    property_id: uuid.UUID,
    body: PropertyUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("property:update")),
):
    prop = await _get_property(db, property_id)
    await _ensure_property_access(db, current_user, prop, "editor")

    update_data = body.model_dump(exclude_unset=True, exclude={"metadata_"})
    if body.metadata_ is not None:
        prop.metadata_ = body.metadata_
    for field, value in update_data.items():
        setattr(prop, field, value)

    await db.flush()
    await db.refresh(prop)
    return prop


@router.delete("/{property_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_property(
    property_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("property:delete")),
):
    prop = await _get_property(db, property_id)
    await _ensure_property_access(db, current_user, prop, "owner")
    await db.delete(prop)


@router.post("/bulk", response_model=list[PropertyResponse], status_code=status.HTTP_201_CREATED)
async def bulk_create_properties(
    body: PropertyBulkCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("property:create")),
):
    """Bulk-create properties after authorizing every referenced material."""
    authorized_material_ids: set[uuid.UUID] = set()
    for prop_data in body.properties:
        if prop_data.material_id in authorized_material_ids:
            continue
        material = await _get_material(db, prop_data.material_id)
        await ensure_material_access(db, current_user, material, "editor")
        authorized_material_ids.add(prop_data.material_id)

    created: list[Property] = []
    for prop_data in body.properties:
        prop = Property(
            **prop_data.model_dump(exclude={"metadata_"}),
            metadata_=prop_data.metadata_,
            created_by=current_user.id,
        )
        db.add(prop)
        created.append(prop)
    await db.flush()
    for prop in created:
        await db.refresh(prop)
    return created
