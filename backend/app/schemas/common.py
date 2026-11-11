"""Common API schemas including pagination, envelope, and error formats."""

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginationParams(BaseModel):
    """Standard cursor-based pagination query parameters."""

    limit: int = Field(default=20, ge=1, le=100, description="Max number of items to return")
    cursor: str | None = Field(default=None, description="Cursor for next page retrieval")


class PaginatedResponse(BaseModel, Generic[T]):
    """Standardized generic paginated response container."""

    items: list[T]
    next_cursor: str | None = None
    has_more: bool = False
    total_count: int | None = None


class ErrorDetail(BaseModel):
    """Detailed error object representation."""

    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    """Root error response schema matching { 'error': { ... } }."""

    error: ErrorDetail
