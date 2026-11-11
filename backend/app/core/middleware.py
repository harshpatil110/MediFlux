"""Custom middleware for MediFlux API."""

import uuid
from collections.abc import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.logging import set_correlation_id


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Middleware ensuring every request has an X-Correlation-ID header and context."""

    async def dispatch(self, request: Request, call_next: Callable[[Request], Response]) -> Response:
        correlation_id = request.headers.get("X-Correlation-ID")
        if not correlation_id:
            correlation_id = str(uuid.uuid4())

        request.state.correlation_id = correlation_id
        set_correlation_id(correlation_id)

        try:
            response = await call_next(request)
        except Exception as exc:
            # Capture any unhandled exception that escapes routing and format standard 500 error
            from app.core.handlers import unhandled_exception_handler
            response = await unhandled_exception_handler(request, exc)

        response.headers["X-Correlation-ID"] = correlation_id
        return response
