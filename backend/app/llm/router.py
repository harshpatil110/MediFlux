"""Intelligent multi-provider LLM router with automatic failover and caching."""

import logging

from app.core.config import settings
from app.core.errors import LLMProviderError
from app.llm.cache import llm_cache
from app.llm.providers import LLMProvider, NvidiaProvider, OllamaProvider, OpenRouterProvider
from app.llm.schemas import ChatCompletionRequest, ChatCompletionResponse

logger = logging.getLogger(__name__)


class LLMRouter:
    """Manages routing between NVIDIA NIM, OpenRouter, and Ollama with fallback."""

    def __init__(self) -> None:
        self.providers: dict[str, LLMProvider] = {
            "nvidia": NvidiaProvider(),
            "openrouter": OpenRouterProvider(),
            "ollama": OllamaProvider(),
        }

    async def complete(
        self,
        request: ChatCompletionRequest,
        preferred_provider: str | None = None,
    ) -> ChatCompletionResponse:
        """Route completion through cache, primary provider, and fallbacks."""
        # 1. Check cache
        raw_messages = [m.model_dump() for m in request.messages]
        cached_result = llm_cache.get(request.model, raw_messages, request.temperature)
        if cached_result:
            return ChatCompletionResponse(**cached_result, cached=True)

        # 2. Determine provider order
        provider_order: list[str] = []
        if preferred_provider and preferred_provider in self.providers:
            provider_order.append(preferred_provider)

        # Default fallback order based on available keys
        if settings.NVIDIA_API_KEY and "nvidia" not in provider_order:
            provider_order.append("nvidia")
        if settings.OPENROUTER_API_KEY and "openrouter" not in provider_order:
            provider_order.append("openrouter")
        if "ollama" not in provider_order:
            provider_order.append("ollama")

        last_error: Exception | None = None
        for prov_name in provider_order:
            provider = self.providers.get(prov_name)
            if not provider:
                continue
            try:
                logger.info("Dispatching LLM prompt to %s (model: %s)", prov_name, request.model)
                response = await provider.complete(request)
                # Store in cache
                llm_cache.set(
                    request.model,
                    raw_messages,
                    request.temperature,
                    response.model_dump(),
                )
                return response
            except Exception as exc:
                logger.warning("Provider %s failed: %s. Falling back...", prov_name, exc)
                last_error = exc

        raise LLMProviderError(
            f"All available LLM providers failed. Last error: {last_error}"
        )


llm_router = LLMRouter()
