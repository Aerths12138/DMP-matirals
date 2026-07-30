"""Material model — core identity for any material."""

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, JSON, String, Text, Uuid
from sqlalchemy.orm import foreign, relationship
from sqlalchemy.sql import func

from app.database import Base


class Material(Base):
    __tablename__ = "materials"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    name = Column(String(500), nullable=False, index=True)
    material_type = Column(String(50), nullable=False, index=True)  # metal, polymer, ceramic, composite, battery, other
    composition = Column(JSON, nullable=False, default=list)
    # composition: [{"element":"Fe","amount":95.5,"unit":"wt%"}] or [{"monomer":"PVDF","mole_percent":70}]
    formula_string = Column(String(500))
    hill_formula = Column(String(300))
    aliases = Column(JSON, default=list)
    description = Column(Text)
    metadata_ = Column("metadata", JSON, default=dict)
    created_by = Column(Uuid, ForeignKey("users.id"))
    project_id = Column(Uuid, ForeignKey("projects.id"))
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    creator = relationship("User", foreign_keys=[created_by], lazy="selectin")
    project = relationship("Project", back_populates="materials", foreign_keys=[project_id])
    crystal_structures = relationship("CrystalStructure", back_populates="material", cascade="all, delete-orphan")
    properties = relationship("Property", back_populates="material", cascade="all, delete-orphan")
    mechanical_properties = relationship("MechanicalProperties", back_populates="material", cascade="all, delete-orphan")
    thermal_properties = relationship("ThermalProperties", back_populates="material", cascade="all, delete-orphan")
    electrical_properties = relationship("ElectricalProperties", back_populates="material", cascade="all, delete-orphan")
    magnetic_properties = relationship("MagneticProperties", back_populates="material", cascade="all, delete-orphan")
    optical_properties = relationship("OpticalProperties", back_populates="material", cascade="all, delete-orphan")
    processing_methods = relationship("ProcessingMethod", back_populates="material", cascade="all, delete-orphan")
    samples = relationship("Sample", back_populates="material")
    tests = relationship("Test", back_populates="material", cascade="all, delete-orphan")
    files = relationship(
        "File",
        primaryjoin="and_(foreign(File.parent_type)=='material', foreign(File.parent_id)==Material.id)",
        viewonly=True,
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Material {self.name}>"
