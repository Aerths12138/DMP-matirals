"""Project-scoped experiment CRUD endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import ensure_project_access, get_db, require_permission
from app.models.experiment import Experiment
from app.models.project import Project
from app.models.user import User
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.experiment import ExperimentCreate, ExperimentResponse, ExperimentUpdate

router = APIRouter(prefix="/experiments", tags=["Experiments"])


async def _ensure_project_exists(db: AsyncSession, project_id: uuid.UUID) -> None:
    project_exists = (
        await db.execute(select(Project.id).where(Project.id == project_id))
    ).scalar_one_or_none()
    if project_exists is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )


async def _get_experiment(
    db: AsyncSession,
    experiment_id: uuid.UUID,
) -> Experiment:
    experiment = (
        await db.execute(select(Experiment).where(Experiment.id == experiment_id))
    ).scalar_one_or_none()
    if experiment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Experiment not found",
        )
    return experiment


@router.get("", response_model=PaginatedResponse[ExperimentResponse])
async def list_experiments(
    project_id: uuid.UUID,
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("experiment:read")),
):
    """List experiments in one accessible project."""
    await _ensure_project_exists(db, project_id)
    await ensure_project_access(db, current_user, project_id, "viewer")

    filters = Experiment.project_id == project_id
    total = (
        await db.execute(select(func.count(Experiment.id)).where(filters))
    ).scalar() or 0
    offset = (pagination.page - 1) * pagination.size
    result = await db.execute(
        select(Experiment)
        .where(filters)
        .order_by(Experiment.updated_at.desc())
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


@router.post("", response_model=ExperimentResponse, status_code=status.HTTP_201_CREATED)
async def create_experiment(
    body: ExperimentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("experiment:create")),
):
    """Create an experiment in a project editable by the current user."""
    await _ensure_project_exists(db, body.project_id)
    await ensure_project_access(db, current_user, body.project_id, "editor")

    name = body.name.strip()
    if not name:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Experiment name cannot be empty",
        )

    data = body.model_dump(exclude={"project_id"})
    data["name"] = name
    experiment = Experiment(
        **data,
        project_id=body.project_id,
        owner_id=current_user.id,
    )
    db.add(experiment)
    await db.flush()
    return await _get_experiment(db, experiment.id)


@router.get("/{experiment_id}", response_model=ExperimentResponse)
async def get_experiment(
    experiment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("experiment:read")),
):
    experiment = await _get_experiment(db, experiment_id)
    await ensure_project_access(db, current_user, experiment.project_id, "viewer")
    return experiment


@router.put("/{experiment_id}", response_model=ExperimentResponse)
async def update_experiment(
    experiment_id: uuid.UUID,
    body: ExperimentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("experiment:update")),
):
    experiment = await _get_experiment(db, experiment_id)
    await ensure_project_access(db, current_user, experiment.project_id, "editor")

    update_data = body.model_dump(exclude_unset=True)
    if "name" in update_data:
        update_data["name"] = update_data["name"].strip()
        if not update_data["name"]:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Experiment name cannot be empty",
            )

    for field, value in update_data.items():
        setattr(experiment, field, value)
    await db.flush()
    return await _get_experiment(db, experiment.id)


@router.delete("/{experiment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_experiment(
    experiment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("experiment:delete")),
):
    experiment = await _get_experiment(db, experiment_id)
    await ensure_project_access(db, current_user, experiment.project_id, "owner")
    await db.delete(experiment)
