"""Collection CRUD endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, material_visibility_condition, require_permission
from app.models.collection import Collection
from app.models.material import Material
from app.models.user import User
from app.schemas.collection import (
    AddMaterialsRequest,
    CollectionCreate,
    CollectionListResponse,
    CollectionResponse,
    CollectionUpdate,
)
from app.schemas.common import PaginatedResponse, PaginationParams

router = APIRouter(prefix="/collections", tags=["Collections"])


def _can_access(collection: Collection, user: User) -> bool:
    """Check if a user can access a collection."""
    # Public — anyone can see
    if collection.visibility == "public":
        return True
    # Private — only creator
    if collection.visibility == "private":
        return str(collection.created_by) == str(user.id)
    # Role-based — creator + users with allowed roles
    if collection.visibility == "role":
        if str(collection.created_by) == str(user.id):
            return True
        if user.role_id and user.role_id in (collection.allowed_role_ids or []):
            return True
        return False
    return False


def _can_manage(collection: Collection, user: User) -> bool:
    """Check if a user can edit/delete a collection (creator or admin)."""
    if user.role and user.role.name == "admin":
        return True
    return str(collection.created_by) == str(user.id)


async def _visible_material_ids(
    db: AsyncSession,
    current_user: User,
    material_ids: list[str],
) -> list[str]:
    """Return existing material IDs visible to the current user, preserving order."""
    parsed_ids: list[uuid.UUID] = []
    for material_id in material_ids:
        try:
            parsed_ids.append(uuid.UUID(str(material_id)))
        except ValueError:
            continue
    if not parsed_ids:
        return []

    result = await db.execute(
        select(Material.id).where(
            Material.id.in_(parsed_ids),
            material_visibility_condition(current_user),
        )
    )
    visible = {str(material_id) for material_id in result.scalars().all()}
    return [str(material_id) for material_id in material_ids if str(material_id) in visible]


async def _ensure_materials_visible(
    db: AsyncSession,
    current_user: User,
    material_ids: list[uuid.UUID],
) -> None:
    requested = [str(material_id) for material_id in material_ids]
    visible = await _visible_material_ids(db, current_user, requested)
    if len(set(visible)) != len(set(requested)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Collection contains inaccessible materials",
        )


def _collection_response(collection: Collection, material_ids: list[str]) -> CollectionResponse:
    data = CollectionResponse.model_validate(collection).model_dump()
    data["material_ids"] = material_ids
    return CollectionResponse.model_validate(data)


@router.get("", response_model=PaginatedResponse[CollectionListResponse])
async def list_collections(
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("material:read")),
):
    """List collections visible to the current user.

    Users see: public collections + their own collections + role-allowed collections.
    Admins see everything.
    """
    is_admin = current_user.role and current_user.role.name == "admin"
    user_id_str = str(current_user.id)
    user_role_id = current_user.role_id

    if is_admin:
        query = select(Collection)
    else:
        conditions = [
            Collection.visibility == "public",
            Collection.created_by == current_user.id,
        ]
        if user_role_id:
            # Visible to this user's role
            conditions.append(
                Collection.visibility == "role",
            )
        query = select(Collection).where(
            or_(
                Collection.visibility == "public",
                Collection.created_by == current_user.id,
            )
        )
        # Also include role-visible collections
        if user_role_id:
            # Use a simpler approach: fetch all and filter in Python, or use JSON contains
            pass  # handled below

    # For role visibility with JSON, we'll do post-filter since SQLite JSON queries vary
    result = await db.execute(query)
    all_collections = result.scalars().all()

    # Post-filter for role-based visibility (works across all DBs)
    if not is_admin:
        visible = []
        for c in all_collections:
            if _can_access(c, current_user):
                visible.append(c)
    else:
        visible = list(all_collections)

    total = len(visible)

    # Sort and paginate
    visible.sort(key=lambda c: c.updated_at, reverse=True)
    offset = (pagination.page - 1) * pagination.size
    page = visible[offset:offset + pagination.size]

    visible_ids_by_collection = {
        c.id: await _visible_material_ids(db, current_user, c.material_ids or [])
        for c in page
    }
    items = [
        CollectionListResponse(
            id=c.id,
            name=c.name,
            description=c.description,
            visibility=c.visibility,
            material_count=len(visible_ids_by_collection[c.id]),
            created_by=c.created_by,
            created_at=c.created_at,
        )
        for c in page
    ]

    return PaginatedResponse(
        items=items,
        total=total,
        page=pagination.page,
        size=pagination.size,
        pages=(total + pagination.size - 1) // pagination.size if total > 0 else 0,
    )


@router.get("/{collection_id}", response_model=CollectionResponse)
async def get_collection(
    collection_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("material:read")),
):
    """Get a single collection (visibility check)."""
    result = await db.execute(
        select(Collection).where(Collection.id == uuid.UUID(collection_id))
    )
    collection = result.scalar_one_or_none()
    if collection is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="子集不存在")

    if not _can_access(collection, current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问此子集")

    visible_ids = await _visible_material_ids(db, current_user, collection.material_ids or [])
    return _collection_response(collection, visible_ids)


@router.post("", response_model=CollectionResponse, status_code=status.HTTP_201_CREATED)
async def create_collection(
    body: CollectionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("material:create")),
):
    """Create a new collection."""
    await _ensure_materials_visible(db, current_user, body.material_ids)
    collection = Collection(
        name=body.name.strip(),
        description=body.description,
        material_ids=[str(mid) for mid in body.material_ids],
        visibility=body.visibility,
        allowed_role_ids=body.allowed_role_ids,
        created_by=current_user.id,
    )
    db.add(collection)
    await db.flush()
    await db.refresh(collection)
    visible_ids = await _visible_material_ids(db, current_user, collection.material_ids or [])
    return _collection_response(collection, visible_ids)


@router.put("/{collection_id}", response_model=CollectionResponse)
async def update_collection(
    collection_id: str,
    body: CollectionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("material:update")),
):
    """Update a collection (creator or admin only)."""
    result = await db.execute(
        select(Collection).where(Collection.id == uuid.UUID(collection_id))
    )
    collection = result.scalar_one_or_none()
    if collection is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="子集不存在")

    if not _can_manage(collection, current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权修改此子集")

    update_data = body.model_dump(exclude_unset=True)
    if "material_ids" in update_data and update_data["material_ids"] is not None:
        await _ensure_materials_visible(db, current_user, update_data["material_ids"])
        update_data["material_ids"] = [str(mid) for mid in update_data["material_ids"]]

    for field, value in update_data.items():
        setattr(collection, field, value)

    await db.flush()
    await db.refresh(collection)
    visible_ids = await _visible_material_ids(db, current_user, collection.material_ids or [])
    return _collection_response(collection, visible_ids)


@router.delete("/{collection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_collection(
    collection_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("material:delete")),
):
    """Delete a collection (creator or admin only)."""
    result = await db.execute(
        select(Collection).where(Collection.id == uuid.UUID(collection_id))
    )
    collection = result.scalar_one_or_none()
    if collection is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="子集不存在")

    if not _can_manage(collection, current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权删除此子集")

    await db.delete(collection)


@router.post("/{collection_id}/add-materials", response_model=CollectionResponse)
async def add_materials_to_collection(
    collection_id: str,
    body: AddMaterialsRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("material:update")),
):
    """Add materials to an existing collection (creator or admin only, deduplicates)."""
    result = await db.execute(
        select(Collection).where(Collection.id == uuid.UUID(collection_id))
    )
    collection = result.scalar_one_or_none()
    if collection is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="子集不存在")

    if not _can_manage(collection, current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权修改此子集")

    existing: set[str] = set(collection.material_ids or [])
    new_ids = [str(mid) for mid in body.material_ids if str(mid) not in existing]
    await _ensure_materials_visible(db, current_user, body.material_ids)
    collection.material_ids = list(existing) + new_ids

    await db.flush()
    await db.refresh(collection)
    visible_ids = await _visible_material_ids(db, current_user, collection.material_ids or [])
    return _collection_response(collection, visible_ids)
