"""Collection model — user-defined subsets of materials."""

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, JSON, String, Text, Uuid
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class Collection(Base):
    __tablename__ = "collections"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    name = Column(String(200), nullable=False, index=True)
    description = Column(Text)
    material_ids = Column(JSON, nullable=False, default=list)  # list of material UUID strings
    visibility = Column(String(20), nullable=False, default="private")  # private | role | public
    allowed_role_ids = Column(JSON, nullable=False, default=list)  # role IDs when visibility="role"
    created_by = Column(Uuid, ForeignKey("users.id"))
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    creator = relationship("User", foreign_keys=[created_by], lazy="selectin")

    def __repr__(self) -> str:
        return f"<Collection {self.name}>"
