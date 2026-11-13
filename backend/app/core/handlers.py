"""Global API exception handlers enforcing standard error response schemas."""

import logging
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import HTTPException as FastAPIHTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.exceptions import AppException

logger = logging.getLogger(__name__)


def build_error_response(
    status_code: int,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    """Construct standardized JSON error response."""
    return JSONResponse(
        status_code=status_code,
        headers=headers,
        content={
            "detail": message,
            "error": {
                "code": code,
                "message": message,
                "details": details or {},
            },
        },
    )


async def app_exception_handler(_: Request, exc: AppException) -> JSONResponse:
    """Handle custom domain AppException instances."""
    logger.warning("AppException [%s]: %s (details: %s)", exc.code, exc.message, exc.details)
    return build_error_response(
        status_code=exc.status_code,
        code=exc.code,
        message=exc.message,
        details=exc.details,
    )


async def http_exception_handler(_: Request, exc: StarletteHTTPException | FastAPIHTTPException) -> JSONResponse:
    """Handle standard Starlette / FastAPI HTTPException instances."""
    code_map = {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        405: "METHOD_NOT_ALLOWED",
        409: "CONFLICT",
        422: "UNPROCESSABLE_ENTITY",
        429: "TOO_MANY_REQUESTS",
        500: "INTERNAL_SERVER_ERROR",
    }
    code = code_map.get(exc.status_code, f"HTTP_{exc.status_code}")
    message = str(exc.detail) if exc.detail else "An error occurred"
    details: dict[str, Any] = {}
    if isinstance(exc.detail, dict):
        details = exc.detail
        message = details.get("message", "HTTP Error")

    headers = getattr(exc, "headers", None)
    return build_error_response(
        status_code=exc.status_code,
        code=code,
        message=message,
        details=details,
        headers=headers,
    )


async def validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    """Handle Pydantic / FastAPI request validation failures."""
    details = {"errors": exc.errors()}
    return build_error_response(
        status_code=422,
        code="VALIDATION_ERROR",
        message="Request parameter validation failed",
        details=details,
    )


async def unhandled_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected uncaught exceptions, masking stack traces in output."""
    logger.exception("Unhandled server error: %s", exc)
    return build_error_response(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        code="INTERNAL_SERVER_ERROR",
        message="An unexpected internal server error occurred",
        details={},
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register all global exception handlers onto FastAPI instance."""
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(FastAPIHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
