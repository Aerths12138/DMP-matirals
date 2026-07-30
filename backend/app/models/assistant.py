"""Execution receipts for confirmed AI assistant write actions."""

import uuid

from sqlalchemy import Column, DateTime, ForeignKey, JSON, String, Uuid
from sqlalchemy.sql import func

from app.database import Base


class AssistantActionExecution(Base):
    """A committed receipt prevents a signed action from being replayed."""

    __tablename__ = "assistant_action_executions"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id = Column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tool_name = Column(String(64), nullable=False)
    entity_type = Column(String(50), nullable=False)
    entity_id = Column(Uuid, nullable=True, index=True)
    arguments = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False, index=True)
