"""Deterministic LLM fault injection harness for chaos testing and resilient failover verification."""

import logging
from collections.abc import Generator
from contextlib import contextmanager

from app.llm.schemas import LLMProviderError

logger = logging.getLogger("mediflux.llm.fault")

# Active fault registry: provider -> error_type
_injected_faults: dict[str, str] = {}


def get_injected_fault(provider: str) -> str | None:
    """Retrieve any active injected fault for the specified provider."""
    return _injected_faults.get(provider.lower().strip())


def check_and_raise_fault(provider: str) -> None:
    """Check if an injected fault is active for the provider and raise the corresponding exception."""
    fault = get_injected_fault(provider)
    if not fault:
        return

    prov = provider.lower().strip()
    fault_norm = fault.lower().strip()

    if fault_norm == "rate_limit_429":
        raise LLMProviderError(
            provider=prov,
            status_code=429,
            message=f"Injected fault: HTTP 429 Rate Limit for provider '{prov}'",
            details={"injected": True, "error_type": "rate_limit_429"},
        )
    elif fault_norm == "server_error_500":
        raise LLMProviderError(
            provider=prov,
            status_code=500,
            message=f"Injected fault: HTTP 500 Internal Server Error for provider '{prov}'",
            details={"injected": True, "error_type": "server_error_500"},
        )
    elif fault_norm == "bad_gateway_502":
        raise LLMProviderError(
            provider=prov,
            status_code=502,
            message=f"Injected fault: HTTP 502 Bad Gateway for provider '{prov}'",
            details={"injected": True, "error_type": "bad_gateway_502"},
        )
    elif fault_norm == "service_unavailable_503":
        raise LLMProviderError(
            provider=prov,
            status_code=503,
            message=f"Injected fault: HTTP 503 Service Unavailable for provider '{prov}'",
            details={"injected": True, "error_type": "service_unavailable_503"},
        )
    elif fault_norm == "timeout":
        raise LLMProviderError(
            provider=prov,
            status_code=408,
            message=f"Injected fault: Request timeout for provider '{prov}'",
            details={"injected": True, "error_type": "timeout"},
        )
    elif fault_norm == "connect_error":
        raise LLMProviderError(
            provider=prov,
            status_code=503,
            message=f"Injected fault: Connection refused for provider '{prov}'",
            details={"injected": True, "error_type": "connect_error"},
        )
    elif fault_norm == "kill":
        raise LLMProviderError(
            provider=prov,
            status_code=500,
            message=f"Injected fault: Process killed abruptly for provider '{prov}'",
            details={"injected": True, "error_type": "kill"},
        )
    else:
        raise LLMProviderError(
            provider=prov,
            status_code=500,
            message=f"Injected fault: Generic failure '{fault}' for provider '{prov}'",
            details={"injected": True, "error_type": fault},
        )


@contextmanager
def inject_llm_fault(provider: str, error_type: str) -> Generator[None, None, None]:
    """Context manager to deterministically inject simulated provider failures.

    Supported providers:
        - "nvidia"
        - "openrouter"
        - "ollama"

    Supported error types:
        - "rate_limit_429"
        - "server_error_500"
        - "bad_gateway_502"
        - "service_unavailable_503"
        - "timeout"
        - "connect_error"
        - "kill"
    """
    prov = provider.lower().strip()
    prev_fault = _injected_faults.get(prov)
    _injected_faults[prov] = error_type
    logger.info("Fault injected: provider=%s error_type=%s", prov, error_type)
    try:
        yield
    finally:
        if prev_fault is not None:
            _injected_faults[prov] = prev_fault
        else:
            _injected_faults.pop(prov, None)
        logger.info("Fault cleared: provider=%s", prov)


def clear_all_faults() -> None:
    """Clear all active fault injections."""
    _injected_faults.clear()
