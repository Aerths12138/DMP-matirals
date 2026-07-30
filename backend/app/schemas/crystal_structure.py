"""CrystalStructure Pydantic schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class AtomicSite(BaseModel):
    element: str
    x: float
    y: float
    z: float
    occupancy: float = 1.0
    site: str | None = None
    wyckoff: str | None = None


class CrystalStructureBase(BaseModel):
    space_group: str | None = Field(default=None, max_length=20)
    space_group_num: int | None = None
    crystal_system: str | None = Field(default=None, max_length=20)
    a: float | None = None
    b: float | None = None
    c: float | None = None
    alpha: float | None = None
    beta: float | None = None
    gamma: float | None = None
    volume: float | None = None
    atomic_sites: list[AtomicSite] = []
    symmetry_ops: list[dict] = []
    source_type: str = Field(default="experimental", max_length=20)
    source_doi: str | None = Field(default=None, max_length=200)
    metadata_: dict = Field(default={}, serialization_alias="metadata")


class CrystalStructureCreate(CrystalStructureBase):
    material_id: uuid.UUID
    metadata_: dict = Field(default={}, serialization_alias="metadata", validation_alias="metadata")


class CrystalStructureUpdate(BaseModel):
    space_group: str | None = None
    space_group_num: int | None = None
    crystal_system: str | None = None
    a: float | None = None
    b: float | None = None
    c: float | None = None
    alpha: float | None = None
    beta: float | None = None
    gamma: float | None = None
    volume: float | None = None
    atomic_sites: list[AtomicSite] | None = None
    symmetry_ops: list[dict] | None = None
    source_type: str | None = None
    source_doi: str | None = None
    metadata_: dict | None = Field(default=None, serialization_alias="metadata", validation_alias="metadata")


class CrystalStructureResponse(CrystalStructureBase):
    id: uuid.UUID
    material_id: uuid.UUID
    cif_file_id: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
