"""Schemas for AI assistant conversations, actions, and rollback backups."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class AssistantMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=20000)


class AssistantChatRequest(BaseModel):
    messages: list[AssistantMessage] = Field(min_length=1, max_length=30)
    context_path: str | None = Field(default=None, max_length=300)


class PendingAssistantAction(BaseModel):
    token: str
    tool_name: str
    operation: Literal["create", "update", "delete"]
    entity_type: Literal["material", "project", "experiment", "sample", "property", "test", "test_measurement", "characterization"]
    summary: str
    arguments: dict
    expires_at: str


class PendingAssistantImport(BaseModel):
    filename: str
    sheet_name: str
    source_row_count: int
    material_count: int
    mapping: dict[str, str]
    normalized_rows: list[list]
    normalized_rows_truncated: bool = False
    conversion_count: int
    conversions: list[dict] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    blocking_errors: list[str] = Field(default_factory=list)
    import_rows: list[dict] = Field(default_factory=list)


class AssistantChatResponse(BaseModel):
    message: str
    pending_actions: list[PendingAssistantAction] = Field(default_factory=list)
    pending_import: PendingAssistantImport | None = None
    model: str


class AssistantHistoryResponse(BaseModel):
    messages: list[AssistantMessage] = Field(default_factory=list)
    updated_at: datetime | None = None


class AssistantBackupResponse(BaseModel):
    id: uuid.UUID
    operation: Literal["update", "delete"]
    entity_type: Literal["material", "project", "experiment", "sample", "property", "test", "test_measurement", "characterization"]
    entity_id: uuid.UUID
    entity_name: str
    summary: str
    created_at: datetime
    expires_at: datetime
    restored_at: datetime | None = None

    model_config = {"from_attributes": True}


class AssistantActionConfirmRequest(BaseModel):
    token: str = Field(min_length=20, max_length=12000)


class AssistantActionConfirmResponse(BaseModel):
    message: str
    request_id: uuid.UUID
    entity_type: Literal["material", "project", "experiment", "sample", "property", "test", "test_measurement", "characterization"]
    entity_id: str | None = None
    data: dict
    backup: AssistantBackupResponse | None = None


class AssistantBackupRestoreResponse(BaseModel):
    message: str
    backup_id: uuid.UUID
    entity_type: Literal["material", "project", "experiment", "sample", "property", "test", "test_measurement", "characterization"]
    entity_id: uuid.UUID
