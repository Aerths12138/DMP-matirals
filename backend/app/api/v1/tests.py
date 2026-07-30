"""Test CRUD endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import (
    ensure_material_access,
    get_db,
    material_visibility_condition,
    require_permission,
)
from app.models.material import Material
from app.models.test import Test, TestMeasurement
from app.models.user import User
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.test import (
    BatchDeleteRequest,
    BatchMergeRequest,
    MeasurementCreate,
    MeasurementResponse,
    MeasurementUpdate,
    TestCreate,
    TestResponse,
    TestUpdate,
)

router = APIRouter(prefix="/tests", tags=["Tests"])


async def _get_test(db: AsyncSession, test_id: uuid.UUID) -> Test:
    result = await db.execute(
        select(Test).options(selectinload(Test.measurements)).where(Test.id == test_id)
    )
    test = result.scalar_one_or_none()
    if test is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test not found")
    return test


async def _ensure_test_access(
    db: AsyncSession,
    current_user: User,
    test: Test,
    minimum_role: str,
) -> None:
    material = await db.get(Material, test.material_id)
    if material is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Material not found")
    await ensure_material_access(db, current_user, material, minimum_role)


@router.get("", response_model=PaginatedResponse[TestResponse])
async def list_tests(
    material_id: str | None = None,
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("property:read")),
):
    """List visible tests with measurements, optionally filtered by material."""
    query = select(Test).options(selectinload(Test.measurements))

    if material_id:
        material_uuid = uuid.UUID(material_id)
        material = await db.get(Material, material_uuid)
        if material is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Material not found")
        await ensure_material_access(db, current_user, material, "viewer")
        query = query.where(Test.material_id == material_uuid)
    else:
        query = query.join(Material, Test.material_id == Material.id).where(
            material_visibility_condition(current_user)
        )

    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    offset = (pagination.page - 1) * pagination.size
    query = query.order_by(Test.created_at.desc()).offset(offset).limit(pagination.size)
    result = await db.execute(query)
    tests = result.scalars().all()

    return PaginatedResponse(
        items=[TestResponse.model_validate(test) for test in tests],
        total=total,
        page=pagination.page,
        size=pagination.size,
        pages=(total + pagination.size - 1) // pagination.size if total > 0 else 0,
    )


@router.get("/{test_id}", response_model=TestResponse)
async def get_test(
    test_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("property:read")),
):
    """Get a visible test with its measurements."""
    test = await _get_test(db, uuid.UUID(test_id))
    await _ensure_test_access(db, current_user, test, "viewer")
    return test


@router.post("", response_model=TestResponse, status_code=status.HTTP_201_CREATED)
async def create_test(
    body: TestCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("property:create")),
):
    """Create a test with optional measurements."""
    material = await db.get(Material, body.material_id)
    if material is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Material not found")
    await ensure_material_access(db, current_user, material, "editor")

    test = Test(
        **body.model_dump(exclude={"metadata_", "measurements"}),
        metadata_=body.metadata_,
        created_by=current_user.id,
    )
    db.add(test)
    await db.flush()

    for measurement in body.measurements:
        db.add(
            TestMeasurement(
                test_id=test.id,
                property_name=measurement.property_name,
                value_number=measurement.value_number,
                value_text=measurement.value_text,
                unit=measurement.unit,
            )
        )

    await db.flush()
    return await _get_test(db, test.id)


@router.put("/{test_id}", response_model=TestResponse)
async def update_test(
    test_id: str,
    body: TestUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("property:update")),
):
    """Update a test."""
    test = await _get_test(db, uuid.UUID(test_id))
    await _ensure_test_access(db, current_user, test, "editor")

    update_data = body.model_dump(exclude_unset=True, exclude={"metadata_"})
    if body.metadata_ is not None:
        test.metadata_ = body.metadata_
    for field, value in update_data.items():
        setattr(test, field, value)

    await db.flush()
    return await _get_test(db, test.id)


@router.delete("/{test_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_test(
    test_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("property:delete")),
):
    """Delete a test and all its measurements."""
    test = await _get_test(db, uuid.UUID(test_id))
    await _ensure_test_access(db, current_user, test, "owner")
    await db.delete(test)


@router.post("/batch-delete", status_code=status.HTTP_204_NO_CONTENT)
async def batch_delete_tests(
    body: BatchDeleteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("property:delete")),
):
    """Delete multiple authorized tests and their measurements."""
    tests: list[Test] = []
    for test_id in body.test_ids:
        result = await db.execute(select(Test).where(Test.id == test_id))
        test = result.scalar_one_or_none()
        if test:
            await _ensure_test_access(db, current_user, test, "owner")
            tests.append(test)
    for test in tests:
        await db.delete(test)


@router.post("/batch-merge", response_model=TestResponse)
async def batch_merge_tests(
    body: BatchMergeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("property:update")),
):
    """Merge tests from one material into the first test."""
    tests: list[Test] = []
    for test_id in body.test_ids:
        result = await db.execute(
            select(Test).options(selectinload(Test.measurements)).where(Test.id == test_id)
        )
        test = result.scalar_one_or_none()
        if test:
            await _ensure_test_access(db, current_user, test, "editor")
            tests.append(test)

    if len(tests) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least two tests are required to merge",
        )
    if len({test.material_id for test in tests}) != 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tests from different materials cannot be merged",
        )

    target = tests[0]
    if body.target_name:
        target.test_name = body.target_name
    if body.target_method:
        target.test_method = body.target_method

    merged: dict[str, str] = {}
    for test in tests:
        for key, value in (test.conditions or {}).items():
            if key not in merged:
                merged[key] = value
    target.conditions = merged

    for test in tests[1:]:
        for measurement in test.measurements:
            measurement.test_id = target.id
        await db.delete(test)

    await db.flush()
    return await _get_test(db, target.id)


@router.post(
    "/{test_id}/measurements",
    response_model=MeasurementResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_measurement(
    test_id: str,
    body: MeasurementCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("property:create")),
):
    """Add a measurement to an existing test."""
    test = await _get_test(db, uuid.UUID(test_id))
    await _ensure_test_access(db, current_user, test, "editor")

    measurement = TestMeasurement(test_id=test.id, **body.model_dump())
    db.add(measurement)
    await db.flush()
    await db.refresh(measurement)
    return measurement


@router.put(
    "/{test_id}/measurements/{measurement_id}",
    response_model=MeasurementResponse,
)
async def update_measurement(
    test_id: str,
    measurement_id: str,
    body: MeasurementUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("property:update")),
):
    """Update a measurement."""
    result = await db.execute(
        select(TestMeasurement).where(
            TestMeasurement.id == uuid.UUID(measurement_id),
            TestMeasurement.test_id == uuid.UUID(test_id),
        )
    )
    measurement = result.scalar_one_or_none()
    if measurement is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Measurement not found",
        )
    test = await _get_test(db, uuid.UUID(test_id))
    await _ensure_test_access(db, current_user, test, "editor")

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(measurement, field, value)
    await db.flush()
    await db.refresh(measurement)
    return measurement


@router.delete(
    "/{test_id}/measurements/{measurement_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_measurement(
    test_id: str,
    measurement_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("property:delete")),
):
    """Delete a measurement."""
    result = await db.execute(
        select(TestMeasurement).where(
            TestMeasurement.id == uuid.UUID(measurement_id),
            TestMeasurement.test_id == uuid.UUID(test_id),
        )
    )
    measurement = result.scalar_one_or_none()
    if measurement is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Measurement not found",
        )
    test = await _get_test(db, uuid.UUID(test_id))
    await _ensure_test_access(db, current_user, test, "owner")
    await db.delete(measurement)
