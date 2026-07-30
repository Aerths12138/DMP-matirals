"""Characterization model — measurement/analysis performed on a sample."""

import uuid

from sqlalchemy import Column, DateTime, ForeignKey, JSON, String, Text, Uuid
from sqlalchemy.orm import foreign, relationship
from sqlalchemy.sql import func

from app.database import Base


class Characterization(Base):
    __tablename__ = "characterizations"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    sample_id = Column(Uuid, ForeignKey("samples.id", ondelete="CASCADE"), nullable=False, index=True)
    technique = Column(String(100), nullable=False)
    title = Column(String(300))
    description = Column(Text)
    instrument = Column(String(300))
    parameters = Column(JSON, nullable=False, default=dict)
    acquisition_date = Column(DateTime)
    operator_id = Column(Uuid, ForeignKey("users.id"))
    status = Column(String(30), default="raw")
    quality_flag = Column(String(20), default="good")
    metadata_ = Column("metadata", JSON, default=dict)
    metadata_template_id = Column(
        Uuid,
        ForeignKey("metadata_templates.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_by = Column(Uuid, ForeignKey("users.id"))
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    sample = relationship("Sample", back_populates="characterizations")
    operator = relationship("User", foreign_keys=[operator_id], lazy="selectin")
    creator = relationship("User", foreign_keys=[created_by], lazy="selectin")
    files = relationship(
        "File",
        primaryjoin="and_(foreign(File.parent_type)=='characterization', foreign(File.parent_id)==Characterization.id)",
        viewonly=True,
        cascade="all, delete-orphan",
    )
    analysis_results = relationship("AnalysisResult", back_populates="characterization", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Characterization {self.technique} on {self.sample_id}>"
