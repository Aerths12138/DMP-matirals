"""User management endpoints (admin only)."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy.orm import selectinload
from app.api.deps import get_current_user, get_db, require_admin, require_permission
from app.models.user import User
from app.schemas.common import PaginatedResponse, PaginationParams
from app.models.permission import Role
from app.schemas.user import (
    ApproveUserRequest,
    ChangePasswordRequest,
    ChangeRoleRequest,
    UserDirectoryItem,
    UserCreate,
    UserListResponse,
    UserResponse,
    UserUpdate,
)
from app.services import auth_service
from app.utils.security import verify_password, hash_password

router = APIRouter(prefix="/users", tags=["Users"])


def _require_self_or_admin(user_id: str, current_user: User) -> uuid.UUID:
    target_id = uuid.UUID(user_id)
    is_admin = current_user.role is not None and current_user.role.name == "admin"
    if current_user.id != target_id and not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only access your own user profile",
        )
    return target_id


@router.get("", response_model=PaginatedResponse[UserListResponse])
async def list_users(
    pagination: PaginationParams = Depends(),
    search: str | None = None,
    is_active: bool | None = None,
    is_approved: bool | None = None,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """List all users with pagination and optional filters."""
    query = select(User).options(selectinload(User.role))

    if search:
        query = query.where(
            (User.username.ilike(f"%{search}%")) | (User.email.ilike(f"%{search}%"))
        )
    if is_active is not None:
        query = query.where(User.is_active == is_active)
    if is_approved is not None:
        query = query.where(User.is_approved == is_approved)

    # Count
    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    # Paginate
    offset = (pagination.page - 1) * pagination.size
    query = query.offset(offset).limit(pagination.size).order_by(User.created_at.desc())
    result = await db.execute(query)
    users = result.scalars().all()

    return PaginatedResponse(
        items=[UserListResponse.model_validate(u) for u in users],
        total=total,
        page=pagination.page,
        size=pagination.size,
        pages=(total + pagination.size - 1) // pagination.size if total > 0 else 0,
    )


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    body: UserCreate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """Create a new user."""
    existing = (await db.execute(select(User).where(User.username == body.username))).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already exists")

    existing_email = (await db.execute(select(User).where(User.email == body.email))).scalar_one_or_none()
    if existing_email:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already exists")

    user = await auth_service.create_user(
        db,
        username=body.username,
        email=body.email,
        password=body.password,
        display_name=body.display_name,
        department=body.department,
    )
    return user


@router.get("/directory", response_model=list[UserDirectoryItem])
async def list_user_directory(
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_permission("user:read")),
):
    """List approved active users for project membership selection."""
    result = await db.execute(
        select(User)
        .where(
            User.is_active.is_(True),
            User.is_approved.is_(True),
        )
        .order_by(User.username)
    )
    return result.scalars().all()


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a single user by ID."""
    target_id = _require_self_or_admin(user_id, current_user)
    result = await db.execute(
        select(User).options(selectinload(User.role)).where(User.id == target_id)
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    body: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a user's profile."""
    target_id = _require_self_or_admin(user_id, current_user)
    result = await db.execute(
        select(User).options(selectinload(User.role)).where(User.id == target_id)
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if body.email is not None:
        user.email = body.email
    if body.display_name is not None:
        user.display_name = body.display_name
    if body.department is not None:
        user.department = body.department
    if body.is_active is not None:
        is_admin = current_user.role is not None and current_user.role.name == "admin"
        if not is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only administrators can change account status",
            )
        user.is_active = body.is_active

    await db.flush()
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """Delete a user."""
    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    await db.delete(user)


@router.patch("/{user_id}/role")
async def change_role(
    user_id: str,
    body: ChangeRoleRequest,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """Change a user's role."""
    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    user.role_id = body.role_id
    await db.flush()
    return {"message": "Role updated", "role_id": body.role_id}


@router.patch("/{user_id}/approve")
async def approve_user(
    user_id: str,
    body: ApproveUserRequest,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """Approve a registered user and assign a role."""
    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Verify role exists
    role_result = await db.execute(select(Role).where(Role.id == body.role_id))
    role = role_result.scalar_one_or_none()
    if role is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Role not found")

    user.is_approved = True
    user.role_id = body.role_id
    await db.flush()
    return {"message": "User approved", "role": role.name}


@router.get("/roles/list", response_model=list[dict])
async def list_roles(
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """List all available roles."""
    result = await db.execute(select(Role).order_by(Role.id))
    roles = result.scalars().all()
    return [{"id": r.id, "name": r.name, "description": r.description} for r in roles]


@router.post("/change-password")
async def change_password(
    body: ChangePasswordRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Change the current user's password."""
    if not verify_password(body.old_password, current_user.hashed_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Incorrect current password")
    current_user.hashed_password = hash_password(body.new_password)
    await db.flush()
    return {"message": "Password changed successfully"}
