"""LLM abstraction layer, multi-provider router, deterministic cache, and repair loop."""

from app.llm.cache import SQLiteLLMCache, llm_cache
from app.llm.parser import execute_repair_loop, inject_schema, parse_and_validate
from app.llm.providers import LLMProvider, NvidiaProvider, OllamaProvider, OpenRouterProvider
from app.llm.router import LLMRouter, llm_router
from app.llm.schemas import (
    LLMBaseError,
    LLMCacheMissError,
    LLMProviderError,
    LLMResponse,
    LLMStructuredOutputError,
    RawCompletionResult,
    SensitiveDataRoutingError,
    TokenUsage,
)
from app.llm.telemetry import LLMTelemetry, llm_telemetry

__all__ = [
    "LLMBaseError",
    "LLMCacheMissError",
    "LLMProvider",
    "LLMProviderError",
    "LLMResponse",
    "LLMRouter",
    "LLMStructuredOutputError",
    "LLMTelemetry",
    "NvidiaProvider",
    "OllamaProvider",
    "OpenRouterProvider",
    "RawCompletionResult",
    "SQLiteLLMCache",
    "SensitiveDataRoutingError",
    "TokenUsage",
    "execute_repair_loop",
    "inject_schema",
    "llm_cache",
    "llm_router",
    "llm_telemetry",
    "parse_and_validate",
]
