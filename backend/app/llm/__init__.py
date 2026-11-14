"""LLM abstraction layer, multi-provider router, deterministic cache, and repair loop."""

from app.core.errors import SovereignLLMOfflineError
from app.llm.cache import SQLiteLLMCache, llm_cache
from app.llm.fault import check_and_raise_fault, clear_all_faults, inject_llm_fault
from app.llm.parser import (
    execute_repair_loop,
    inject_schema,
    parse_and_repair_llm_json,
    parse_and_validate,
)
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
    "SovereignLLMOfflineError",
    "TokenUsage",
    "check_and_raise_fault",
    "clear_all_faults",
    "execute_repair_loop",
    "inject_llm_fault",
    "inject_schema",
    "llm_cache",
    "llm_router",
    "llm_telemetry",
    "parse_and_repair_llm_json",
    "parse_and_validate",
]
