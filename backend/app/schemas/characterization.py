"""Characterization and immutable analysis-result schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class CharacterizationBase(BaseModel):
    technique: str = Field(max_length=100)
    title: str | None = Field(default=None, max_length=300)
    description: str | None = None
    instrument: str | None = Field(default=None, max_length=300)
    parameters: dict = Field(default_factory=dict)
    acquisition_date: datetime | None = None
    status: str = Field(default="raw", max_length=30)
    quality_flag: str = Field(default="good", max_length=20)
    metadata_: dict = Field(default_factory=dict, serialization_alias="metadata")
    metadata_template_id: uuid.UUID | None = None


class CharacterizationCreate(CharacterizationBase):
    sample_id: uuid.UUID
    metadata_: dict = Field(
        default_factory=dict,
        serialization_alias="metadata",
        validation_alias="metadata",
    )


class CharacterizationUpdate(BaseModel):
    technique: str | None = Field(default=None, max_length=100)
    title: str | None = Field(default=None, max_length=300)
    description: str | None = None
    instrument: str | None = Field(default=None, max_length=300)
    parameters: dict | None = None
    acquisition_date: datetime | None = None
    status: str | None = Field(default=None, max_length=30)
    quality_flag: str | None = Field(default=None, max_length=20)
    metadata_: dict | None = Field(
        default=None,
        serialization_alias="metadata",
        validation_alias="metadata",
    )
    metadata_template_id: uuid.UUID | None = None


class CharacterizationResponse(CharacterizationBase):
    id: uuid.UUID
    sample_id: uuid.UUID
    operator_id: uuid.UUID | None = None
    created_by: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AnalysisResultCreate(BaseModel):
    characterization_id: uuid.UUID
    analysis_type: str = Field(max_length=100)
    pipeline_name: str | None = Field(default=None, max_length=200)
    model_name: str | None = Field(default=None, max_length=200)
    model_version: str | None = Field(default=None, max_length=50)
    result_data: dict = Field(default_factory=dict)
    segmentation_data: dict | None = None
    quality_metrics: dict = Field(default_factory=dict)
    source_file_id: uuid.UUID | None = None
    processing_time_ms: int | None = Field(default=None, ge=0)
    gpu_used: bool = False
    error_message: str | None = None


class AnalysisResultResponse(BaseModel):
    id: uuid.UUID
    characterization_id: uuid.UUID
    analysis_type: str
    pipeline_name: str | None = None
    model_name: str | None = None
    model_version: str | None = None
    result_data: dict = Field(default_factory=dict)
    segmentation_data: dict | None = None
    quality_metrics: dict = Field(default_factory=dict)
    source_file_id: uuid.UUID | None = None
    processing_time_ms: int | None = None
    gpu_used: bool = False
    error_message: str | None = None
    is_latest: bool = True
    previous_version_id: uuid.UUID | None = None
    run_by: uuid.UUID | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AnalysisStatusResponse(BaseModel):
    task_id: str
    status: str
    progress: str | None = None
    result: AnalysisResultResponse | None = None
    error: str | None = None
