"""Permission-aware global search across core research entities."""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import String, Uuid, and_, cast, exists, func, literal, or_, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import ensure_project_access, get_db, require_permission
from app.models.analysis import AnalysisResult
from app.models.characterization import Characterization
from app.models.experiment import Experiment
from app.models.file import File
from app.models.material import Material
from app.models.project import Project, ProjectMember
from app.models.sample import Sample
from app.models.user import User
from app.schemas.common import PaginatedResponse

router = APIRouter(prefix="/search", tags=["Search"])

SEARCH_ENTITY_TYPES = {
    "project",
    "material",
    "experiment",
    "sample",
    "characterization",
    "file",
}


class SearchResult(BaseModel):
    id: uuid.UUID
    entity_type: str
    title: str
    subtitle: str | None = None
    project_id: uuid.UUID | None = None
    parent_type: str | None = None
    parent_id: uuid.UUID | None = None
    updated_at: datetime


def _null_uuid():
    return cast(literal(None), Uuid)


def _null_text(length: int = 36):
    return cast(literal(None), String(length))


def _project_visible(current_user: User, project_id_column):
    if current_user.role is not None and current_user.role.name == "admin":
        return literal(True)
    return exists().where(
        ProjectMember.project_id == project_id_column,
        ProjectMember.user_id == current_user.id,
    )


def _sample_visible(current_user: User, project_id_column):
    if current_user.role is not None and current_user.role.name == "admin":
        return literal(True)
    return or_(
        and_(
            Sample.experiment_id.is_(None),
            Sample.created_by == current_user.id,
        ),
        _project_visible(current_user, project_id_column),
    )


def _select_result(
    *,
    id_column,
    entity_type: str,
    title_column,
    subtitle_column,
    project_id_column,
    updated_at_column,
    parent_type_column=None,
    parent_id_column=None,
):
    return select(
        id_column.label("id"),
        literal(entity_type).label("entity_type"),
        title_column.label("title"),
        subtitle_column.label("subtitle"),
        (
            project_id_column
            if project_id_column is not None
            else _null_uuid()
        ).label("project_id"),
        (
            parent_type_column
            if parent_type_column is not None
            else _null_text(50)
        ).label("parent_type"),
        (
            parent_id_column
            if parent_id_column is not None
            else _null_uuid()
        ).label("parent_id"),
        updated_at_column.label("updated_at"),
    )


