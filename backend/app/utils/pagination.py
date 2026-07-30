"""Shared pagination helpers."""

from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class PaginationParams(BaseModel):
    """Query parameters accepted by every list endpoint."""

    page: int = 1
    size: int = 20
    sort_by: str | None = None
    sort_order: str = "asc"  # "asc" | "desc"


class PaginatedResponse(BaseModel, Generic[T]):
    """Standard envelope for paginated list responses."""

    items: list[T]
    total: int
    page: int
    size: int
    pages: int
