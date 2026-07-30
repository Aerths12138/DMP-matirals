"""Immutable, versioned analysis-result endpoints."""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_permission
from app.api.v1.characterizations import (
    _get_characterization,
    ensure_characterization_access,
)
from app.models.analysis import AnalysisResult
from app.models.file import File
from app.models.user import User
from app.schemas.characterization import AnalysisResultCreate, AnalysisResultResponse
from app.schemas.common import PaginatedResponse, PaginationParams

router = APIRouter(prefix="/analysis-results", tags=["Analysis Results"])


async def _get_analysis_result(
    db: AsyncSession,
    result_id: uuid.UUID,
) -> AnalysisResult:
    analysis = await db.get(AnalysisResult, result_id)
    if analysis is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis result not found",
        )
    return analysis


async def _authorize_analysis(
    db: AsyncSession,
    current_user: User,
    analysis: AnalysisResult,
    minimum_role: str,
) -> None:
    characterization = await _get_characterization(
        db,
        analysis.characterization_id,
    )
    await ensure_characterization_access(
        db,
        current_user,
        characterization,
        minimum_role,
    )


@router.get("", response_model=PaginatedResponse[AnalysisResultResponse])
async def list_analysis_results(
    characterization_id: uuid.UUID,
    latest_only: bool = False,
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("analysis:read")),
):
    characterization = await _get_characterization(db, characterization_id)
    await ensure_characterization_access(
        db,
        current_user,
        characterization,
        "viewer",
    )

    filters = [AnalysisResult.characterization_id == characterization_id]
    if latest_only:
        filters.append(AnalysisResult.is_latest.is_(True))
    total = (
        await db.execute(select(func.count(AnalysisResult.id)).where(*filters))
    ).scalar() or 0
    offset = (pagination.page - 1) * pagination.size
    result = await db.execute(
        select(AnalysisResult)
        .where(*filters)
        .order_by(AnalysisResult.created_at.desc(), AnalysisResult.id.desc())
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


@router.post("", response_model=AnalysisResultResponse, status_code=status.HTTP_201_CREATED)
async def create_analysis_result(
    body: AnalysisResultCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("analysis:run")),
):
    characterization = await _get_characterization(db, body.characterization_id)
    await ensure_characterization_access(
        db,
        current_user,
        characterization,
        "editor",
    )
    analysis_type = body.analysis_type.strip()
    if not analysis_type:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Analysis type cannot be empty",
        )

    if body.source_file_id is not None:
        source_file = await db.get(File, body.source_file_id)
        if source_file is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Source file not found",
            )
        if (
            source_file.parent_type != "characterization"
            or source_file.parent_id != body.characterization_id
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Source file must belong to the characterization",
            )

    previous = (
        await db.execute(
            select(AnalysisResult)
            .where(
                AnalysisResult.characterization_id == body.characterization_id,
                AnalysisResult.analysis_type == analysis_type,
                AnalysisResult.is_latest.is_(True),
            )
            .order_by(AnalysisResult.created_at.desc(), AnalysisResult.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    await db.execute(
        update(AnalysisResult)
        .where(
            AnalysisResult.characterization_id == body.characterization_id,
            AnalysisResult.analysis_type == analysis_type,
            AnalysisResult.is_latest.is_(True),
        )
        .values(is_latest=False)
    )

    data = body.model_dump(exclude={"characterization_id"})
    data["analysis_type"] = analysis_type
    analysis = AnalysisResult(
        **data,
        characterization_id=body.characterization_id,
        previous_version_id=previous.id if previous else None,
        is_latest=True,
        run_by=current_user.id,
        created_at=datetime.utcnow(),
    )
    db.add(analysis)
    await db.flush()
    await db.refresh(analysis)
    return analysis


@router.get("/{result_id}", response_model=AnalysisResultResponse)
async def get_analysis_result(
    result_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("analysis:read")),
):
    analysis = await _get_analysis_result(db, result_id)
    await _authorize_analysis(db, current_user, analysis, "viewer")
    return analysis
