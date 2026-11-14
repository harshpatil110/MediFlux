"""Pydantic schemas and exception definitions for LLM routing and telemetry."""

from typing import Any, Generic, TypeVar

from pydantic import BaseModel

from app.core.errors import MediFluxError, SensitiveDataRoutingError, SovereignLLMOfflineError

T = TypeVar("T")


# -----------------------------------------------------------------------------
# 1. Custom LLM Exceptions
# -----------------------------------------------------------------------------
class LLMBaseError(MediFluxError):
    """Base exception for all LLM routing and provider failures."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class LLMProviderError(LLMBaseError):
    """Raised when an individual LLM provider fails (e.g. 429, 5xx, timeout)."""

    def __init__(
        self,
        provider: str,
        status_code: int | None = None,
        message: str = "",
        details: dict[str, Any] | None = None,
    ) -> None:
        full_msg = f"Provider [{provider}] failed (status: {status_code}): {message}"
        super().__init__(full_msg, details)
        self.provider = provider
        self.status_code = status_code


class LLMStructuredOutputError(LLMBaseError):
    """Raised when LLM output fails schema validation even after repair loop attempts."""

    def __init__(
        self,
        message: str,
        raw_output: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, details)
        self.raw_output = raw_output


class LLMCacheMissError(LLMBaseError):
    """Raised when a cache key misses in 'replay' mode."""


# -----------------------------------------------------------------------------
# 2. Telemetry & Response Containers
# -----------------------------------------------------------------------------
class TokenUsage(BaseModel):
    """Token consumption telemetry."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class RawCompletionResult(BaseModel):
    """Intermediate provider completion container."""

    content: str
    provider: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    latency_ms: float = 0.0


class LLMResponse(BaseModel, Generic[T]):
    """Standardized response container returning validated model instance and telemetry."""

    data: T
    provider: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    latency_ms: float = 0.0
    cached: bool = False
    raw_content: str | None = None


__all__ = [
    "LLMBaseError",
    "LLMCacheMissError",
    "LLMProviderError",
    "LLMResponse",
    "LLMStructuredOutputError",
    "RawCompletionResult",
    "SensitiveDataRoutingError",
    "SovereignLLMOfflineError",
    "TokenUsage",
]
