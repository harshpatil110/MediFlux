"""LLM Provider adapters for NVIDIA NIM, OpenRouter, and Ollama."""

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from typing import Any

import httpx

from app.core.config import settings
from app.llm.schemas import LLMProviderError, RawCompletionResult

logger = logging.getLogger("mediflux.llm.providers")


class LLMProvider(ABC):
    """Abstract base class for all LLM provider adapters."""

    def __init__(
        self,
        base_url: str,
        timeout_seconds: float = 30.0,
        max_concurrency: int = 5,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.semaphore = asyncio.Semaphore(max_concurrency)

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Identifier name of the provider."""

    @abstractmethod
    async def complete(
        self,
        messages: list[dict[str, str]],
        model: str,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> RawCompletionResult:
        """Execute chat completion request asynchronously."""


class NvidiaProvider(LLMProvider):
    """NVIDIA NIM hosted API provider adapter."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = "https://integrate.api.nvidia.com/v1",
        timeout_seconds: float = 30.0,
        max_concurrency: int = 5,
    ) -> None:
        super().__init__(base_url=base_url, timeout_seconds=timeout_seconds, max_concurrency=max_concurrency)
        self.api_key = api_key or settings.NVIDIA_API_KEY

    @property
    def provider_name(self) -> str:
        return "nvidia"

    async def complete(
        self,
        messages: list[dict[str, str]],
        model: str,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> RawCompletionResult:
        if not self.api_key:
            raise LLMProviderError(
                provider=self.provider_name,
                status_code=None,
                message="NVIDIA_API_KEY is not configured",
            )

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        url = f"{self.base_url}/chat/completions"

        async with self.semaphore:
            start_time = time.perf_counter()
            try:
                async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                    response = await client.post(url, headers=headers, json=payload)
            except httpx.TimeoutException as exc:
                raise LLMProviderError(
                    provider=self.provider_name,
                    status_code=408,
                    message=f"Request timed out after {self.timeout_seconds}s",
                ) from exc
            except httpx.RequestError as exc:
                raise LLMProviderError(
                    provider=self.provider_name,
                    status_code=None,
                    message=f"Network connection failed: {exc}",
                ) from exc

            latency_ms = (time.perf_counter() - start_time) * 1000.0

            if response.status_code == 429:
                raise LLMProviderError(
                    provider=self.provider_name,
                    status_code=429,
                    message=f"Rate limit exceeded (429): {response.text}",
                )
            if response.status_code >= 500:
                raise LLMProviderError(
                    provider=self.provider_name,
                    status_code=response.status_code,
                    message=f"Server error ({response.status_code}): {response.text}",
                )
            if response.status_code != 200:
                raise LLMProviderError(
                    provider=self.provider_name,
                    status_code=response.status_code,
                    message=f"Unexpected status ({response.status_code}): {response.text}",
                )

            data = response.json()
            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})

            return RawCompletionResult(
                content=content,
                provider=self.provider_name,
                model=model,
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
                total_tokens=usage.get("total_tokens", 0),
                latency_ms=latency_ms,
            )


class OpenRouterProvider(LLMProvider):
    """OpenRouter free-tier provider adapter."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = "https://openrouter.ai/api/v1",
        timeout_seconds: float = 30.0,
        max_concurrency: int = 5,
    ) -> None:
        super().__init__(base_url=base_url, timeout_seconds=timeout_seconds, max_concurrency=max_concurrency)
        self.api_key = api_key or settings.OPENROUTER_API_KEY

    @property
    def provider_name(self) -> str:
        return "openrouter"

    async def complete(
        self,
        messages: list[dict[str, str]],
        model: str,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> RawCompletionResult:
        if not self.api_key:
            raise LLMProviderError(
                provider=self.provider_name,
                status_code=None,
                message="OPENROUTER_API_KEY is not configured",
            )

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/mediflux/mediflux",
            "X-Title": "MediFlux",
        }
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        url = f"{self.base_url}/chat/completions"

        async with self.semaphore:
            start_time = time.perf_counter()
            try:
                async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                    response = await client.post(url, headers=headers, json=payload)
            except httpx.TimeoutException as exc:
                raise LLMProviderError(
                    provider=self.provider_name,
                    status_code=408,
                    message=f"Request timed out after {self.timeout_seconds}s",
                ) from exc
            except httpx.RequestError as exc:
                raise LLMProviderError(
                    provider=self.provider_name,
                    status_code=None,
                    message=f"Network connection failed: {exc}",
                ) from exc

            latency_ms = (time.perf_counter() - start_time) * 1000.0

            if response.status_code == 429:
                raise LLMProviderError(
                    provider=self.provider_name,
                    status_code=429,
                    message=f"Rate limit exceeded (429): {response.text}",
                )
            if response.status_code >= 500:
                raise LLMProviderError(
                    provider=self.provider_name,
                    status_code=response.status_code,
                    message=f"Server error ({response.status_code}): {response.text}",
                )
            if response.status_code != 200:
                raise LLMProviderError(
                    provider=self.provider_name,
                    status_code=response.status_code,
                    message=f"Unexpected status ({response.status_code}): {response.text}",
                )

            data = response.json()
            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})

            return RawCompletionResult(
                content=content,
                provider=self.provider_name,
                model=model,
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
                total_tokens=usage.get("total_tokens", 0),
                latency_ms=latency_ms,
            )


class OllamaProvider(LLMProvider):
    """Local Ollama instance adapter for privacy-isolated processing."""

    def __init__(
        self,
        base_url: str | None = None,
        timeout_seconds: float = 60.0,
        max_concurrency: int = 2,
    ) -> None:
        url = base_url or settings.OLLAMA_BASE_URL
        super().__init__(base_url=url, timeout_seconds=timeout_seconds, max_concurrency=max_concurrency)

    @property
    def provider_name(self) -> str:
        return "ollama"

    async def complete(
        self,
        messages: list[dict[str, str]],
        model: str,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> RawCompletionResult:
        headers = {"Content-Type": "application/json"}
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature},
        }
        if max_tokens is not None:
            payload["options"]["num_predict"] = max_tokens

        url = f"{self.base_url}/chat/completions"

        async with self.semaphore:
            start_time = time.perf_counter()
            try:
                async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                    response = await client.post(url, headers=headers, json=payload)
            except httpx.TimeoutException as exc:
                raise LLMProviderError(
                    provider=self.provider_name,
                    status_code=408,
                    message=f"Ollama request timed out after {self.timeout_seconds}s",
                ) from exc
            except httpx.RequestError as exc:
                raise LLMProviderError(
                    provider=self.provider_name,
                    status_code=None,
                    message=f"Ollama local connection failed: {exc}",
                ) from exc

            latency_ms = (time.perf_counter() - start_time) * 1000.0

            if response.status_code >= 400:
                raise LLMProviderError(
                    provider=self.provider_name,
                    status_code=response.status_code,
                    message=f"Ollama error ({response.status_code}): {response.text}",
                )

            data = response.json()
            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})

            # Estimate token usage if Ollama doesn't return usage
            prompt_tokens = usage.get("prompt_tokens", 0)
            completion_tokens = usage.get("completion_tokens", 0)
            if not prompt_tokens and not completion_tokens:
                prompt_tokens = sum(len(m.get("content", "").split()) for m in messages)
                completion_tokens = len(content.split())

            return RawCompletionResult(
                content=content,
                provider=self.provider_name,
                model=model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
                latency_ms=latency_ms,
            )
