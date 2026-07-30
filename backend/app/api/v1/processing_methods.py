"""Project-aware processing-method CRUD endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    ensure_material_access,
    ensure_sample_access,
    get_db,
    require_permission,
)
from app.models.material import Material
from app.models.processing import ProcessingMethod
from app.models.sample import Sample
from app.models.user import User
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.experiment import ProcessingCreate, ProcessingResponse, ProcessingUpdate

router = APIRouter(prefix="/processing-methods", tags=["Processing Methods"])


async def _get_method(db: AsyncSession, method_id: uuid.UUID) -> ProcessingMethod:
    method = await db.get(ProcessingMethod, method_id)
    if method is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Processing method not found",
        )
    return method


async def _authorize_target(
    db: AsyncSession,
    current_user: User,
    sample_id: uuid.UUID | None,
    material_id: uuid.UUID | None,
    minimum_role: str,
) -> None:
    if (sample_id is None) == (material_id is None):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Exactly one of sample_id or material_id is required",
        )

    if sample_id is not None:
        sample = await db.get(Sample, sample_id)
        if sample is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sample not found")
        await ensure_sample_access(db, current_user, sample, minimum_role)
        return

    material = await db.get(Material, material_id)
    if material is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Material not found")
    await ensure_material_access(db, current_user, material, minimum_role)


async def _authorize_method(
    db: AsyncSession,
    current_user: User,
    method: ProcessingMethod,
    minimum_role: str,
) -> None:
    await _authorize_target(
        db,
        current_user,
        method.sample_id,
        method.material_id,
        minimum_role,
    )


@router.get("", response_model=PaginatedResponse[ProcessingResponse])
async def list_processing_methods(
    sample_id: uuid.UUID | None = None,
    material_id: uuid.UUID | None = None,
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("sample:read")),
):
    """List the ordered processing chain for one sample or material."""
    await _authorize_target(
        db,
        current_user,
        sample_id,
        material_id,
        "viewer",
    )
    target_filter = (
        ProcessingMethod.sample_id == sample_id
        if sample_id is not None
        else ProcessingMethod.material_id == material_id
    )
    total = (
        await db.execute(select(func.count(ProcessingMethod.id)).where(target_filter))
    ).scalar() or 0
    offset = (pagination.page - 1) * pagination.size
    result = await db.execute(
        select(ProcessingMethod)
        .where(target_filter)
        .order_by(
            ProcessingMethod.order_in_chain.is_(None),
            ProcessingMethod.order_in_chain.asc(),
            ProcessingMethod.created_at.asc(),
        )
        .offset(offset)
        .limit(pagination.size)
    )
    return PaginatedResponse(
        items=result.scalars().all(),
        total=total,
        page=pagination.page,
        size=pagination.size,
        pages=(total + pagination.size - 1) // pagination.size if total else 0,
    )


@router.post("", response_model=ProcessingResponse, status_code=status.HTTP_201_CREATED)
async def create_processing_method(
    body: ProcessingCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("sample:create")),
):
    await _authorize_target(
        db,
        current_user,
        body.sample_id,
        body.material_id,
        "editor",
    )
    method_type = body.method_type.strip()
    if not method_type:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Method type cannot be empty",
        )

    if body.parent_step_id is not None:
        parent = await _get_method(db, body.parent_step_id)
        if parent.sample_id != body.sample_id or parent.material_id != body.material_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Parent step belongs to a different processing chain",
            )

    data = body.model_dump()
    data["method_type"] = method_type
    method = ProcessingMethod(**data, created_by=current_user.id)
    db.add(method)
    await db.flush()
    await db.refresh(method)
    return method


@router.get("/{method_id}", response_model=ProcessingResponse)
async def get_processing_method(
    method_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("sample:read")),
):
    method = await _get_method(db, method_id)
    await _authorize_method(db, current_user, method, "viewer")
    return method


@router.put("/{method_id}", response_model=ProcessingResponse)
async def update_processing_method(
    method_id: uuid.UUID,
    body: ProcessingUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("sample:update")),
):
    method = await _get_method(db, method_id)
    await _authorize_method(db, current_user, method, "editor")
    update_data = body.model_dump(exclude_unset=True)
    if "method_type" in update_data:
        update_data["method_type"] = update_data["method_type"].strip()
        if not update_data["method_type"]:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Method type cannot be empty",
            )
    for field, value in update_data.items():
        setattr(method, field, value)
    await db.flush()
    await db.refresh(method)
    return method


@router.delete("/{method_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_processing_method(
    method_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("sample:delete")),
):
    method = await _get_method(db, method_id)
    await _authorize_method(db, current_user, method, "owner")
    await db.delete(method)
