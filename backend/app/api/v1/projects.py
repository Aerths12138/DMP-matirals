"""Project CRUD and membership endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_db, require_permission, require_project_access
from app.models.project import Project, ProjectMember
from app.models.user import User
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.experiment import (
    ProjectCreate,
    ProjectMemberCreate,
    ProjectMemberResponse,
    ProjectMemberUpdate,
    ProjectResponse,
    ProjectUpdate,
)

router = APIRouter(prefix="/projects", tags=["Projects"])


def _project_query():
    return select(Project).options(
        selectinload(Project.owner),
        selectinload(Project.members).selectinload(ProjectMember.user),
    )


async def _get_project(db: AsyncSession, project_id: uuid.UUID) -> Project:
    result = await db.execute(_project_query().where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )
    return project


async def _get_member(
    db: AsyncSession,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
) -> ProjectMember:
    result = await db.execute(
        select(ProjectMember)
        .options(selectinload(ProjectMember.user))
        .where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id,
        )
    )
    membership = result.scalar_one_or_none()
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project member not found",
        )
    return membership


@router.get("", response_model=PaginatedResponse[ProjectResponse])
async def list_projects(
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("experiment:read")),
):
    """List projects visible to the current user."""
    query = _project_query()
    count_query = select(func.count(Project.id))
    is_admin = current_user.role is not None and current_user.role.name == "admin"

    if not is_admin:
        query = query.join(ProjectMember).where(
            ProjectMember.user_id == current_user.id
        )
        count_query = count_query.join(ProjectMember).where(
            ProjectMember.user_id == current_user.id
        )

    total = (await db.execute(count_query)).scalar() or 0
    offset = (pagination.page - 1) * pagination.size
    result = await db.execute(
        query.order_by(Project.updated_at.desc()).offset(offset).limit(pagination.size)
    )
    projects = result.scalars().all()

    return PaginatedResponse(
        items=projects,
        total=total,
        page=pagination.page,
        size=pagination.size,
        pages=(total + pagination.size - 1) // pagination.size if total else 0,
    )


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    body: ProjectCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("experiment:create")),
):
    """Create a private project and make the creator its owner."""
    name = body.name.strip()
    if not name:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Project name cannot be empty",
        )

    data = body.model_dump()
    data["name"] = name
    project = Project(**data, owner_id=current_user.id)
    db.add(project)
    await db.flush()

    db.add(
        ProjectMember(
            project_id=project.id,
            user_id=current_user.id,
            role="owner",
        )
    )
    await db.flush()
    return await _get_project(db, project.id)


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(
        require_project_access("experiment:read", "viewer")
    ),
):
    """Get one project visible to the current member."""
    return await _get_project(db, project_id)


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: uuid.UUID,
    body: ProjectUpdate,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(
        require_project_access("experiment:update", "editor")
    ),
):
    """Update a project as an editor or owner."""
    project = await _get_project(db, project_id)
    update_data = body.model_dump(exclude_unset=True)
    if "name" in update_data:
        update_data["name"] = update_data["name"].strip()
        if not update_data["name"]:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Project name cannot be empty",
            )

    for field, value in update_data.items():
        setattr(project, field, value)

    await db.flush()
    return await _get_project(db, project.id)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(
        require_project_access("experiment:delete", "owner")
    ),
):
    """Delete a project as an owner with delete permission."""
    project = await _get_project(db, project_id)
    await db.delete(project)


@router.post(
    "/{project_id}/members",
    response_model=ProjectMemberResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_project_member(
    project_id: uuid.UUID,
    body: ProjectMemberCreate,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(
        require_project_access("experiment:update", "owner")
    ),
):
    """Add an approved user to a project."""
    await _get_project(db, project_id)
    user = (
        await db.execute(
            select(User).where(
                User.id == body.user_id,
                User.is_active.is_(True),
                User.is_approved.is_(True),
            )
        )
    ).scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Approved user not found",
        )

    existing = (
        await db.execute(
            select(ProjectMember).where(
                ProjectMember.project_id == project_id,
                ProjectMember.user_id == body.user_id,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User is already a project member",
        )

    membership = ProjectMember(
        project_id=project_id,
        user_id=body.user_id,
        role=body.role,
    )
    db.add(membership)
    await db.flush()
    return await _get_member(db, project_id, body.user_id)


@router.put(
    "/{project_id}/members/{user_id}",
    response_model=ProjectMemberResponse,
)
async def update_project_member(
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    body: ProjectMemberUpdate,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(
        require_project_access("experiment:update", "owner")
    ),
):
    """Change a non-owner project member's role."""
    membership = await _get_member(db, project_id, user_id)
    if membership.role == "owner":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The project owner role cannot be changed",
        )
    membership.role = body.role
    await db.flush()
    return await _get_member(db, project_id, user_id)


@router.delete(
    "/{project_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_project_member(
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(
        require_project_access("experiment:update", "owner")
    ),
):
    """Remove a non-owner member from a project."""
    membership = await _get_member(db, project_id, user_id)
    if membership.role == "owner":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The project owner cannot be removed",
        )
    await db.delete(membership)
