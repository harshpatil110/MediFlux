"""Multi-provider LLM router supporting sensitivity isolation, fallback chains, and structured outputs."""

import logging
from pathlib import Path
from typing import Any, Literal, TypeVar

import yaml

from app.core.config import settings
from app.llm.cache import llm_cache
from app.llm.parser import execute_repair_loop, inject_schema
from app.llm.providers import LLMProvider, NvidiaProvider, OllamaProvider, OpenRouterProvider
from app.llm.schemas import (
    LLMBaseError,
    LLMProviderError,
    LLMResponse,
    LLMStructuredOutputError,
    RawCompletionResult,
    SensitiveDataRoutingError,
)
from app.llm.telemetry import llm_telemetry

logger = logging.getLogger("mediflux.llm.router")

T = TypeVar("T")

DEFAULT_CONFIG: dict[str, Any] = {
    "default_fallback_chain": ["nvidia", "openrouter", "ollama"],
    "providers": {
        "nvidia": {
            "base_url": "https://integrate.api.nvidia.com/v1",
            "max_concurrency": 5,
            "timeout_seconds": 30,
        },
        "openrouter": {
            "base_url": "https://openrouter.ai/api/v1",
            "max_concurrency": 5,
            "timeout_seconds": 30,
        },
        "ollama": {
            "base_url": "http://localhost:11434/v1",
            "max_concurrency": 2,
            "timeout_seconds": 60,
        },
    },
    "agents": {
        "coding_agent": {
            "nvidia": "meta/llama-3.1-70b-instruct",
            "openrouter": "meta-llama/llama-3.1-70b-instruct:free",
            "ollama": "qwen2.5-coder:7b",
        },
        "analytics_agent": {
            "nvidia": "meta/llama-3.1-8b-instruct",
            "openrouter": "google/gemma-2-9b-it:free",
            "ollama": "llama3.2:latest",
        },
        "compliance_agent": {
            "nvidia": "meta/llama-3.1-70b-instruct",
            "openrouter": "meta-llama/llama-3.1-70b-instruct:free",
            "ollama": "llama3.2:latest",
        },
        "default": {
            "nvidia": "meta/llama-3.1-8b-instruct",
            "openrouter": "meta-llama/llama-3.1-8b-instruct:free",
            "ollama": "llama3.2:latest",
        },
    },
}


def load_agent_models_config(config_path: str | None = None) -> dict[str, Any]:
    """Load agent models and fallback chain configuration from YAML file or defaults."""
    target_path = config_path or settings.AGENT_MODELS_CONFIG_PATH
    candidates = [
        Path(target_path),
        Path("backend") / target_path,
        Path(__file__).parent.parent.parent / target_path,
        Path(__file__).parent.parent.parent.parent / target_path,
    ]

    for p in candidates:
        if p.is_file():
            try:
                with open(p, encoding="utf-8") as f:
                    loaded = yaml.safe_load(f)
                    if isinstance(loaded, dict):
                        logger.info("Loaded LLM router configuration from %s", p)
                        return loaded
            except Exception as exc:
                logger.warning("Failed to parse config at %s: %s", p, exc)

    logger.info("Using embedded default LLM router configuration")
    return DEFAULT_CONFIG


