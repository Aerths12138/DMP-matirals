"""Shared schemas: pagination, filtering, sorting."""

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginationParams(BaseModel):
    """Accepted by every list endpoint."""

    page: int = Field(default=1, ge=1)
    size: int = Field(default=20, ge=1, le=2000)
    sort_by: str | None = None
    sort_order: str = Field(default="asc", pattern=r"^(asc|desc)$")


class PaginatedResponse(BaseModel, Generic[T]):
    """Standard envelope for paginated list responses."""

    items: list[T]
    total: int
    page: int
    size: int
    pages: int
