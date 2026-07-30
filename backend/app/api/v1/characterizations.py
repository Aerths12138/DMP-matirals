"""Project-aware characterization CRUD endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import ensure_sample_access, get_db, require_permission
from app.models.characterization import Characterization
from app.models.sample import Sample
from app.models.user import User
from app.schemas.characterization import (
    CharacterizationCreate,
    CharacterizationResponse,
    CharacterizationUpdate,
)
from app.schemas.common import PaginatedResponse, PaginationParams
from app.services.metadata_validation import get_metadata_template, validate_metadata

router = APIRouter(prefix="/characterizations", tags=["Characterizations"])


async def _get_sample(db: AsyncSession, sample_id: uuid.UUID) -> Sample:
    sample = await db.get(Sample, sample_id)
    if sample is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sample not found")
    return sample


async def _get_characterization(
    db: AsyncSession,
    characterization_id: uuid.UUID,
) -> Characterization:
    characterization = await db.get(Characterization, characterization_id)
    if characterization is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Characterization not found",
        )
    return characterization


async def ensure_characterization_access(
    db: AsyncSession,
    current_user: User,
    characterization: Characterization,
    minimum_role: str,
) -> uuid.UUID | None:
    sample = await _get_sample(db, characterization.sample_id)
    return await ensure_sample_access(db, current_user, sample, minimum_role)


@router.get("", response_model=PaginatedResponse[CharacterizationResponse])
async def list_characterizations(
    sample_id: uuid.UUID,
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("characterization:read")),
):
    sample = await _get_sample(db, sample_id)
    await ensure_sample_access(db, current_user, sample, "viewer")

    target_filter = Characterization.sample_id == sample_id
    total = (
        await db.execute(select(func.count(Characterization.id)).where(target_filter))
    ).scalar() or 0
    offset = (pagination.page - 1) * pagination.size
    result = await db.execute(
        select(Characterization)
        .where(target_filter)
        .order_by(Characterization.created_at.desc())
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


@router.post("", response_model=CharacterizationResponse, status_code=status.HTTP_201_CREATED)
async def create_characterization(
    body: CharacterizationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("characterization:create")),
):
    sample = await _get_sample(db, body.sample_id)
    project_id = await ensure_sample_access(db, current_user, sample, "editor")
    if body.metadata_template_id is not None:
        if project_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Standalone samples cannot use project metadata templates",
            )
        template = await get_metadata_template(db, body.metadata_template_id, project_id, "characterization")
        validate_metadata(template, body.metadata_)
    technique = body.technique.strip()
    if not technique:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Technique cannot be empty",
        )

    data = body.model_dump(exclude={"metadata_"})
    data["technique"] = technique
    characterization = Characterization(
        **data,
        metadata_=body.metadata_,
        operator_id=current_user.id,
        created_by=current_user.id,
    )
    db.add(characterization)
    await db.flush()
    await db.refresh(characterization)
    return characterization


@router.get("/{characterization_id}", response_model=CharacterizationResponse)
async def get_characterization(
    characterization_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("characterization:read")),
):
    characterization = await _get_characterization(db, characterization_id)
    await ensure_characterization_access(db, current_user, characterization, "viewer")
    return characterization


@router.put("/{characterization_id}", response_model=CharacterizationResponse)
async def update_characterization(
    characterization_id: uuid.UUID,
    body: CharacterizationUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("characterization:update")),
):
    characterization = await _get_characterization(db, characterization_id)
    project_id = await ensure_characterization_access(db, current_user, characterization, "editor")

    update_data = body.model_dump(exclude_unset=True, exclude={"metadata_"})
    template_id = update_data.get("metadata_template_id", characterization.metadata_template_id)
    metadata = body.metadata_ if body.metadata_ is not None else characterization.metadata_
    if template_id is not None:
        if project_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Standalone samples cannot use project metadata templates",
            )
        template = await get_metadata_template(db, template_id, project_id, "characterization")
        validate_metadata(template, metadata)
    if body.metadata_ is not None:
        characterization.metadata_ = body.metadata_
    if "technique" in update_data:
        update_data["technique"] = update_data["technique"].strip()
        if not update_data["technique"]:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Technique cannot be empty",
            )
    for field, value in update_data.items():
        setattr(characterization, field, value)
    await db.flush()
    await db.refresh(characterization)
    return characterization


@router.delete("/{characterization_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_characterization(
    characterization_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("characterization:delete")),
):
    characterization = await _get_characterization(db, characterization_id)
    await ensure_characterization_access(db, current_user, characterization, "owner")
    await db.delete(characterization)
