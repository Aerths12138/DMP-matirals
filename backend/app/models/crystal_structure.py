"""Crystal structure model — parsed from CIF or entered manually."""

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, JSON, String, Text, Uuid
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class CrystalStructure(Base):
    __tablename__ = "crystal_structures"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    material_id = Column(Uuid, ForeignKey("materials.id", ondelete="CASCADE"), nullable=False)
    space_group = Column(String(20))
    space_group_num = Column(Integer)
    crystal_system = Column(String(20))  # cubic, hexagonal, monoclinic, etc.
    a = Column(Float)
    b = Column(Float)
    c = Column(Float)
    alpha = Column(Float)
    beta = Column(Float)
    gamma = Column(Float)
    volume = Column(Float)
    atomic_sites = Column(JSON, default=list)
    # [{"element":"Li","x":0,"y":0,"z":0,"occupancy":1.0,"site":"3a","wyckoff":"3a"}, ...]
    symmetry_ops = Column(JSON, default=list)
    cif_file_id = Column(Uuid, ForeignKey("files.id"))
    cif_raw_data = Column(JSON, default=dict)
    source_type = Column(String(20), default="experimental")  # experimental, dft, literature
    source_doi = Column(String(200))
    metadata_ = Column("metadata", JSON, default=dict)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    material = relationship("Material", back_populates="crystal_structures")
    cif_file = relationship("File", foreign_keys=[cif_file_id], lazy="selectin")

    def __repr__(self) -> str:
        return f"<CrystalStructure {self.space_group} {self.crystal_system}>"
