"""Project, Experiment, Sample, and Processing Pydantic schemas."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field


# ── Project ──────────────────────────────────────────────────────


class ProjectMemberCreate(BaseModel):
    user_id: uuid.UUID
    role: str = Field(pattern=r"^(editor|viewer)$")


class ProjectMemberUpdate(BaseModel):
    role: str = Field(pattern=r"^(editor|viewer)$")


class ProjectMemberUser(BaseModel):
    id: uuid.UUID
    username: str
    display_name: str | None = None

    model_config = {"from_attributes": True}


class ProjectMemberResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    role: str
    created_at: datetime
    updated_at: datetime
    user: ProjectMemberUser

    model_config = {"from_attributes": True}


class ProjectBase(BaseModel):
    name: str = Field(max_length=300)
    description: str | None = None
    status: str = Field(default="active", pattern=r"^(active|completed|archived)$")
    start_date: date | None = None
    end_date: date | None = None
    metadata_: dict = Field(default={}, serialization_alias="metadata")


class ProjectCreate(ProjectBase):
    metadata_: dict = Field(
        default={}, serialization_alias="metadata", validation_alias="metadata"
    )


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=300)
    description: str | None = None
    status: str | None = Field(default=None, pattern=r"^(active|completed|archived)$")
    start_date: date | None = None
    end_date: date | None = None
    metadata_: dict | None = Field(
        default=None, serialization_alias="metadata", validation_alias="metadata"
    )


class ProjectResponse(ProjectBase):
    id: uuid.UUID
    owner_id: uuid.UUID | None = None
    members: list[ProjectMemberResponse] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}



# ── Experiment ───────────────────────────────────────────────────


class ExperimentBase(BaseModel):
    name: str = Field(max_length=300)
    description: str | None = None
    hypothesis: str | None = None
    status: str = Field(
        default="planned", pattern=r"^(planned|running|completed|failed)$"
    )
    start_date: datetime | None = None
    end_date: datetime | None = None
    metadata_: dict = Field(default_factory=dict, serialization_alias="metadata")


class ExperimentCreate(ExperimentBase):
    project_id: uuid.UUID
    metadata_: dict = Field(
        default_factory=dict,
        serialization_alias="metadata",
        validation_alias="metadata",
    )


class ExperimentUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=300)
    description: str | None = None
    hypothesis: str | None = None
    status: str | None = Field(
        default=None, pattern=r"^(planned|running|completed|failed)$"
    )
    start_date: datetime | None = None
    end_date: datetime | None = None
    metadata_: dict | None = Field(
        default=None, serialization_alias="metadata", validation_alias="metadata"
    )


class ExperimentResponse(ExperimentBase):
    id: uuid.UUID
    project_id: uuid.UUID
    owner_id: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Sample ───────────────────────────────────────────────────────


class SampleBase(BaseModel):
    sample_code: str = Field(max_length=200)
    batch_number: str | None = Field(default=None, max_length=100)
    description: str | None = None
    mass_g: float | None = Field(default=None, ge=0)
    dimensions: dict = Field(default_factory=dict)
    form: str | None = Field(default=None, max_length=50)
    storage_location: str | None = Field(default=None, max_length=200)
    status: str = Field(
        default="created", pattern=r"^(created|processing|characterizing|archived)$"
    )
    metadata_: dict = Field(default_factory=dict, serialization_alias="metadata")
    metadata_template_id: uuid.UUID | None = None


class SampleCreate(SampleBase):
    experiment_id: uuid.UUID
    material_id: uuid.UUID | None = None
    metadata_: dict = Field(
        default_factory=dict,
        serialization_alias="metadata",
        validation_alias="metadata",
    )


class SampleUpdate(BaseModel):
    sample_code: str | None = Field(default=None, max_length=200)
    batch_number: str | None = None
    description: str | None = None
    mass_g: float | None = Field(default=None, ge=0)
    dimensions: dict | None = None
    form: str | None = None
    storage_location: str | None = None
    status: str | None = Field(
        default=None, pattern=r"^(created|processing|characterizing|archived)$"
    )
    metadata_: dict | None = Field(
        default=None, serialization_alias="metadata", validation_alias="metadata"
    )
    material_id: uuid.UUID | None = None
    metadata_template_id: uuid.UUID | None = None


class SampleResponse(SampleBase):
    id: uuid.UUID
    experiment_id: uuid.UUID | None = None
    material_id: uuid.UUID | None = None
    created_by: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Processing Method ────────────────────────────────────────────


class ProcessingBase(BaseModel):
    method_type: str = Field(max_length=100)
    parameters: dict = {}
    equipment: str | None = Field(default=None, max_length=300)
    description: str | None = None
    order_in_chain: int | None = None
    parent_step_id: uuid.UUID | None = None


class ProcessingCreate(ProcessingBase):
    material_id: uuid.UUID | None = None
    sample_id: uuid.UUID | None = None


class ProcessingUpdate(BaseModel):
    method_type: str | None = Field(default=None, max_length=100)
    parameters: dict | None = None
    equipment: str | None = Field(default=None, max_length=300)
    description: str | None = None
    order_in_chain: int | None = None


class ProcessingResponse(ProcessingBase):
    id: uuid.UUID
    material_id: uuid.UUID | None = None
    sample_id: uuid.UUID | None = None
    created_by: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
