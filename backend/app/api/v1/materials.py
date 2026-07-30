"""Material CRUD endpoints."""

import csv
import io
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import (
    ensure_material_access,
    ensure_project_access,
    get_db,
    material_visibility_condition,
    require_permission,
)
from app.models.material import Material
from app.models.property import Property
from app.models.test import Test, TestMeasurement
from app.models.user import User
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.material import (
    MaterialCreate,
    MaterialListResponse,
    MaterialResponse,
    MaterialUpdate,
)

VALID_MATERIAL_TYPES = {"metal", "polymer", "ceramic", "composite", "battery", "other"}


class ImportTestMeasurement(BaseModel):
    """A measurement within an imported test."""
    property_name: str
    value_number: float | None = None
    value_text: str | None = None
    unit: str | None = None


class ImportTest(BaseModel):
    """A test entry within an import row."""
    test_name: str = "导入测试"
    test_method: str | None = None
    conditions: dict[str, str] = {}
    measurements: list[ImportTestMeasurement] = []


class ImportRow(BaseModel):
    """A single import row — material base fields + dynamic properties + tests."""
    name: str = Field(max_length=500)
    material_type: str = "other"
    formula_string: str | None = None
    hill_formula: str | None = None
    aliases: str | None = None
    description: str | None = None
    properties: dict[str, float | str] = {}
    tests: list[ImportTest] = []


class ImportRequest(BaseModel):
    rows: list[ImportRow] = Field(min_length=1, max_length=500)


class ImportResult(BaseModel):
    total: int
    created: int
    failed: int
    errors: list[dict]  # [{"row": N, "message": "..."}]


router = APIRouter(prefix="/materials", tags=["Materials"])


@router.get("", response_model=PaginatedResponse[MaterialListResponse])
async def list_materials(
    pagination: PaginationParams = Depends(),
    search: str | None = None,
    material_type: str | None = None,
    project_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("material:read")),
):
    """List materials with search, filter, and pagination."""
    query = select(Material).where(
        material_visibility_condition(current_user)
    )

    if project_id is not None:
        await ensure_project_access(db, current_user, project_id, "viewer")
        query = query.where(Material.project_id == project_id)

    if search:
        query = query.where(
            or_(
                Material.name.ilike(f"%{search}%"),
                Material.formula_string.ilike(f"%{search}%"),
                Material.description.ilike(f"%{search}%"),
            )
        )
    if material_type:
        query = query.where(Material.material_type == material_type)

    # Count
    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    # Sort
    sort_col = getattr(Material, pagination.sort_by or "created_at", Material.created_at)
    if pagination.sort_order == "desc":
        query = query.order_by(sort_col.desc())
    else:
        query = query.order_by(sort_col.asc())

    # Paginate
    offset = (pagination.page - 1) * pagination.size
    query = query.offset(offset).limit(pagination.size)
    result = await db.execute(query)
    materials = result.scalars().all()

    return PaginatedResponse(
        items=[MaterialListResponse.model_validate(m) for m in materials],
        total=total,
        page=pagination.page,
        size=pagination.size,
        pages=(total + pagination.size - 1) // pagination.size if total > 0 else 0,
    )


@router.post("", response_model=MaterialResponse, status_code=status.HTTP_201_CREATED)
async def create_material(
    body: MaterialCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("material:create")),
):
    """Create a new material."""
    if body.project_id is not None:
        await ensure_project_access(db, current_user, body.project_id, "editor")

    material = Material(
        **body.model_dump(exclude={"metadata_"}),
        metadata_=body.metadata_,
        created_by=current_user.id,
    )
    db.add(material)
    await db.flush()
    result = await db.execute(
        select(Material)
        .options(selectinload(Material.tests).selectinload(Test.measurements))
        .where(Material.id == material.id)
    )
    return result.scalar_one()


