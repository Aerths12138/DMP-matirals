"""Material Pydantic schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.test import TestResponse


class CompositionItem(BaseModel):
    """A single composition entry — element, monomer, or phase."""

    element: str | None = None
    monomer: str | None = None
    phase: str | None = None
    amount: float | None = None
    unit: str = "wt%"  # wt%, at%, mole_percent, weight_fraction
    mole_percent: float | None = None
    weight_fraction: float | None = None


class MaterialBase(BaseModel):
    name: str = Field(max_length=500)
    material_type: str = Field(max_length=50)
    formula_string: str | None = Field(default=None, max_length=500)
    hill_formula: str | None = Field(default=None, max_length=300)
    composition: list[CompositionItem] = []
    aliases: list[str] = []
    description: str | None = None
    metadata_: dict = Field(default={}, serialization_alias="metadata")
    project_id: uuid.UUID | None = None


class MaterialCreate(MaterialBase):
    # Accept "metadata" from JSON input, maps to metadata_ ← SQLAlchemy column name
    metadata_: dict = Field(default={}, serialization_alias="metadata", validation_alias="metadata")


class MaterialUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=500)
    material_type: str | None = Field(default=None, max_length=50)
    formula_string: str | None = Field(default=None, max_length=500)
    hill_formula: str | None = Field(default=None, max_length=300)
    composition: list[CompositionItem] | None = None
    aliases: list[str] | None = None
    description: str | None = None
    metadata_: dict | None = Field(default=None, serialization_alias="metadata", validation_alias="metadata")
    project_id: uuid.UUID | None = None


class MaterialResponse(MaterialBase):
    id: uuid.UUID
    created_by: uuid.UUID | None = None
    tests: list[TestResponse] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MaterialListResponse(BaseModel):
    id: uuid.UUID
    name: str
    material_type: str
    formula_string: str | None = None
    aliases: list[str] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
