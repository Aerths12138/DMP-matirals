"""Processing method model — how a material or sample was prepared/treated."""

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, JSON, String, Text, Uuid
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class ProcessingMethod(Base):
    __tablename__ = "processing_methods"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    material_id = Column(Uuid, ForeignKey("materials.id", ondelete="CASCADE"), index=True)
    sample_id = Column(Uuid, ForeignKey("samples.id", ondelete="CASCADE"), index=True)
    method_type = Column(String(100), nullable=False)  # annealing, sintering, electrospinning, 3D_printing, hot_pressing
    parameters = Column(JSON, nullable=False, default=dict)
    # {"temperature":800,"temperature_unit":"C","duration":2,"duration_unit":"h","atmosphere":"Ar"}
    equipment = Column(String(300))
    description = Column(Text)
    order_in_chain = Column(Integer)
    parent_step_id = Column(Uuid, ForeignKey("processing_methods.id"))
    created_by = Column(Uuid, ForeignKey("users.id"))
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    material = relationship("Material", back_populates="processing_methods")
    sample = relationship("Sample", back_populates="processing_methods")
    creator = relationship("User", foreign_keys=[created_by], lazy="selectin")

    def __repr__(self) -> str:
        return f"<ProcessingMethod {self.method_type}>"
