"""RBAC: Role and Permission models."""

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Table, Text
from sqlalchemy.orm import relationship

from app.database import Base

role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column(
        "role_id",
        Integer,
        ForeignKey("roles.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "permission_id",
        Integer,
        ForeignKey("permissions.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class Role(Base):
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True)
    name = Column(String(50), unique=True, nullable=False)
    description = Column(Text)

    permissions = relationship("Permission", secondary=role_permissions, lazy="selectin")
    users = relationship("User", back_populates="role")

    def __repr__(self) -> str:
        return f"<Role {self.name}>"


class Permission(Base):
    __tablename__ = "permissions"

    id = Column(Integer, primary_key=True)
    codename = Column(String(100), unique=True, nullable=False)
    description = Column(Text)

    def __repr__(self) -> str:
        return f"<Permission {self.codename}>"
