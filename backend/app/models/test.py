"""Test and TestMeasurement models — experiment runs with conditions and results."""

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, JSON, String, Text, Uuid
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class Test(Base):
    """A test/experiment run on a material with variable conditions."""

    __tablename__ = "tests"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    material_id = Column(Uuid, ForeignKey("materials.id", ondelete="CASCADE"), nullable=False, index=True)
    test_name = Column(String(200), nullable=False)
    test_method = Column(String(200))
    test_date = Column(DateTime)
    conditions = Column(JSON, default=dict)  # {"温度":"25°C","频率":"1kHz"}
    notes = Column(Text)
    metadata_ = Column("metadata", JSON, default=dict)
    created_by = Column(Uuid, ForeignKey("users.id"))
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    material = relationship("Material", back_populates="tests")
    measurements = relationship("TestMeasurement", back_populates="test", cascade="all, delete-orphan")
    creator = relationship("User", foreign_keys=[created_by])

    def __repr__(self) -> str:
        return f"<Test {self.test_name} conditions={self.conditions}>"


class TestMeasurement(Base):
    """A single measurement within a test run."""

    __tablename__ = "test_measurements"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    test_id = Column(Uuid, ForeignKey("tests.id", ondelete="CASCADE"), nullable=False, index=True)
    property_name = Column(String(200), nullable=False)
    value_number = Column(Float)
    value_text = Column(String(500))
    unit = Column(String(50))
    metadata_ = Column("metadata", JSON, default=dict)
    created_at = Column(DateTime, default=func.now())

    test = relationship("Test", back_populates="measurements")

    def __repr__(self) -> str:
        return f"<TestMeasurement {self.property_name}={self.value_number} {self.unit}>"
