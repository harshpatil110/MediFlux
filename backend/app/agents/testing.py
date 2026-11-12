"""Deterministic test harness and fake LLM for testing agents and LangGraph workflows."""

import logging
from collections import deque
from typing import Any, TypeVar

from app.llm.schemas import LLMResponse

logger = logging.getLogger("mediflux.agents.testing")

T = TypeVar("T")


class FakeLLM:
    """Mock LLM router for deterministic agent unit tests without network calls."""

    def __init__(self, responses: list[Any] | None = None) -> None:
        self.queue: deque[Any] = deque(responses or [])
        self.history: list[dict[str, Any]] = []

    def queue_response(self, response: Any) -> None:
        """Add a response to the queue."""
        self.queue.append(response)

    def queue_responses(self, responses: list[Any]) -> None:
        """Add multiple responses to the queue."""
        self.queue.extend(responses)

    async def complete(
        self,
        agent: str,
        messages: list[dict[str, str]],
        response_model: type[T],
        sensitivity: str = "normal",
        task_type: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        max_repairs: int = 2,
    ) -> LLMResponse[T]:
        """Return the next pre-scripted decision from the queue wrapped in an LLMResponse."""
        self.history.append({
            "agent": agent,
            "messages": list(messages),
            "response_model": response_model,
        })

        if not self.queue:
            raise RuntimeError(
                f"FakeLLM queue exhausted for agent '{agent}'. No pre-scripted decision available."
            )

        data = self.queue.popleft()

        return LLMResponse[T](
            data=data,
            provider="fake_llm",
            model="fake-deterministic-model",
            prompt_tokens=15,
            completion_tokens=10,
            total_tokens=25,
            latency_ms=2.5,
            cached=False,
            raw_content=str(data),
        )
