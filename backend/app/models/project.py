"""Project model — top-level organizational unit."""

import uuid

from sqlalchemy import Column, Date, DateTime, ForeignKey, JSON, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class Project(Base):
    __tablename__ = "projects"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    name = Column(String(300), nullable=False, index=True)
    description = Column(Text)
    status = Column(String(30), default="active")  # active, completed, archived
    start_date = Column(Date)
    end_date = Column(Date)
    owner_id = Column(Uuid, ForeignKey("users.id"))
    members_legacy = Column("members", JSON, default=list)
    metadata_ = Column("metadata", JSON, default=dict)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    owner = relationship("User", foreign_keys=[owner_id], lazy="selectin")
    experiments = relationship("Experiment", back_populates="project", cascade="all, delete-orphan")
    materials = relationship("Material", back_populates="project", foreign_keys="Material.project_id")
    members = relationship(
        "ProjectMember",
        back_populates="project",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Project {self.name}>"


class ProjectMember(Base):
    __tablename__ = "project_members"
    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "user_id",
            name="uq_project_members_project_user",
        ),
    )

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    project_id = Column(
        Uuid,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role = Column(String(20), nullable=False)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    project = relationship("Project", back_populates="members")
    user = relationship("User", lazy="selectin")
