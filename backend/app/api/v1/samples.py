"""Project-scoped sample CRUD endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import ensure_project_access, get_db, require_permission
from app.models.experiment import Experiment
from app.models.material import Material
from app.models.project import Project
from app.models.sample import Sample
from app.models.user import User
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.experiment import SampleCreate, SampleResponse, SampleUpdate
from app.services.metadata_validation import get_metadata_template, validate_metadata

router = APIRouter(prefix="/samples", tags=["Samples"])


def _sample_query():
    return select(Sample).options(selectinload(Sample.experiment))


async def _get_sample(db: AsyncSession, sample_id: uuid.UUID) -> Sample:
    sample = (
        await db.execute(_sample_query().where(Sample.id == sample_id))
    ).scalar_one_or_none()
    if sample is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sample not found",
        )
    return sample


async def _get_experiment(db: AsyncSession, experiment_id: uuid.UUID) -> Experiment:
    experiment = (
        await db.execute(select(Experiment).where(Experiment.id == experiment_id))
    ).scalar_one_or_none()
    if experiment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Experiment not found",
        )
    return experiment


async def _authorize_sample(
    db: AsyncSession,
    current_user: User,
    sample: Sample,
    minimum_role: str,
) -> uuid.UUID | None:
    """Authorize linked samples by project and legacy standalone samples by owner."""
    if sample.experiment is None:
        is_admin = current_user.role is not None and current_user.role.name == "admin"
        if is_admin or sample.created_by == current_user.id:
            return None
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient sample access",
        )

    project_id = sample.experiment.project_id
    await ensure_project_access(db, current_user, project_id, minimum_role)
    return project_id


async def _validate_material(
    db: AsyncSession,
    material_id: uuid.UUID | None,
    project_id: uuid.UUID | None,
) -> None:
    if material_id is None:
        return
    material = (
        await db.execute(select(Material).where(Material.id == material_id))
    ).scalar_one_or_none()
    if material is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Material not found",
        )
    if (
        project_id is not None
        and material.project_id is not None
        and material.project_id != project_id
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Material belongs to a different project",
        )


@router.get("", response_model=PaginatedResponse[SampleResponse])
async def list_samples(
    project_id: uuid.UUID,
    experiment_id: uuid.UUID | None = None,
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("sample:read")),
):
    """List samples linked to experiments in one accessible project."""
    project_exists = (
        await db.execute(select(Project.id).where(Project.id == project_id))
    ).scalar_one_or_none()
    if project_exists is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )
    await ensure_project_access(db, current_user, project_id, "viewer")

    filters = [Experiment.project_id == project_id]
    if experiment_id is not None:
        filters.append(Sample.experiment_id == experiment_id)

    count_query = (
        select(func.count(Sample.id))
        .join(Experiment, Sample.experiment_id == Experiment.id)
        .where(*filters)
    )
    total = (await db.execute(count_query)).scalar() or 0
    offset = (pagination.page - 1) * pagination.size
    result = await db.execute(
        _sample_query()
        .join(Experiment, Sample.experiment_id == Experiment.id)
        .where(*filters)
        .order_by(Sample.updated_at.desc())
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


@router.get("/{sample_id}", response_model=SampleResponse)
async def get_sample(
    sample_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("sample:read")),
):
    sample = await _get_sample(db, sample_id)
    await _authorize_sample(db, current_user, sample, "viewer")
    return sample


@router.post("", response_model=SampleResponse, status_code=status.HTTP_201_CREATED)
async def create_sample(
    body: SampleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("sample:create")),
):
    experiment = await _get_experiment(db, body.experiment_id)
    await ensure_project_access(db, current_user, experiment.project_id, "editor")
    await _validate_material(db, body.material_id, experiment.project_id)
    if body.metadata_template_id is not None:
        template = await get_metadata_template(
            db,
            body.metadata_template_id,
            experiment.project_id,
            "sample",
        )
        validate_metadata(template, body.metadata_)

    sample_code = body.sample_code.strip()
    if not sample_code:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Sample code cannot be empty",
        )

    data = body.model_dump(exclude={"metadata_"})
    data["sample_code"] = sample_code
    sample = Sample(
        **data,
        metadata_=body.metadata_,
        created_by=current_user.id,
    )
    db.add(sample)
    await db.flush()
    return await _get_sample(db, sample.id)


@router.put("/{sample_id}", response_model=SampleResponse)
async def update_sample(
    sample_id: uuid.UUID,
    body: SampleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("sample:update")),
):
    sample = await _get_sample(db, sample_id)
    project_id = await _authorize_sample(db, current_user, sample, "editor")
    update_data = body.model_dump(exclude_unset=True, exclude={"metadata_"})
    template_id = update_data.get("metadata_template_id", sample.metadata_template_id)
    metadata = body.metadata_ if body.metadata_ is not None else sample.metadata_
    if template_id is not None:
        if project_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Standalone samples cannot use project metadata templates",
            )
        template = await get_metadata_template(db, template_id, project_id, "sample")
        validate_metadata(template, metadata)
    if body.metadata_ is not None:
        sample.metadata_ = body.metadata_

    if "sample_code" in update_data:
        update_data["sample_code"] = update_data["sample_code"].strip()
        if not update_data["sample_code"]:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Sample code cannot be empty",
            )
    if "material_id" in update_data:
        await _validate_material(db, update_data["material_id"], project_id)

    for field, value in update_data.items():
        setattr(sample, field, value)
    await db.flush()
    return await _get_sample(db, sample.id)


@router.delete("/{sample_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_sample(
    sample_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("sample:delete")),
):
    sample = await _get_sample(db, sample_id)
    await _authorize_sample(db, current_user, sample, "owner")
    await db.delete(sample)
