"""Collection Pydantic schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class CollectionBase(BaseModel):
    name: str = Field(max_length=200)
    description: str | None = None
    material_ids: list[uuid.UUID] = []
    visibility: str = "private"  # private | role | public
    allowed_role_ids: list[int] = []  # visible roles when visibility="role"


class CollectionCreate(CollectionBase):
    pass


class CollectionUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    description: str | None = None
    material_ids: list[uuid.UUID] | None = None
    visibility: str | None = None
    allowed_role_ids: list[int] | None = None


class CollectionResponse(CollectionBase):
    id: uuid.UUID
    created_by: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CollectionListResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None = None
    visibility: str = "private"
    material_count: int = 0
    created_by: uuid.UUID | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AddMaterialsRequest(BaseModel):
    material_ids: list[uuid.UUID] = Field(min_length=1, max_length=500)
