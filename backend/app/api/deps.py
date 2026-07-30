"""FastAPI dependencies: database session, current user, permission checks."""

import uuid
from typing import AsyncGenerator

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy import exists, or_, select, true
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.experiment import Experiment
from app.models.permission import Permission, Role
from app.models.material import Material
from app.models.project import ProjectMember
from app.models.sample import Sample
from app.models.user import User
from app.utils.security import decode_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


async def get_current_user(
    request: Request,
    token: str | None = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Extract and validate the current user from the JWT token."""
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")
        user_id: str | None = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    result = await db.execute(
        select(User).options(selectinload(User.role).selectinload(Role.permissions)).where(User.id == uuid.UUID(user_id))
    )
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")

    request.state.user_id = str(user.id)
    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    if not current_user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user")
    return current_user


def require_permission(permission_codename: str):
    """Dependency factory: require a specific permission."""

    async def _check(
        current_user: User = Depends(get_current_approved_user),
    ) -> User:
        if current_user.role is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No role assigned")

        user_permissions: set[str] = {p.codename for p in current_user.role.permissions}

        if "admin" in user_permissions or permission_codename in user_permissions:
            return current_user

        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

    return _check


async def get_current_approved_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Require that the user has been approved by an admin."""
    if not current_user.is_approved:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account pending approval. Please wait for an administrator to approve your account.",
        )
    if current_user.role is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No role assigned. Please contact an administrator.",
        )
    return current_user


def require_admin(current_user: User = Depends(get_current_approved_user)) -> User:
    """Require admin role."""
    if current_user.role is None or current_user.role.name != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user


PROJECT_ROLE_LEVELS = {"viewer": 1, "editor": 2, "owner": 3}


async def ensure_project_access(
    db: AsyncSession,
    current_user: User,
    project_id: uuid.UUID,
    minimum_role: str,
) -> None:
    """Check a user's project role after their global permission is verified."""
    if minimum_role not in PROJECT_ROLE_LEVELS:
        raise ValueError(f"Unknown project role: {minimum_role}")
    if current_user.role is not None and current_user.role.name == "admin":
        return

    result = await db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == current_user.id,
        )
    )
    membership = result.scalar_one_or_none()
    if membership is None or (
        PROJECT_ROLE_LEVELS.get(membership.role, 0)
        < PROJECT_ROLE_LEVELS[minimum_role]
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient project access",
        )


async def ensure_sample_access(
    db: AsyncSession,
    current_user: User,
    sample: Sample,
    minimum_role: str,
) -> uuid.UUID | None:
    """Authorize project samples and legacy standalone samples."""
    if sample.experiment_id is None:
        is_admin = current_user.role is not None and current_user.role.name == "admin"
        if is_admin or sample.created_by == current_user.id:
            return None
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient sample access",
        )

    experiment = await db.get(Experiment, sample.experiment_id)
    if experiment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Experiment not found",
        )
    await ensure_project_access(
        db,
        current_user,
        experiment.project_id,
        minimum_role,
    )
    return experiment.project_id


def require_project_access(permission_codename: str, minimum_role: str):
    """Require both a global permission and sufficient project membership."""
    if minimum_role not in PROJECT_ROLE_LEVELS:
        raise ValueError(f"Unknown project role: {minimum_role}")

    async def _check(
        project_id: uuid.UUID,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(require_permission(permission_codename)),
    ) -> User:
        await ensure_project_access(db, current_user, project_id, minimum_role)
        return current_user

    return _check


def material_visibility_condition(current_user: User):
    """SQL condition for materials visible to the current user."""
    if current_user.role is not None and current_user.role.name == "admin":
        return true()
    return or_(
        Material.project_id.is_(None),
        exists().where(
            ProjectMember.project_id == Material.project_id,
            ProjectMember.user_id == current_user.id,
        ),
    )


async def ensure_material_access(
    db: AsyncSession,
    current_user: User,
    material: Material,
    minimum_role: str,
) -> None:
    """Apply project membership to project-owned materials."""
    if material.project_id is None:
        return
    await ensure_project_access(
        db,
        current_user,
        material.project_id,
        minimum_role,
    )
