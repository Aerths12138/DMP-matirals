"""Project-scoped metadata templates and controlled unit definitions."""

import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, JSON, String, Text, UniqueConstraint, Uuid
from sqlalchemy.sql import func

from app.database import Base


class MetadataTemplate(Base):
    __tablename__ = "metadata_templates"
    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "entity_type",
            "name",
            name="uq_metadata_templates_project_entity_name",
        ),
    )

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    project_id = Column(
        Uuid,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name = Column(String(200), nullable=False)
    entity_type = Column(String(30), nullable=False, index=True)
    description = Column(Text)
    fields = Column(JSON, nullable=False, default=list)
    is_active = Column(Boolean, nullable=False, default=True)
    created_by = Column(Uuid, ForeignKey("users.id"))
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class UnitDefinition(Base):
    __tablename__ = "unit_definitions"
    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "symbol",
            name="uq_unit_definitions_project_symbol",
        ),
    )

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    project_id = Column(
        Uuid,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    symbol = Column(String(50), nullable=False)
    name = Column(String(100), nullable=False)
    quantity_type = Column(String(100), nullable=False)
    description = Column(Text)
    is_active = Column(Boolean, nullable=False, default=True)
    created_by = Column(Uuid, ForeignKey("users.id"))
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
