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


class AgentExecutionError(MediFluxError):
    """Raised when an autonomous agent graph execution encounters an unrecoverable state."""


class ModuleSecurityViolation(MediFluxError):
    """Raised when dynamic code violates static AST safety guardrails."""


class EntityNotFoundError(MediFluxError):
    """Raised when a requested resource is not found."""