@router.post("/import", response_model=ImportResult, status_code=status.HTTP_201_CREATED)
async def import_materials(
    body: ImportRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("import:create")),
):
    """Bulk import materials with dynamic properties."""
    created = 0
    failed = 0
    errors: list[dict] = []

    for i, row in enumerate(body.rows):
        try:
            # Validate required fields
            if not row.name or not row.name.strip():
                raise ValueError("材料名称不能为空")

            # Validate material_type
            material_type = row.material_type.strip().lower()
            if material_type not in VALID_MATERIAL_TYPES:
                material_type = "other"

            # Parse aliases
            aliases_list: list[str] = []
            if row.aliases:
                aliases_list = [a.strip() for a in row.aliases.split(",") if a.strip()]

            # Create material
            material = Material(
                name=row.name.strip(),
                material_type=material_type,
                formula_string=row.formula_string.strip() if row.formula_string else None,
                hill_formula=row.hill_formula.strip() if row.hill_formula else None,
                aliases=aliases_list,
                description=row.description.strip() if row.description else None,
                created_by=current_user.id,
            )
            db.add(material)
            await db.flush()  # get material.id

            # Create property rows for dynamic fields
            for prop_name, prop_value in row.properties.items():
                if prop_value is None or prop_value == "":
                    continue
                value_number: float | None = None
                value_text: str | None = None
                if isinstance(prop_value, (int, float)):
                    value_number = float(prop_value)
                else:
                    value_text = str(prop_value).strip()

                prop = Property(
                    material_id=material.id,
                    property_name=prop_name.strip(),
                    property_type="other",
                    value_number=value_number,
                    value_text=value_text,
                    created_by=current_user.id,
                )
                db.add(prop)

            # Create tests with conditions and measurements
            for t in row.tests:
                test = Test(
                    material_id=material.id,
                    test_name=t.test_name,
                    test_method=t.test_method,
                    conditions=t.conditions,
                    created_by=current_user.id,
                )
                db.add(test)
                await db.flush()

                for m in t.measurements:
                    meas = TestMeasurement(
                        test_id=test.id,
                        property_name=m.property_name,
                        value_number=m.value_number,
                        value_text=m.value_text,
                        unit=m.unit,
                    )
                    db.add(meas)

            created += 1

        except Exception as e:
            failed += 1
            errors.append({"row": i + 1, "message": str(e)})

    await db.flush()
    return ImportResult(total=len(body.rows), created=created, failed=failed, errors=errors)


@router.get("/{material_id}", response_model=MaterialResponse)
async def get_material(
    material_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("material:read")),
):
    """Get a single material with its properties and structures."""
    result = await db.execute(
        select(Material)
        .options(
            selectinload(Material.crystal_structures),
            selectinload(Material.properties),
            selectinload(Material.tests).selectinload(Test.measurements),
        )
        .where(Material.id == uuid.UUID(material_id))
    )
    material = result.scalar_one_or_none()
    if material is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Material not found")
    await ensure_material_access(db, current_user, material, "viewer")
    return material


@router.put("/{material_id}", response_model=MaterialResponse)
async def update_material(
    material_id: str,
    body: MaterialUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("material:update")),
):
    """Update a material."""
    result = await db.execute(select(Material).where(Material.id == uuid.UUID(material_id)))
    material = result.scalar_one_or_none()
    if material is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Material not found")

    await ensure_material_access(db, current_user, material, "editor")
    update_data = body.model_dump(exclude_unset=True, exclude={"metadata_"})
    if (
        "project_id" in update_data
        and update_data["project_id"] is not None
        and update_data["project_id"] != material.project_id
    ):
        await ensure_project_access(
            db,
            current_user,
            update_data["project_id"],
            "editor",
        )
    if body.metadata_ is not None:
        material.metadata_ = body.metadata_
    for field, value in update_data.items():
        setattr(material, field, value)

    await db.flush()
    result = await db.execute(
        select(Material)
        .options(selectinload(Material.tests).selectinload(Test.measurements))
        .where(Material.id == material.id)
    )
    return result.scalar_one()


@router.delete("/{material_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_material(
    material_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("material:delete")),
):
    """Delete a material and all its related data."""
    result = await db.execute(select(Material).where(Material.id == uuid.UUID(material_id)))
    material = result.scalar_one_or_none()
    if material is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Material not found")
    await ensure_material_access(db, current_user, material, "owner")
    await db.delete(material)


class BatchDeleteRequest(BaseModel):
    material_ids: list[uuid.UUID] = Field(min_length=1, max_length=200)


class BatchDeleteResult(BaseModel):
    deleted: int


@router.post("/batch-delete", response_model=BatchDeleteResult)
async def batch_delete_materials(
    body: BatchDeleteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("material:delete")),
):
    """Delete multiple materials and all their related data."""
    deleted = 0
    for mid in body.material_ids:
        result = await db.execute(select(Material).where(Material.id == mid))
        material = result.scalar_one_or_none()
        if material:
            await ensure_material_access(db, current_user, material, "owner")
            await db.delete(material)
            deleted += 1
    return BatchDeleteResult(deleted=deleted)


@router.get("/export/csv")
async def export_materials_csv(
    search: str | None = None,
    material_type: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("export:create")),
):
    """Export filtered materials as CSV."""
    query = select(Material).where(
        material_visibility_condition(current_user)
    )
    if search:
        query = query.where(
            or_(
                Material.name.ilike(f"%{search}%"),
                Material.formula_string.ilike(f"%{search}%"),
                Material.description.ilike(f"%{search}%"),
            )
        )
    if material_type:
        query = query.where(Material.material_type == material_type)

    result = await db.execute(query.order_by(Material.name))
    materials = result.scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["名称", "类型", "化学式", "Hill公式", "别名", "描述", "创建时间"])
    for m in materials:
        writer.writerow([
            m.name,
            m.material_type,
            m.formula_string or "",
            m.hill_formula or "",
            ", ".join(m.aliases or []),
            m.description or "",
            m.created_at.isoformat() if m.created_at else "",
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=materials_export.csv"},
    )
