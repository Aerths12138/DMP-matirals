"""File model — metadata for uploaded files stored in local / MinIO storage."""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Column, DateTime, Float, ForeignKey, Integer, JSON, String, Text, Uuid
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class File(Base):
    __tablename__ = "files"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    parent_type = Column(String(50), nullable=False, index=True)  # material, characterization, analysis, sample, experiment
    parent_id = Column(Uuid, nullable=False, index=True)
    original_name = Column(String(500), nullable=False)
    stored_path = Column(String(1000), nullable=False)
    storage_backend = Column(String(20), default="local")  # local, minio
    mime_type = Column(String(100))
    file_size_bytes = Column(BigInteger)
    checksum_sha256 = Column(String(64))
    file_type = Column(String(50))  # sem_image, cif_file, xrd_raw, spreadsheet, document
    description = Column(Text)
    image_width = Column(Integer)
    image_height = Column(Integer)
    image_channels = Column(Integer)
    pixel_scale_um = Column(Float)
    tags = Column(JSON, default=list)
    uploaded_by = Column(Uuid, ForeignKey("users.id"))
    created_at = Column(DateTime, default=func.now())

    # Relationships — we use foreign_keys on the other side, so no back_populates needed here.
    # Instead, use dynamic relationship lookups.
    uploader = relationship("User", foreign_keys=[uploaded_by], lazy="selectin")

    # Convenience accessors for parent entities
    material = relationship(
        "Material",
        primaryjoin="and_(File.parent_type=='material', foreign(File.parent_id)==Material.id)",
        viewonly=True,
        lazy="selectin",
    )

    characterization = relationship(
        "Characterization",
        primaryjoin="and_(File.parent_type=='characterization', foreign(File.parent_id)==Characterization.id)",
        viewonly=True,
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<File {self.original_name}>"
