"""Custom domain exception classes for MediFlux."""

from typing import Any


class MediFluxError(Exception):
    """Base exception for all MediFlux domain errors."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ConfigurationError(MediFluxError):
    """Raised when required configuration or environment variables are missing."""


class DatabaseError(MediFluxError):
    """Raised when a Supabase/PostgreSQL database operation fails."""


class LLMProviderError(MediFluxError):
    """Raised when an LLM provider request fails or exhausts retries."""


class SensitiveDataRoutingError(MediFluxError):
    """Raised when a sensitive query fails on local Ollama, strictly forbidding external cloud fallback."""

    status_code: int = 503
    code: str = "SOVEREIGN_LOCAL_MODEL_OFFLINE"


class SovereignLLMOfflineError(SensitiveDataRoutingError):
    """Raised when a sensitive query fails on local Ollama, strictly forbidding external cloud fallback."""

    status_code: int = 503
    code: str = "SOVEREIGN_LOCAL_MODEL_OFFLINE"

    def __init__(
        self,
        message: str = "Local sovereign LLM is offline or unreachable. Cloud fallback is strictly prohibited for sensitive data.",
        details: dict[str, Any] | None = None,
        status_code: int = 503,
        code: str = "SOVEREIGN_LOCAL_MODEL_OFFLINE",
    ) -> None:
        super().__init__(message, details)
        self.status_code = status_code
        self.code = code


class AgentExecutionError(MediFluxError):
    """Raised when an autonomous agent graph execution encounters an unrecoverable state."""


class ModuleSecurityViolation(MediFluxError):
    """Raised when dynamic code violates static AST safety guardrails."""


class EntityNotFoundError(MediFluxError):
    """Raised when a requested resource is not found."""

