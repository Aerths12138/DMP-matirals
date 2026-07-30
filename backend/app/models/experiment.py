"""Experiment model — groups samples and characterizations under a project."""

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, JSON, String, Text, Uuid
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class Experiment(Base):
    __tablename__ = "experiments"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    project_id = Column(Uuid, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(300), nullable=False)
    description = Column(Text)
    hypothesis = Column(Text)
    status = Column(String(30), default="planned")  # planned, running, completed, failed
    start_date = Column(DateTime)
    end_date = Column(DateTime)
    owner_id = Column(Uuid, ForeignKey("users.id"))
    metadata_ = Column("metadata", JSON, default=dict)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    project = relationship("Project", back_populates="experiments")
    owner = relationship("User", foreign_keys=[owner_id], lazy="selectin")
    samples = relationship("Sample", back_populates="experiment", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Experiment {self.name}>"
