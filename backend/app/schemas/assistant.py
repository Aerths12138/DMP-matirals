"""Schemas for AI assistant conversations, actions, and rollback backups."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class AssistantMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=6000)


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


class AssistantChatResponse(BaseModel):
    message: str
    pending_actions: list[PendingAssistantAction] = Field(default_factory=list)
    model: str


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
    entity_type: Literal["material", "project", "experiment", "sample", "property", "test", "test_measurement", "characterization"]
    entity_id: str | None = None
    data: dict
    backup: AssistantBackupResponse | None = None


class AssistantBackupRestoreResponse(BaseModel):
    message: str
    backup_id: uuid.UUID
    entity_type: Literal["material", "project", "experiment", "sample", "property", "test", "test_measurement", "characterization"]
    entity_id: uuid.UUID
