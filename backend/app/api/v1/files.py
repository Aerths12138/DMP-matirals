"""File upload, listing, download, and management endpoints."""

import uuid
from urllib.parse import quote

from fastapi import APIRouter, Depends, File as FastAPIFile, HTTPException, UploadFile, status
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    ensure_material_access,
    ensure_project_access,
    get_db,
    require_permission,
)
from app.models.analysis import AnalysisResult
from app.models.characterization import Characterization
from app.models.experiment import Experiment
from app.models.file import File as FileModel
from app.models.material import Material
from app.models.sample import Sample
from app.models.user import User
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.file import FileResponse as FileResp, FileUploadResponse
from app.services.file_storage_service import get_storage_backend

router = APIRouter(prefix="/files", tags=["Files"])
storage = get_storage_backend()

VALID_PARENT_TYPES = {
    "material",
    "characterization",
    "analysis",
    "sample",
    "experiment",
}


async def _get_file(db: AsyncSession, file_id: uuid.UUID) -> FileModel:
    db_file = await db.get(FileModel, file_id)
    if db_file is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
    return db_file


async def _get_parent(db: AsyncSession, model, parent_id: uuid.UUID):
    parent = await db.get(model, parent_id)
    if parent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File parent not found",
        )
    return parent


def _parse_parent_id(parent_id: str) -> uuid.UUID:
    if not parent_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="parent_id is required",
        )
    try:
        return uuid.UUID(parent_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid parent_id",
        ) from exc


async def _ensure_sample_access(
    db: AsyncSession,
    current_user: User,
    sample: Sample,
    minimum_role: str,
) -> None:
    if sample.experiment_id is not None:
        experiment = await _get_parent(db, Experiment, sample.experiment_id)
        await ensure_project_access(
            db,
            current_user,
            experiment.project_id,
            minimum_role,
        )
        return

    is_admin = current_user.role is not None and current_user.role.name == "admin"
    if not is_admin and sample.created_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient sample access",
        )


async def _ensure_parent_access(
    db: AsyncSession,
    current_user: User,
    parent_type: str,
    parent_id: uuid.UUID,
    minimum_role: str,
) -> None:
    """Authorize a file through its material or project-scoped parent chain."""
    if parent_type == "material":
        material = await _get_parent(db, Material, parent_id)
        await ensure_material_access(db, current_user, material, minimum_role)
        return

    if parent_type == "experiment":
        experiment = await _get_parent(db, Experiment, parent_id)
        await ensure_project_access(
            db,
            current_user,
            experiment.project_id,
            minimum_role,
        )
        return

    if parent_type == "sample":
        sample = await _get_parent(db, Sample, parent_id)
        await _ensure_sample_access(db, current_user, sample, minimum_role)
        return

    if parent_type == "characterization":
        characterization = await _get_parent(db, Characterization, parent_id)
        sample = await _get_parent(db, Sample, characterization.sample_id)
        await _ensure_sample_access(db, current_user, sample, minimum_role)
        return

    if parent_type == "analysis":
        analysis = await _get_parent(db, AnalysisResult, parent_id)
        characterization = await _get_parent(
            db,
            Characterization,
            analysis.characterization_id,
        )
        sample = await _get_parent(db, Sample, characterization.sample_id)
        await _ensure_sample_access(db, current_user, sample, minimum_role)
        return

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"Invalid parent_type: {parent_type}",
    )


@router.get("", response_model=PaginatedResponse[FileResp])
async def list_files(
    parent_type: str,
    parent_id: str,
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("file:read")),
):
    """List attachments after authorizing their parent entity."""
    if parent_type not in VALID_PARENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid parent_type: {parent_type}",
        )
    parent_uuid = _parse_parent_id(parent_id)
    await _ensure_parent_access(db, current_user, parent_type, parent_uuid, "viewer")

    filters = [
        FileModel.parent_type == parent_type,
        FileModel.parent_id == parent_uuid,
    ]
    total = (
        await db.execute(select(func.count(FileModel.id)).where(*filters))
    ).scalar() or 0
    offset = (pagination.page - 1) * pagination.size
    result = await db.execute(
        select(FileModel)
        .where(*filters)
        .order_by(FileModel.created_at.desc(), FileModel.id.desc())
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


@router.post("/upload", response_model=FileUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_file(
    file: UploadFile = FastAPIFile(...),
    parent_type: str = "material",
    parent_id: str = "",
    file_type: str = "other",
    description: str = "",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("file:upload")),
):
    """Upload a file after authorizing its existing parent entity."""
    if parent_type not in VALID_PARENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid parent_type: {parent_type}",
        )
    parent_uuid = _parse_parent_id(parent_id)
    await _ensure_parent_access(db, current_user, parent_type, parent_uuid, "editor")

    original_name = (file.filename or "unknown").replace("\\", "/").rsplit("/", 1)[-1]
    original_name = original_name or "unknown"
    stored_file = await storage.upload(
        file,
        f"{parent_type}/{parent_uuid}/{uuid.uuid4().hex}_{original_name}",
    )

    duplicate = (
        await db.execute(
            select(FileModel.id).where(
                FileModel.parent_type == parent_type,
                FileModel.parent_id == parent_uuid,
                FileModel.checksum_sha256 == stored_file.checksum_sha256,
            )
        )
    ).scalar_one_or_none()
    if duplicate is not None:
        await storage.delete(stored_file.path)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"The same file is already attached: {duplicate}",
        )

    db_file = FileModel(
        parent_type=parent_type,
        parent_id=parent_uuid,
        original_name=original_name,
        stored_path=stored_file.path,
        storage_backend=storage.name,
        mime_type=file.content_type,
        file_size_bytes=stored_file.size_bytes,
        checksum_sha256=stored_file.checksum_sha256,
        file_type=file_type,
        description=description.strip() or None,
        uploaded_by=current_user.id,
    )
    db.add(db_file)
    await db.flush()
    await db.refresh(db_file)

    return FileUploadResponse(
        id=db_file.id,
        original_name=db_file.original_name,
        mime_type=db_file.mime_type,
        file_size_bytes=db_file.file_size_bytes,
        download_url=f"/api/v1/files/{db_file.id}/download",
    )


@router.get("/{file_id}", response_model=FileResp)
async def get_file_info(
    file_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("file:read")),
):
    """Get file metadata after authorizing its parent."""
    db_file = await _get_file(db, file_id)
    await _ensure_parent_access(
        db,
        current_user,
        db_file.parent_type,
        db_file.parent_id,
        "viewer",
    )
    return db_file


@router.get("/{file_id}/download")
async def download_file(
    file_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("file:read")),
):
    """Download file content after authorizing its parent."""
    db_file = await _get_file(db, file_id)
    await _ensure_parent_access(
        db,
        current_user,
        db_file.parent_type,
        db_file.parent_id,
        "viewer",
    )

    try:
        content = await storage.download(db_file.stored_path)
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found in storage",
        ) from None
    encoded_name = quote(db_file.original_name)
    return Response(
        content=content,
        media_type=db_file.mime_type or "application/octet-stream",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_name}",
            "Cache-Control": "private, no-store",
        },
    )


@router.delete("/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_file(
    file_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("file:upload")),
):
    """Delete an attachment as a parent editor or owner."""
    db_file = await _get_file(db, file_id)
    await _ensure_parent_access(
        db,
        current_user,
        db_file.parent_type,
        db_file.parent_id,
        "editor",
    )
    await storage.delete(db_file.stored_path)
    await db.delete(db_file)
