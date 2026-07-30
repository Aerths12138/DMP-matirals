"""Schemas for project metadata templates and controlled units."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


MetadataEntityType = Literal["sample", "characterization"]
MetadataValueType = Literal["string", "number", "integer", "boolean"]


class MetadataFieldDefinition(BaseModel):
    key: str = Field(max_length=64, pattern=r"^[A-Za-z][A-Za-z0-9_]*$")
    label: str = Field(max_length=100)
    value_type: MetadataValueType = "string"
    required: bool = False
    unit: str | None = Field(default=None, max_length=50)
    options: list[str] = Field(default_factory=list, max_length=100)
    description: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_field_definition(self):
        if self.options and self.value_type != "string":
            raise ValueError("Controlled options are supported only for string fields")
        if self.unit and self.value_type not in {"number", "integer"}:
            raise ValueError("Units are supported only for numeric fields")
        if len(set(self.options)) != len(self.options):
            raise ValueError("Controlled options must be unique")
        return self


class MetadataTemplateCreate(BaseModel):
    project_id: uuid.UUID
    name: str = Field(max_length=200)
    entity_type: MetadataEntityType
    description: str | None = None
    fields: list[MetadataFieldDefinition] = Field(default_factory=list, max_length=100)


class MetadataTemplateUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    description: str | None = None
    fields: list[MetadataFieldDefinition] | None = Field(default=None, max_length=100)
    is_active: bool | None = None


class MetadataTemplateResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    entity_type: MetadataEntityType
    description: str | None = None
    fields: list[MetadataFieldDefinition]
    is_active: bool
    created_by: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class UnitDefinitionCreate(BaseModel):
    project_id: uuid.UUID
    symbol: str = Field(max_length=50)
    name: str = Field(max_length=100)
    quantity_type: str = Field(max_length=100)
    description: str | None = None


class UnitDefinitionResponse(BaseModel):
    id: str
    project_id: uuid.UUID | None = None
    symbol: str
    name: str
    quantity_type: str
    description: str | None = None
    is_active: bool = True
    is_builtin: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}
