"""User-related Pydantic schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class UserBase(BaseModel):
    username: str = Field(min_length=3, max_length=150)
    email: EmailStr
    display_name: str | None = Field(default=None, max_length=200)
    department: str | None = Field(default=None, max_length=200)


class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=128)


class UserUpdate(BaseModel):
    email: EmailStr | None = None
    display_name: str | None = None
    department: str | None = None
    is_active: bool | None = None


class UserResponse(UserBase):
    id: uuid.UUID
    is_active: bool
    is_approved: bool = False
    role_id: int | None
    role_name: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class UserListResponse(UserBase):
    id: uuid.UUID
    is_active: bool
    is_approved: bool = False
    role_id: int | None
    role_name: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class UserDirectoryItem(BaseModel):
    id: uuid.UUID
    username: str
    display_name: str | None = None
    department: str | None = None

    model_config = {"from_attributes": True}


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str = Field(min_length=8, max_length=128)


class ChangeRoleRequest(BaseModel):
    role_id: int


class ApproveUserRequest(BaseModel):
    role_id: int
