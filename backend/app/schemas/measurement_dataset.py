"""Schemas for ordered measurement datasets imported from tabular files."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, model_validator


class MeasurementSeries(BaseModel):
    key: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    unit: str | None = Field(default=None, max_length=50)


class MeasurementPointCreate(BaseModel):
    sequence: int = Field(ge=1)
    x_value: float
    values: dict[str, float]


class MeasurementDatasetCreate(BaseModel):
    sample_id: uuid.UUID
    name: str = Field(min_length=1, max_length=200)
    x_name: str = Field(min_length=1, max_length=100)
    x_unit: str | None = Field(default=None, max_length=50)
    series_schema: list[MeasurementSeries] = Field(min_length=1, max_length=100)
    points: list[MeasurementPointCreate] = Field(min_length=1, max_length=100000)
    provenance: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_dataset(self):
        keys = [series.key for series in self.series_schema]
        if len(keys) != len(set(keys)):
            raise ValueError("Series keys must be unique")
        sequences = [point.sequence for point in self.points]
        if len(sequences) != len(set(sequences)):
            raise ValueError("Point sequences must be unique")
        allowed = set(keys)
        for point in self.points:
            unknown = set(point.values) - allowed
            if unknown:
                raise ValueError(f"Point contains unknown series keys: {sorted(unknown)}")
        return self


class MeasurementDatasetUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    x_name: str | None = Field(default=None, min_length=1, max_length=100)
    x_unit: str | None = Field(default=None, max_length=50)
    series_schema: list[MeasurementSeries] | None = Field(default=None, min_length=1, max_length=100)
    points: list[MeasurementPointCreate] | None = Field(default=None, min_length=1, max_length=100000)
    provenance: dict | None = None
    source_file_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def validate_dataset(self):
        if self.series_schema is not None:
            keys = [series.key for series in self.series_schema]
            if len(keys) != len(set(keys)):
                raise ValueError("Series keys must be unique")
            allowed = set(keys)
            if self.points is not None:
                for point in self.points:
                    unknown = set(point.values) - allowed
                    if unknown:
                        raise ValueError(f"Point contains unknown series keys: {sorted(unknown)}")
        if self.points is not None:
            sequences = [point.sequence for point in self.points]
            if len(sequences) != len(set(sequences)):
                raise ValueError("Point sequences must be unique")
        return self


class MeasurementPointResponse(BaseModel):
    sequence: int
    x_value: float
    values: dict[str, float]

    model_config = {"from_attributes": True}


class MeasurementDatasetSummary(BaseModel):
    id: uuid.UUID
    characterization_id: uuid.UUID
    source_file_id: uuid.UUID | None = None
    name: str
    x_name: str
    x_unit: str | None = None
    series_schema: list[dict]
    provenance: dict
    row_count: int
    created_by: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MeasurementDatasetResponse(MeasurementDatasetSummary):
    points: list[MeasurementPointResponse]
