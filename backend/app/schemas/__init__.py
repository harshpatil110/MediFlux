"""Shared Pydantic request and response schemas."""

from app.schemas.common import ErrorDetail, ErrorResponse, PaginatedResponse, PaginationParams

__all__ = ["ErrorDetail", "ErrorResponse", "PaginatedResponse", "PaginationParams"]