class LLMRouter:
    """Intelligent multi-provider LLM router with strict privacy boundaries and telemetry."""

    def __init__(self, config_path: str | None = None) -> None:
        self.config = load_agent_models_config(config_path)
        prov_cfg = self.config.get("providers", {})

        nvidia_cfg = prov_cfg.get("nvidia", {})
        openrouter_cfg = prov_cfg.get("openrouter", {})
        ollama_cfg = prov_cfg.get("ollama", {})

        self.providers: dict[str, LLMProvider] = {
            "nvidia": NvidiaProvider(
                base_url=nvidia_cfg.get("base_url", "https://integrate.api.nvidia.com/v1"),
                timeout_seconds=nvidia_cfg.get("timeout_seconds", 30.0),
                max_concurrency=nvidia_cfg.get("max_concurrency", 5),
            ),
            "openrouter": OpenRouterProvider(
                base_url=openrouter_cfg.get("base_url", "https://openrouter.ai/api/v1"),
                timeout_seconds=openrouter_cfg.get("timeout_seconds", 30.0),
                max_concurrency=openrouter_cfg.get("max_concurrency", 5),
            ),
            "ollama": OllamaProvider(
                base_url=ollama_cfg.get("base_url", settings.OLLAMA_BASE_URL),
                timeout_seconds=ollama_cfg.get("timeout_seconds", 60.0),
                max_concurrency=ollama_cfg.get("max_concurrency", 2),
            ),
        }

    def get_model_for_agent(self, agent: str, provider: str) -> str:
        """Resolve the model name for a specific agent and provider."""
        agent_models = self.config.get("agents", {}).get(agent, {})
        if provider in agent_models:
            return agent_models[provider]

        default_models = self.config.get("agents", {}).get("default", {})
        if provider in default_models:
            return default_models[provider]

        # Generic fallbacks
        fallbacks = {
            "nvidia": "meta/llama-3.1-8b-instruct",
            "openrouter": "meta-llama/llama-3.1-8b-instruct:free",
            "ollama": "llama3.2:latest",
        }
        return fallbacks.get(provider, "default-model")

    async def complete(
        self,
        agent: str,
        messages: list[dict[str, str]],
        response_model: type[T],
        sensitivity: Literal["normal", "sensitive"] = "normal",
        task_type: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        max_repairs: int = 2,
    ) -> LLMResponse[T]:
        """Execute chat completion with automatic schema injection, validation, and failover.

        - If sensitivity="sensitive": strictly routes to local Ollama. Failures raise
          SensitiveDataRoutingError and NEVER fail over to hosted providers.
        - If sensitivity="normal": routes along fallback chain (nvidia -> openrouter -> ollama).
        """
        # 1. Check persistent SQLite cache
        cache_key = llm_cache.compute_cache_key(agent, messages, response_model)
        cached_response = llm_cache.get(cache_key, response_model)
        if cached_response is not None:
            llm_telemetry.record(cached_response, agent, task_type)
            return cached_response

        # 2. Inject schema into prompt messages
        injected_messages = inject_schema(messages, response_model)

        # 3. Privacy-isolated execution for sensitive data
        if sensitivity == "sensitive":
            ollama_prov = self.providers.get("ollama")
            if not ollama_prov:
                raise SensitiveDataRoutingError("Ollama provider is not registered in router")

            ollama_model = self.get_model_for_agent(agent, "ollama")

            async def _call_ollama(msgs: list[dict[str, str]]) -> RawCompletionResult:
                return await ollama_prov.complete(
                    messages=msgs,
                    model=ollama_model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )

            try:
                parsed_data, completion_res = await execute_repair_loop(
                    complete_fn=_call_ollama,
                    messages=injected_messages,
                    response_model=response_model,
                    max_repairs=max_repairs,
                )
            except Exception as exc:
                # MUST NEVER fall back to hosted cloud providers
                logger.error(
                    "Sensitive data query failed on local Ollama for agent [%s]: %s. "
                    "Routing terminated to protect data privacy.",
                    agent,
                    exc,
                )
                raise SensitiveDataRoutingError(
                    f"Sensitive data routing failed on local Ollama: {exc}"
                ) from exc

            response = LLMResponse[T](
                data=parsed_data,
                provider="ollama",
                model=ollama_model,
                prompt_tokens=completion_res.prompt_tokens,
                completion_tokens=completion_res.completion_tokens,
                total_tokens=completion_res.total_tokens,
                latency_ms=completion_res.latency_ms,
                cached=False,
                raw_content=completion_res.content,
            )
            llm_telemetry.record(response, agent, task_type)
            llm_cache.set(cache_key, agent, response)
            return response

        # 4. Normal task execution with fallback chain
        fallback_chain: list[str] = self.config.get(
            "default_fallback_chain", ["nvidia", "openrouter", "ollama"]
        )
        chain_errors: list[tuple[str, str]] = []

        for prov_name in fallback_chain:
            provider = self.providers.get(prov_name)
            if not provider:
                continue

            # Skip providers without configured keys if required
            if prov_name == "nvidia" and not settings.NVIDIA_API_KEY:
                chain_errors.append((prov_name, "NVIDIA_API_KEY not configured"))
                continue
            if prov_name == "openrouter" and not settings.OPENROUTER_API_KEY:
                chain_errors.append((prov_name, "OPENROUTER_API_KEY not configured"))
                continue
            if prov_name == "ollama" and not settings.OLLAMA_BASE_URL:
                chain_errors.append((prov_name, "OLLAMA_BASE_URL not configured"))
                continue

            model = self.get_model_for_agent(agent, prov_name)

            current_provider = provider
            current_model = model

            async def _make_call(
                msgs: list[dict[str, str]],
                p: LLMProvider = current_provider,
                m: str = current_model,
            ) -> RawCompletionResult:
                return await p.complete(
                    messages=msgs,
                    model=m,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )

            try:
                logger.info(
                    "Dispatching prompt for agent [%s] to [%s] (model: %s)",
                    agent,
                    prov_name,
                    model,
                )
                parsed_data, completion_res = await execute_repair_loop(
                    complete_fn=_make_call,
                    messages=injected_messages,
                    response_model=response_model,
                    max_repairs=max_repairs,
                )

                response = LLMResponse[T](
                    data=parsed_data,
                    provider=prov_name,
                    model=model,
                    prompt_tokens=completion_res.prompt_tokens,
                    completion_tokens=completion_res.completion_tokens,
                    total_tokens=completion_res.total_tokens,
                    latency_ms=completion_res.latency_ms,
                    cached=False,
                    raw_content=completion_res.content,
                )
                llm_telemetry.record(response, agent, task_type)
                llm_cache.set(cache_key, agent, response)
                return response

            except (LLMProviderError, LLMStructuredOutputError, LLMBaseError) as exc:
                logger.warning(
                    "Provider [%s] failed for agent [%s]: %s. Falling back to next provider...",
                    prov_name,
                    agent,
                    exc,
                )
                chain_errors.append((prov_name, str(exc)))
            except Exception as exc:
                logger.warning(
                    "Unexpected error on provider [%s] for agent [%s]: %s. Falling back...",
                    prov_name,
                    agent,
                    exc,
                )
                chain_errors.append((prov_name, str(exc)))

        # If all providers failed
        error_summary = "; ".join(f"{p}: {err}" for p, err in chain_errors)
        raise LLMProviderError(
            provider="chain",
            status_code=502,
            message=f"All providers in fallback chain failed for agent '{agent}'. Details: {error_summary}",
            details={"chain_errors": chain_errors},
        )


llm_router = LLMRouter()
