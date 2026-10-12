"""File and Audit schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class FileResponse(BaseModel):
    id: uuid.UUID
    parent_type: str
    parent_id: uuid.UUID
    original_name: str
    stored_path: str
    storage_backend: str = "local"
    mime_type: str | None = None
    file_size_bytes: int | None = None
    checksum_sha256: str | None = None
    file_type: str | None = None
    description: str | None = None
    image_width: int | None = None
    image_height: int | None = None
    tags: list[str] = Field(default_factory=list)
    knowledge_status: str = "pending"
    knowledge_chunk_count: int = 0
    knowledge_indexed_at: datetime | None = None
    knowledge_error: str | None = None
    uploaded_by: uuid.UUID | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class FileUploadResponse(BaseModel):
    id: uuid.UUID
    original_name: str
    mime_type: str | None = None
    file_size_bytes: int | None = None
    thumbnail_url: str | None = None
    download_url: str
    knowledge: dict = Field(default_factory=dict)


# ── Audit ────────────────────────────────────────────────────────


class AuditLogResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID | None = None
    username: str | None = None
    action: str
    entity_type: str
    entity_id: uuid.UUID | None = None
    changes: dict = {}
    ip_address: str | None = None
    request_id: uuid.UUID | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