@router.get("", response_model=PaginatedResponse[SearchResult])
async def global_search(
    q: str = Query(min_length=1, max_length=200),
    entity_type: str | None = None,
    project_id: uuid.UUID | None = None,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("material:read")),
):
    """Search visible projects, materials, experiments, samples, characterizations, and files."""
    term = q.strip()
    if not term:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Search term cannot be empty",
        )
    if entity_type is not None and entity_type not in SEARCH_ENTITY_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid search entity type",
        )
    if project_id is not None:
        project = await db.get(Project, project_id)
        if project is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
        await ensure_project_access(db, current_user, project_id, "viewer")

    pattern = f"%{term}%"
    requested_types = {entity_type} if entity_type else SEARCH_ENTITY_TYPES
    branches = []

    if "project" in requested_types:
        query = _select_result(
            id_column=Project.id,
            entity_type="project",
            title_column=Project.name,
            subtitle_column=Project.description,
            project_id_column=Project.id,
            updated_at_column=Project.updated_at,
        ).where(
            _project_visible(current_user, Project.id),
            or_(Project.name.ilike(pattern), Project.description.ilike(pattern)),
        )
        if project_id is not None:
            query = query.where(Project.id == project_id)
        branches.append(query)

    if "material" in requested_types:
        material_visible = or_(
            Material.project_id.is_(None),
            _project_visible(current_user, Material.project_id),
        )
        query = _select_result(
            id_column=Material.id,
            entity_type="material",
            title_column=Material.name,
            subtitle_column=func.coalesce(Material.formula_string, Material.description),
            project_id_column=Material.project_id,
            updated_at_column=Material.updated_at,
        ).where(
            material_visible,
            or_(
                Material.name.ilike(pattern),
                Material.formula_string.ilike(pattern),
                Material.description.ilike(pattern),
            ),
        )
        if project_id is not None:
            query = query.where(Material.project_id == project_id)
        branches.append(query)

    if "experiment" in requested_types:
        query = _select_result(
            id_column=Experiment.id,
            entity_type="experiment",
            title_column=Experiment.name,
            subtitle_column=func.coalesce(Experiment.description, Experiment.hypothesis),
            project_id_column=Experiment.project_id,
            updated_at_column=Experiment.updated_at,
        ).where(
            _project_visible(current_user, Experiment.project_id),
            or_(
                Experiment.name.ilike(pattern),
                Experiment.description.ilike(pattern),
                Experiment.hypothesis.ilike(pattern),
            ),
        )
        if project_id is not None:
            query = query.where(Experiment.project_id == project_id)
        branches.append(query)

    if "sample" in requested_types:
        query = (
            _select_result(
                id_column=Sample.id,
                entity_type="sample",
                title_column=Sample.sample_code,
                subtitle_column=func.coalesce(Sample.description, Sample.batch_number),
                project_id_column=Experiment.project_id,
                updated_at_column=Sample.updated_at,
            )
            .select_from(Sample)
            .outerjoin(Experiment, Sample.experiment_id == Experiment.id)
            .where(
                _sample_visible(current_user, Experiment.project_id),
                or_(
                    Sample.sample_code.ilike(pattern),
                    Sample.batch_number.ilike(pattern),
                    Sample.description.ilike(pattern),
                    Sample.storage_location.ilike(pattern),
                ),
            )
        )
        if project_id is not None:
            query = query.where(Experiment.project_id == project_id)
        branches.append(query)

    if "characterization" in requested_types:
        query = (
            _select_result(
                id_column=Characterization.id,
                entity_type="characterization",
                title_column=func.coalesce(Characterization.title, Characterization.technique),
                subtitle_column=func.coalesce(Characterization.instrument, Characterization.technique),
                project_id_column=Experiment.project_id,
                updated_at_column=Characterization.updated_at,
            )
            .select_from(Characterization)
            .join(Sample, Characterization.sample_id == Sample.id)
            .outerjoin(Experiment, Sample.experiment_id == Experiment.id)
            .where(
                _sample_visible(current_user, Experiment.project_id),
                or_(
                    Characterization.technique.ilike(pattern),
                    Characterization.title.ilike(pattern),
                    Characterization.description.ilike(pattern),
                    Characterization.instrument.ilike(pattern),
                ),
            )
        )
        if project_id is not None:
            query = query.where(Experiment.project_id == project_id)
        branches.append(query)

    if "file" in requested_types:
        file_text_filter = or_(
            File.original_name.ilike(pattern),
            File.description.ilike(pattern),
            File.file_type.ilike(pattern),
        )

        material_file = (
            _select_result(
                id_column=File.id,
                entity_type="file",
                title_column=File.original_name,
                subtitle_column=func.coalesce(File.description, File.file_type),
                project_id_column=Material.project_id,
                parent_type_column=File.parent_type,
                parent_id_column=File.parent_id,
                updated_at_column=File.created_at,
            )
            .select_from(File)
            .join(
                Material,
                and_(File.parent_type == "material", File.parent_id == Material.id),
            )
            .where(
                or_(
                    Material.project_id.is_(None),
                    _project_visible(current_user, Material.project_id),
                ),
                file_text_filter,
            )
        )
        if project_id is not None:
            material_file = material_file.where(Material.project_id == project_id)
        branches.append(material_file)

        experiment_file = (
            _select_result(
                id_column=File.id,
                entity_type="file",
                title_column=File.original_name,
                subtitle_column=func.coalesce(File.description, File.file_type),
                project_id_column=Experiment.project_id,
                parent_type_column=File.parent_type,
                parent_id_column=File.parent_id,
                updated_at_column=File.created_at,
            )
            .select_from(File)
            .join(
                Experiment,
                and_(File.parent_type == "experiment", File.parent_id == Experiment.id),
            )
            .where(
                _project_visible(current_user, Experiment.project_id),
                file_text_filter,
            )
        )
        if project_id is not None:
            experiment_file = experiment_file.where(Experiment.project_id == project_id)
        branches.append(experiment_file)

        sample_file = (
            _select_result(
                id_column=File.id,
                entity_type="file",
                title_column=File.original_name,
                subtitle_column=func.coalesce(File.description, File.file_type),
                project_id_column=Experiment.project_id,
                parent_type_column=File.parent_type,
                parent_id_column=File.parent_id,
                updated_at_column=File.created_at,
            )
            .select_from(File)
            .join(Sample, and_(File.parent_type == "sample", File.parent_id == Sample.id))
            .outerjoin(Experiment, Sample.experiment_id == Experiment.id)
            .where(_sample_visible(current_user, Experiment.project_id), file_text_filter)
        )
        if project_id is not None:
            sample_file = sample_file.where(Experiment.project_id == project_id)
        branches.append(sample_file)

        characterization_file = (
            _select_result(
                id_column=File.id,
                entity_type="file",
                title_column=File.original_name,
                subtitle_column=func.coalesce(File.description, File.file_type),
                project_id_column=Experiment.project_id,
                parent_type_column=File.parent_type,
                parent_id_column=File.parent_id,
                updated_at_column=File.created_at,
            )
            .select_from(File)
            .join(
                Characterization,
                and_(
                    File.parent_type == "characterization",
                    File.parent_id == Characterization.id,
                ),
            )
            .join(Sample, Characterization.sample_id == Sample.id)
            .outerjoin(Experiment, Sample.experiment_id == Experiment.id)
            .where(_sample_visible(current_user, Experiment.project_id), file_text_filter)
        )
        if project_id is not None:
            characterization_file = characterization_file.where(Experiment.project_id == project_id)
        branches.append(characterization_file)

        analysis_file = (
            _select_result(
                id_column=File.id,
                entity_type="file",
                title_column=File.original_name,
                subtitle_column=func.coalesce(File.description, File.file_type),
                project_id_column=Experiment.project_id,
                parent_type_column=File.parent_type,
                parent_id_column=File.parent_id,
                updated_at_column=File.created_at,
            )
            .select_from(File)
            .join(
                AnalysisResult,
                and_(File.parent_type == "analysis", File.parent_id == AnalysisResult.id),
            )
            .join(Characterization, AnalysisResult.characterization_id == Characterization.id)
            .join(Sample, Characterization.sample_id == Sample.id)
            .outerjoin(Experiment, Sample.experiment_id == Experiment.id)
            .where(_sample_visible(current_user, Experiment.project_id), file_text_filter)
        )
        if project_id is not None:
            analysis_file = analysis_file.where(Experiment.project_id == project_id)
        branches.append(analysis_file)

    combined = union_all(*branches).subquery("global_search_results")
    total = (await db.execute(select(func.count()).select_from(combined))).scalar() or 0
    offset = (page - 1) * size
    rows = (
        await db.execute(
            select(combined)
            .order_by(combined.c.updated_at.desc(), combined.c.title.asc())
            .offset(offset)
            .limit(size)
        )
    ).mappings().all()

    return PaginatedResponse(
        items=[SearchResult(**row) for row in rows],
        total=total,
        page=page,
        size=size,
        pages=(total + size - 1) // size if total else 0,
    )
