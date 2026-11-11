"""LLM Provider implementations for NVIDIA NIM, OpenRouter, and Ollama."""

import uuid
from abc import ABC, abstractmethod

import httpx

from app.core.config import settings
from app.core.errors import LLMProviderError
from app.llm.schemas import ChatCompletionRequest, ChatCompletionResponse, TokenUsage


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Name of the provider."""

    @abstractmethod
    async def complete(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
        """Execute chat completion request asynchronously."""


class NvidiaProvider(LLMProvider):
    """NVIDIA NIM hosted API provider."""

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or settings.NVIDIA_API_KEY
        self.base_url = "https://integrate.api.nvidia.com/v1"

    @property
    def provider_name(self) -> str:
        return "nvidia"

    async def complete(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
        if not self.api_key:
            raise LLMProviderError("NVIDIA_API_KEY is not configured")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": request.model,
            "messages": [m.model_dump() for m in request.messages],
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                usage_data = data.get("usage", {})
                return ChatCompletionResponse(
                    id=data.get("id", str(uuid.uuid4())),
                    provider=self.provider_name,
                    model=request.model,
                    content=content,
                    usage=TokenUsage(
                        prompt_tokens=usage_data.get("prompt_tokens", 0),
                        completion_tokens=usage_data.get("completion_tokens", 0),
                        total_tokens=usage_data.get("total_tokens", 0),
                    ),
                )
            except Exception as exc:
                raise LLMProviderError(f"NVIDIA API failure: {exc}") from exc


class OpenRouterProvider(LLMProvider):
    """OpenRouter free-tier provider."""

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or settings.OPENROUTER_API_KEY
        self.base_url = "https://openrouter.ai/api/v1"

    @property
    def provider_name(self) -> str:
        return "openrouter"

    async def complete(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
        if not self.api_key:
            raise LLMProviderError("OPENROUTER_API_KEY is not configured")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": request.model,
            "messages": [m.model_dump() for m in request.messages],
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                usage_data = data.get("usage", {})
                return ChatCompletionResponse(
                    id=data.get("id", str(uuid.uuid4())),
                    provider=self.provider_name,
                    model=request.model,
                    content=content,
                    usage=TokenUsage(
                        prompt_tokens=usage_data.get("prompt_tokens", 0),
                        completion_tokens=usage_data.get("completion_tokens", 0),
                        total_tokens=usage_data.get("total_tokens", 0),
                    ),
                )
            except Exception as exc:
                raise LLMProviderError(f"OpenRouter API failure: {exc}") from exc


class OllamaProvider(LLMProvider):
    """Local Ollama instance provider."""

    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = base_url or settings.OLLAMA_BASE_URL

    @property
    def provider_name(self) -> str:
        return "ollama"

    async def complete(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
        payload = {
            "model": request.model,
            "messages": [m.model_dump() for m in request.messages],
            "options": {"temperature": request.temperature},
            "stream": False,
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            try:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                return ChatCompletionResponse(
                    id=str(uuid.uuid4()),
                    provider=self.provider_name,
                    model=request.model,
                    content=content,
                )
            except Exception as exc:
                raise LLMProviderError(f"Ollama local API failure: {exc}") from exc
