"""Generic ordered datasets produced by characterization instruments."""

import uuid

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, JSON, String, UniqueConstraint, Uuid
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class MeasurementDataset(Base):
    __tablename__ = "measurement_datasets"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    characterization_id = Column(
        Uuid,
        ForeignKey("characterizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_file_id = Column(
        Uuid,
        ForeignKey("files.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    name = Column(String(200), nullable=False)
    x_name = Column(String(100), nullable=False)
    x_unit = Column(String(50))
    series_schema = Column(JSON, nullable=False, default=list)
    provenance = Column(JSON, nullable=False, default=dict)
    row_count = Column(Integer, nullable=False, default=0)
    created_by = Column(Uuid, ForeignKey("users.id"))
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    characterization = relationship("Characterization", back_populates="measurement_datasets")
    source_file = relationship("File", foreign_keys=[source_file_id], lazy="selectin")
    points = relationship(
        "MeasurementPoint",
        back_populates="dataset",
        cascade="all, delete-orphan",
        order_by="MeasurementPoint.sequence",
    )


class MeasurementPoint(Base):
    __tablename__ = "measurement_points"
    __table_args__ = (
        UniqueConstraint(
            "dataset_id",
            "sequence",
            name="uq_measurement_points_dataset_sequence",
        ),
    )

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    dataset_id = Column(
        Uuid,
        ForeignKey("measurement_datasets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sequence = Column(Integer, nullable=False)
    x_value = Column(Float, nullable=False)
    values = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    dataset = relationship("MeasurementDataset", back_populates="points")
