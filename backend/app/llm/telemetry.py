"""Telemetry tracking and logging for LLM invocations."""

import logging
from typing import Any

from app.core.logging import get_correlation_id
from app.llm.schemas import LLMResponse

logger = logging.getLogger("mediflux.llm.telemetry")


class LLMTelemetry:
    """Manages telemetry recording and metrics collection for LLM interactions."""

    def __init__(self) -> None:
        self.records: list[dict[str, Any]] = []

    def record(self, response: LLMResponse[Any], agent: str, task_type: str | None = None) -> dict[str, Any]:
        """Record and log telemetry metrics for an LLM response."""
        correlation_id = get_correlation_id()
        metric_record = {
            "correlation_id": correlation_id,
            "agent": agent,
            "task_type": task_type or "general",
            "provider": response.provider,
            "model": response.model,
            "prompt_tokens": response.prompt_tokens,
            "completion_tokens": response.completion_tokens,
            "total_tokens": response.total_tokens,
            "latency_ms": response.latency_ms,
            "cached": response.cached,
        }

        self.records.append(metric_record)

        logger.info(
            "LLM Telemetry | agent=%s | provider=%s | model=%s | tokens=%d (in: %d, out: %d) | "
            "latency=%.2fms | cached=%s | corr_id=%s",
            agent,
            response.provider,
            response.model,
            response.total_tokens,
            response.prompt_tokens,
            response.completion_tokens,
            response.latency_ms,
            response.cached,
            correlation_id,
        )

        return metric_record

    def get_recent(self, limit: int = 50) -> list[dict[str, Any]]:
        """Retrieve recent telemetry records."""
        return self.records[-limit:]


llm_telemetry = LLMTelemetry()

