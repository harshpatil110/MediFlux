"""Custom application domain exceptions."""

from typing import Any


class AppException(Exception):
    """Base application exception for all standardized API errors."""

    status_code: int = 500
    code: str = "INTERNAL_SERVER_ERROR"

    def __init__(
        self,
        message: str = "An unexpected error occurred",
        code: str | None = None,
        status_code: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code
        if status_code is not None:
            self.status_code = status_code
        self.details = details or {}


class NotFoundError(AppException):
    """Resource not found exception."""

    status_code = 404
    code = "NOT_FOUND"

    def __init__(self, message: str = "Resource not found", details: dict[str, Any] | None = None) -> None:
        super().__init__(message=message, code=self.code, status_code=self.status_code, details=details)


class UnauthorizedError(AppException):
    """Authentication required or invalid credentials."""

    status_code = 401
    code = "UNAUTHORIZED"

    def __init__(self, message: str = "Authentication required", details: dict[str, Any] | None = None) -> None:
        super().__init__(message=message, code=self.code, status_code=self.status_code, details=details)


class ForbiddenError(AppException):
    """Action forbidden for the authenticated user/role."""

    status_code = 403
    code = "FORBIDDEN"

    def __init__(self, message: str = "Access forbidden", details: dict[str, Any] | None = None) -> None:
        super().__init__(message=message, code=self.code, status_code=self.status_code, details=details)


class ValidationError(AppException):
    """Input or entity validation error."""

    status_code = 422
    code = "VALIDATION_ERROR"

    def __init__(self, message: str = "Validation failed", details: dict[str, Any] | None = None) -> None:
        super().__init__(message=message, code=self.code, status_code=self.status_code, details=details)


class ConflictError(AppException):
    """Resource conflict or duplicate entry."""

    status_code = 409
    code = "CONFLICT"

    def __init__(self, message: str = "Resource conflict", details: dict[str, Any] | None = None) -> None:
        super().__init__(message=message, code=self.code, status_code=self.status_code, details=details)

