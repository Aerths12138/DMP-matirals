"""Per-user persisted AI assistant conversation history."""

import uuid

from sqlalchemy import Column, DateTime, ForeignKey, JSON, Uuid
from sqlalchemy.sql import func

from app.database import Base


class AssistantConversation(Base):
    __tablename__ = "assistant_conversations"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id = Column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    messages = Column(JSON, nullable=False, default=list)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(
        DateTime,
        default=func.now(),
        onupdate=func.now(),
        nullable=False,
        index=True,
    )
