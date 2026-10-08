"""Import and read ordered measurement datasets with sample-scoped access."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import ensure_sample_access, get_db, require_permission
from app.models.characterization import Characterization
from app.models.file import File
from app.models.measurement_dataset import MeasurementDataset, MeasurementPoint
from app.models.sample import Sample
from app.models.user import User
from app.schemas.measurement_dataset import (
    MeasurementDatasetCreate,
    MeasurementDatasetResponse,
    MeasurementDatasetSummary,
    MeasurementDatasetUpdate,
)

router = APIRouter(prefix="/measurement-datasets", tags=["Measurement datasets"])


async def _get_sample(db: AsyncSession, sample_id: uuid.UUID) -> Sample:
    sample = await db.get(Sample, sample_id)
    if sample is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sample not found")
    return sample


async def _get_dataset(db: AsyncSession, dataset_id: uuid.UUID) -> MeasurementDataset:
    dataset = (
        await db.execute(
            select(MeasurementDataset)
            .options(
                selectinload(MeasurementDataset.points),
                selectinload(MeasurementDataset.characterization),
            )
            .where(MeasurementDataset.id == dataset_id)
        )
    ).scalar_one_or_none()
    if dataset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Measurement dataset not found")
    return dataset


@router.post("", response_model=MeasurementDatasetResponse, status_code=status.HTTP_201_CREATED)
async def create_measurement_dataset(
    body: MeasurementDatasetCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("import:create")),
):
    """Create one characterization-backed dataset after the UI confirmation step."""
    sample = await _get_sample(db, body.sample_id)
    await ensure_sample_access(db, current_user, sample, "editor")

    name = body.name.strip()
    duplicate = (
        await db.execute(
            select(MeasurementDataset.id)
            .join(Characterization)
            .where(
                Characterization.sample_id == body.sample_id,
                MeasurementDataset.name == name,
            )
        )
    ).scalar_one_or_none()
    if duplicate is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A measurement dataset with the same name already exists for this sample",
        )

    characterization = Characterization(
        sample_id=body.sample_id,
        technique="structured_data_import",
        title=name,
        parameters={"source_filename": body.provenance.get("source_filename")},
        status="raw",
        metadata_=body.provenance,
        operator_id=current_user.id,
        created_by=current_user.id,
    )
    db.add(characterization)
    await db.flush()

    dataset = MeasurementDataset(
        characterization_id=characterization.id,
        name=name,
        x_name=body.x_name.strip(),
        x_unit=body.x_unit.strip() if body.x_unit else None,
        series_schema=[series.model_dump() for series in body.series_schema],
        provenance=body.provenance,
        row_count=len(body.points),
        created_by=current_user.id,
    )
    db.add(dataset)
    await db.flush()
    db.add_all(
        MeasurementPoint(
            dataset_id=dataset.id,
            sequence=point.sequence,
            x_value=point.x_value,
            values=point.values,
        )
        for point in body.points
    )
    await db.flush()
    return await _get_dataset(db, dataset.id)


@router.get("", response_model=list[MeasurementDatasetSummary])
async def list_measurement_datasets(
    sample_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("characterization:read")),
):
    sample = await _get_sample(db, sample_id)
    await ensure_sample_access(db, current_user, sample, "viewer")
    result = await db.execute(
        select(MeasurementDataset)
        .join(Characterization)
        .where(Characterization.sample_id == sample_id)
        .order_by(MeasurementDataset.created_at.desc(), MeasurementDataset.id.desc())
    )
    return result.scalars().all()


@router.get("/{dataset_id}", response_model=MeasurementDatasetResponse)
async def get_measurement_dataset(
    dataset_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("characterization:read")),
):
    dataset = await _get_dataset(db, dataset_id)
    sample = await _get_sample(db, dataset.characterization.sample_id)
    await ensure_sample_access(db, current_user, sample, "viewer")
    return dataset


@router.patch("/{dataset_id}", response_model=MeasurementDatasetResponse)
async def update_measurement_dataset(
    dataset_id: uuid.UUID,
    body: MeasurementDatasetUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("characterization:update")),
):
    dataset = await _get_dataset(db, dataset_id)
    sample = await _get_sample(db, dataset.characterization.sample_id)
    await ensure_sample_access(db, current_user, sample, "editor")

    changes = body.model_dump(exclude_unset=True)
    if "name" in changes:
        name = changes["name"].strip()
        duplicate = await db.scalar(
            select(MeasurementDataset.id)
            .join(Characterization)
            .where(
                Characterization.sample_id == sample.id,
                MeasurementDataset.name == name,
                MeasurementDataset.id != dataset.id,
            )
        )
        if duplicate is not None:
            raise HTTPException(status_code=409, detail="A measurement dataset with the same name already exists for this sample")
        dataset.name = name
        dataset.characterization.title = name
    if "source_file_id" in changes and changes["source_file_id"] is not None:
        source_file = await db.get(File, changes["source_file_id"])
        if source_file is None or source_file.parent_type != "characterization" or source_file.parent_id != dataset.characterization_id:
            raise HTTPException(status_code=422, detail="Source file must be attached to this dataset characterization")
        dataset.source_file_id = source_file.id
    for field in ("x_name", "x_unit", "provenance"):
        if field in changes:
            setattr(dataset, field, changes[field])
    if "series_schema" in changes:
        dataset.series_schema = [series.model_dump() for series in body.series_schema or []]
    if "points" in changes:
        dataset.points.clear()
        await db.flush()
        db.add_all(
            MeasurementPoint(dataset_id=dataset.id, sequence=point.sequence, x_value=point.x_value, values=point.values)
            for point in body.points or []
        )
        dataset.row_count = len(body.points or [])
    await db.flush()
    return await _get_dataset(db, dataset.id)


@router.delete("/{dataset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_measurement_dataset(
    dataset_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("characterization:delete")),
):
    dataset = await _get_dataset(db, dataset_id)
    sample = await _get_sample(db, dataset.characterization.sample_id)
    await ensure_sample_access(db, current_user, sample, "owner")
    await db.delete(dataset)
