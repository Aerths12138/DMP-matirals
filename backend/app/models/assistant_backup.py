"""Temporary server-side backups for reversible AI mutations."""

import uuid

from sqlalchemy import Column, DateTime, ForeignKey, JSON, String, Text, Uuid
from sqlalchemy.sql import func

from app.database import Base


class AssistantEntityBackup(Base):
    __tablename__ = "assistant_entity_backups"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    action_execution_id = Column(
        Uuid,
        ForeignKey("assistant_action_executions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    user_id = Column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tool_name = Column(String(64), nullable=False)
    operation = Column(String(20), nullable=False)
    entity_type = Column(String(50), nullable=False, index=True)
    entity_id = Column(Uuid, nullable=False, index=True)
    entity_name = Column(String(500), nullable=False)
    summary = Column(Text, nullable=False)
    snapshot = Column(JSON, nullable=False)
    post_snapshot = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=func.now(), nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False, index=True)
    restored_at = Column(DateTime, nullable=True, index=True)
    restored_by = Column(Uuid, ForeignKey("users.id"), nullable=True)
