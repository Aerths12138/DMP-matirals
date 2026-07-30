"""AuditLog model — tracks all mutating operations for compliance."""

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, JSON, String, Text, Uuid
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id = Column(Uuid, ForeignKey("users.id"), index=True)
    action = Column(String(50), nullable=False)  # CREATE, UPDATE, DELETE, EXPORT, LOGIN, RUN_ANALYSIS
    entity_type = Column(String(50), nullable=False, index=True)  # material, experiment, characterization, user
    entity_id = Column(Uuid, index=True)
    changes = Column(JSON, default=dict)  # {"field":"composition","old":...,"new":...}
    ip_address = Column(String(45))
    user_agent = Column(Text)
    request_id = Column(Uuid, index=True)  # For correlating multi-row changes
    created_at = Column(DateTime, default=func.now(), index=True)

    user = relationship("User", foreign_keys=[user_id], lazy="selectin")

    def __repr__(self) -> str:
        return f"<AuditLog {self.action} {self.entity_type}>"
