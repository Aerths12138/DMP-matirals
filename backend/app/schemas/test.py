"""Test and TestMeasurement Pydantic schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


# --- Measurement ---

class MeasurementBase(BaseModel):
    property_name: str = Field(max_length=200)
    value_number: float | None = None
    value_text: str | None = Field(default=None, max_length=500)
    unit: str | None = Field(default=None, max_length=50)


class MeasurementCreate(MeasurementBase):
    pass


class MeasurementUpdate(BaseModel):
    property_name: str | None = Field(default=None, max_length=200)
    value_number: float | None = None
    value_text: str | None = None
    unit: str | None = None


class MeasurementResponse(MeasurementBase):
    id: uuid.UUID
    test_id: uuid.UUID
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Test ---

class TestBase(BaseModel):
    test_name: str = Field(max_length=200)
    test_method: str | None = Field(default=None, max_length=200)
    test_date: datetime | None = None
    conditions: dict[str, str] = {}
    notes: str | None = None
    metadata_: dict = Field(default={}, serialization_alias="metadata")


class TestCreate(TestBase):
    material_id: uuid.UUID
    measurements: list[MeasurementCreate] = []
    # Accept "metadata" from JSON
    metadata_: dict = Field(default={}, serialization_alias="metadata", validation_alias="metadata")


class TestUpdate(BaseModel):
    test_name: str | None = Field(default=None, max_length=200)
    test_method: str | None = Field(default=None, max_length=200)
    test_date: datetime | None = None
    conditions: dict[str, str] | None = None
    notes: str | None = None
    metadata_: dict | None = Field(default=None, serialization_alias="metadata", validation_alias="metadata")


class TestResponse(TestBase):
    id: uuid.UUID
    material_id: uuid.UUID
    created_by: uuid.UUID | None = None
    measurements: list[MeasurementResponse] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TestListResponse(BaseModel):
    id: uuid.UUID
    material_id: uuid.UUID
    test_name: str
    test_method: str | None = None
    test_date: datetime | None = None
    conditions: dict[str, str] = {}
    measurement_count: int = 0
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Batch operations ---


class BatchDeleteRequest(BaseModel):
    test_ids: list[uuid.UUID] = Field(min_length=1, max_length=200)


class BatchMergeRequest(BaseModel):
    test_ids: list[uuid.UUID] = Field(min_length=2, max_length=200)
    target_name: str | None = Field(default=None, max_length=200)
    target_method: str | None = Field(default=None, max_length=200)
