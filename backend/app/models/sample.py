"""Sample model — a physical specimen linked to a material and experiment."""

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, JSON, String, Text, Uuid
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class Sample(Base):
    __tablename__ = "samples"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    experiment_id = Column(Uuid, ForeignKey("experiments.id", ondelete="CASCADE"), nullable=True, index=True)
    material_id = Column(Uuid, ForeignKey("materials.id", ondelete="SET NULL"), index=True)
    sample_code = Column(String(200), nullable=False)
    batch_number = Column(String(100))
    description = Column(Text)
    mass_g = Column(Float)
    dimensions = Column(JSON, default=dict)  # {"length_mm":10,"width_mm":10,"thickness_mm":1}
    form = Column(String(50))  # film, pellet, powder, fiber, bulk, liquid
    storage_location = Column(String(200))
    status = Column(String(30), default="created")  # created, processing, characterizing, archived
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

    experiment = relationship("Experiment", back_populates="samples")
    material = relationship("Material", back_populates="samples")
    creator = relationship("User", foreign_keys=[created_by], lazy="selectin")
    processing_methods = relationship("ProcessingMethod", back_populates="sample", cascade="all, delete-orphan")
    characterizations = relationship("Characterization", back_populates="sample", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Sample {self.sample_code}>"
