"""Unit and integration tests for Task 5: LLM Router, Fallback Chain, Privacy Isolation,

SQLite Caching, and Self-Healing Repair Loop.
"""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import BaseModel, Field

from app.core.config import settings
from app.llm.cache import SQLiteLLMCache
from app.llm.parser import extract_json_str, inject_schema, parse_and_validate
from app.llm.router import LLMRouter
from app.llm.schemas import (
    LLMCacheMissError,
    LLMProviderError,
    RawCompletionResult,
    SensitiveDataRoutingError,
)


# -----------------------------------------------------------------------------
# Test Models
# -----------------------------------------------------------------------------
class MedicationAnalysis(BaseModel):
    """Test schema for structured LLM extraction."""

    medicine_name: str
    stock_recommendation: int
    risk_level: str = Field(description="low, medium, high")


# -----------------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------------
@pytest.fixture
def temp_cache(tmp_path: Path) -> SQLiteLLMCache:
    """Create an isolated temporary SQLite cache."""
    db_file = tmp_path / "test_llm_cache.db"
    return SQLiteLLMCache(db_path=str(db_file), mode="record")


@pytest.fixture
def mock_router(temp_cache: SQLiteLLMCache) -> LLMRouter:
    """Initialize LLMRouter with isolated cache and dummy API keys."""
    with patch.object(settings, "NVIDIA_API_KEY", "nv-mock-key"), patch.object(
        settings, "OPENROUTER_API_KEY", "openrouter-mock-key"
    ):
        router = LLMRouter()
        # Patch cache inside router
        return router


# -----------------------------------------------------------------------------
# 1. Parser & Schema Injection Tests
# -----------------------------------------------------------------------------
def test_schema_injection_preserves_messages() -> None:
    """Validate that inject_schema adds JSON schema instructions without mutating original input."""
    original_messages = [
        {"role": "user", "content": "Check stock for Paracetamol 500mg."}
    ]
    injected = inject_schema(original_messages, MedicationAnalysis)

    assert len(original_messages) == 1
    assert "OUTPUT SCHEMA REQUIREMENT" not in original_messages[0]["content"]

    assert len(injected) == 2
    assert injected[0]["role"] == "system"
    assert "MedicationAnalysis" in injected[0]["content"] or "medicine_name" in injected[0]["content"]
    assert injected[1]["role"] == "user"


def test_extract_and_validate_markdown_fenced_json() -> None:
    """Validate that parse_and_validate extracts JSON from markdown fences and conversational filler."""
    llm_raw_output = """
    Certainly! Here is the JSON analysis you requested:
    ```json
    {
        "medicine_name": "Paracetamol 500mg",
        "stock_recommendation": 150,
        "risk_level": "low"
    }
    ```
    Please let me know if you need anything else!
    """

    parsed = parse_and_validate(llm_raw_output, MedicationAnalysis)
    assert parsed.medicine_name == "Paracetamol 500mg"
    assert parsed.stock_recommendation == 150
    assert parsed.risk_level == "low"


def test_extract_json_str_unfenced() -> None:
    """Validate JSON extraction when text contains leading or trailing text without fences."""
    raw = 'Analysis result: {"medicine_name": "Amoxicillin", "stock_recommendation": 50, "risk_level": "medium"} done.'
    clean = extract_json_str(raw)
    assert clean.startswith("{")
    assert clean.endswith("}")


# -----------------------------------------------------------------------------
# 2. Normal Call with Structured Output & Telemetry
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_normal_call_structured_output_and_telemetry(temp_cache: SQLiteLLMCache) -> None:
    """Verify standard completion returns typed Pydantic model with complete telemetry."""
    with patch.object(settings, "NVIDIA_API_KEY", "nv-test-key"), patch.object(
        settings, "OPENROUTER_API_KEY", "or-test-key"
    ):
        router = LLMRouter()

        valid_json = (
            '{"medicine_name": "Metformin 500mg", "stock_recommendation": 200, "risk_level": "low"}'
        )
        mock_result = RawCompletionResult(
            content=valid_json,
            provider="nvidia",
            model="meta/llama-3.1-70b-instruct",
            prompt_tokens=45,
            completion_tokens=25,
            total_tokens=70,
            latency_ms=120.5,
        )

        with patch("app.llm.router.llm_cache", temp_cache):
            router.providers["nvidia"].complete = AsyncMock(return_value=mock_result)

            response = await router.complete(
                agent="coding_agent",
                messages=[{"role": "user", "content": "Analyze Metformin supply"}],
                response_model=MedicationAnalysis,
                sensitivity="normal",
                task_type="inventory_forecast",
            )

            assert isinstance(response.data, MedicationAnalysis)
            assert response.data.medicine_name == "Metformin 500mg"
            assert response.data.stock_recommendation == 200
            assert response.provider == "nvidia"
            assert response.prompt_tokens == 45
            assert response.completion_tokens == 25
            assert response.total_tokens == 70
            assert response.latency_ms == 120.5
            assert response.cached is False


# -----------------------------------------------------------------------------
# 3. Fallback Chain on Primary Provider Rate Limit (429)
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_fallback_chain_on_rate_limit(temp_cache: SQLiteLLMCache) -> None:
    """Verify fallback sequence: NVIDIA 429 rate limit triggers OpenRouter seamlessly."""
    with patch.object(settings, "NVIDIA_API_KEY", "nv-key"), patch.object(
        settings, "OPENROUTER_API_KEY", "or-key"
    ):
        router = LLMRouter()

        # NVIDIA fails with 429
        router.providers["nvidia"].complete = AsyncMock(
            side_effect=LLMProviderError(provider="nvidia", status_code=429, message="Rate limit exceeded")
        )

        # OpenRouter succeeds
        valid_json = (
            '{"medicine_name": "Azithromycin 250mg", "stock_recommendation": 80, "risk_level": "medium"}'
        )
        openrouter_result = RawCompletionResult(
            content=valid_json,
            provider="openrouter",
            model="meta-llama/llama-3.1-70b-instruct:free",
            prompt_tokens=50,
            completion_tokens=30,
            total_tokens=80,
            latency_ms=210.0,
        )
        router.providers["openrouter"].complete = AsyncMock(return_value=openrouter_result)
        router.providers["ollama"].complete = AsyncMock()

        with patch("app.llm.router.llm_cache", temp_cache):
            response = await router.complete(
                agent="coding_agent",
                messages=[{"role": "user", "content": "Azithromycin stock plan"}],
                response_model=MedicationAnalysis,
                sensitivity="normal",
            )

            assert response.provider == "openrouter"
            assert response.data.medicine_name == "Azithromycin 250mg"
            assert response.data.risk_level == "medium"

            # Verify NVIDIA was called once, OpenRouter was called once, Ollama was not called
            assert router.providers["nvidia"].complete.call_count == 1
            assert router.providers["openrouter"].complete.call_count == 1
            assert router.providers["ollama"].complete.call_count == 0


# -----------------------------------------------------------------------------
# 4. Sensitivity Isolation (Zero Hosted Cloud Leak)
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_sensitive_routing_isolation_failure_never_calls_hosted(
    temp_cache: SQLiteLLMCache,
) -> None:
    """Verify that sensitivity='sensitive' queries NEVER fail over to cloud providers when Ollama fails."""
    with patch.object(settings, "NVIDIA_API_KEY", "nv-key"), patch.object(
        settings, "OPENROUTER_API_KEY", "or-key"
    ):
        router = LLMRouter()

        # Ollama fails (connection refused or model timeout)
        router.providers["ollama"].complete = AsyncMock(
            side_effect=LLMProviderError(provider="ollama", status_code=500, message="Ollama daemon unreachable")
        )
        router.providers["nvidia"].complete = AsyncMock()
        router.providers["openrouter"].complete = AsyncMock()

        with patch("app.llm.router.llm_cache", temp_cache):
            with pytest.raises(SensitiveDataRoutingError) as exc_info:
                await router.complete(
                    agent="compliance_agent",
                    messages=[{"role": "user", "content": "Patient PII and batch narcotics audit"}],
                    response_model=MedicationAnalysis,
                    sensitivity="sensitive",
                )

            assert "Sensitive data routing failed" in str(exc_info.value)
            # CRITICAL PRIVACY ASSERTION: Neither NVIDIA nor OpenRouter must be touched!
            assert router.providers["nvidia"].complete.call_count == 0
            assert router.providers["openrouter"].complete.call_count == 0
            assert router.providers["ollama"].complete.call_count == 1


@pytest.mark.asyncio
async def test_sensitive_routing_success_uses_ollama(temp_cache: SQLiteLLMCache) -> None:
    """Verify sensitivity='sensitive' queries succeed via Ollama without touching cloud providers."""
    router = LLMRouter()

    valid_json = (
        '{"medicine_name": "Morphine Sulfate 10mg", "stock_recommendation": 10, "risk_level": "high"}'
    )
    ollama_result = RawCompletionResult(
        content=valid_json,
        provider="ollama",
        model="llama3.2:latest",
        prompt_tokens=60,
        completion_tokens=20,
        total_tokens=80,
        latency_ms=95.0,
    )
    router.providers["ollama"].complete = AsyncMock(return_value=ollama_result)
    router.providers["nvidia"].complete = AsyncMock()
    router.providers["openrouter"].complete = AsyncMock()

    with patch("app.llm.router.llm_cache", temp_cache):
        response = await router.complete(
            agent="compliance_agent",
            messages=[{"role": "user", "content": "Sensitive narcotics ledger"}],
            response_model=MedicationAnalysis,
            sensitivity="sensitive",
        )

        assert response.provider == "ollama"
        assert response.data.medicine_name == "Morphine Sulfate 10mg"
        assert router.providers["nvidia"].complete.call_count == 0
        assert router.providers["openrouter"].complete.call_count == 0
        assert router.providers["ollama"].complete.call_count == 1


# -----------------------------------------------------------------------------
# 5. SQLite Cache Modes (Record & Replay)
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_cache_replay_mode_and_miss_error(tmp_path: Path) -> None:
    """Verify cache replay mode returns stored responses and unseeded queries raise LLMCacheMissError."""
    cache_file = tmp_path / "replay_test.db"
    # 1. Record mode: seed response
    cache_record = SQLiteLLMCache(db_path=str(cache_file), mode="record")

    messages = [{"role": "user", "content": "Deterministic cached prompt"}]
    key = cache_record.compute_cache_key("coding_agent", messages, MedicationAnalysis)

    from app.llm.schemas import LLMResponse

    seeded_resp = LLMResponse(
        data=MedicationAnalysis(
            medicine_name="Ibuprofen 400mg",
            stock_recommendation=100,
            risk_level="low",
        ),
        provider="cached_prov",
        model="cached_model",
        prompt_tokens=10,
        completion_tokens=10,
        total_tokens=20,
        latency_ms=5.0,
        cached=False,
    )
    cache_record.set(key, "coding_agent", seeded_resp)

    # 2. Switch to replay mode with a new cache instance
    cache_replay = SQLiteLLMCache(db_path=str(cache_file), mode="replay")
    router = LLMRouter()

    # Network completely mocked out
    router.providers["nvidia"].complete = AsyncMock(side_effect=Exception("Should not be called"))
    router.providers["openrouter"].complete = AsyncMock(side_effect=Exception("Should not be called"))
    router.providers["ollama"].complete = AsyncMock(side_effect=Exception("Should not be called"))

    with patch("app.llm.router.llm_cache", cache_replay):
        # Hit in replay mode
        hit_resp = await router.complete(
            agent="coding_agent",
            messages=messages,
            response_model=MedicationAnalysis,
            sensitivity="normal",
        )
        assert hit_resp.cached is True
        assert hit_resp.data.medicine_name == "Ibuprofen 400mg"
        assert hit_resp.data.stock_recommendation == 100

        # Miss in replay mode -> raises LLMCacheMissError
        unseeded_messages = [{"role": "user", "content": "Unknown query never cached"}]
        with pytest.raises(LLMCacheMissError) as exc_info:
            await router.complete(
                agent="coding_agent",
                messages=unseeded_messages,
                response_model=MedicationAnalysis,
                sensitivity="normal",
            )
        assert "Cache miss in replay mode" in str(exc_info.value)


# -----------------------------------------------------------------------------
# 6. Self-Healing Repair Loop
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_self_healing_repair_loop_recovers(temp_cache: SQLiteLLMCache) -> None:
    """Verify that when an LLM returns malformed JSON, the repair loop feeds the error back and recovers."""
    with patch.object(settings, "NVIDIA_API_KEY", "nv-key"):
        router = LLMRouter()

        # Attempt 1 returns broken JSON (syntax error)
        broken_result = RawCompletionResult(
            content='{"medicine_name": "Doxycycline", "stock_recommendation": BROKEN, "risk_level": "low"}',
            provider="nvidia",
            model="meta/llama-3.1-70b-instruct",
            prompt_tokens=40,
            completion_tokens=15,
            total_tokens=55,
            latency_ms=90.0,
        )

        # Attempt 2 returns valid repaired JSON
        fixed_result = RawCompletionResult(
            content='{"medicine_name": "Doxycycline 100mg", "stock_recommendation": 60, "risk_level": "low"}',
            provider="nvidia",
            model="meta/llama-3.1-70b-instruct",
            prompt_tokens=85,
            completion_tokens=25,
            total_tokens=110,
            latency_ms=105.0,
        )

        router.providers["nvidia"].complete = AsyncMock(
            side_effect=[broken_result, fixed_result]
        )

        with patch("app.llm.router.llm_cache", temp_cache):
            response = await router.complete(
                agent="coding_agent",
                messages=[{"role": "user", "content": "Analyze Doxycycline"}],
                response_model=MedicationAnalysis,
                sensitivity="normal",
                max_repairs=2,
            )

            assert response.data.medicine_name == "Doxycycline 100mg"
            assert response.data.stock_recommendation == 60
            # Provider should have been called twice (1 initial + 1 repair)
            assert router.providers["nvidia"].complete.call_count == 2

            # Check that the repair call included feedback about the failure
            second_call_messages = router.providers["nvidia"].complete.call_args_list[1][1]["messages"]
            assert any("failed schema validation" in m.get("content", "") for m in second_call_messages)


@pytest.mark.asyncio
async def test_repair_loop_exhaustion_raises_error(temp_cache: SQLiteLLMCache) -> None:
    """Verify that if all repair attempts persistently fail, the error is propagated."""
    with patch.object(settings, "NVIDIA_API_KEY", "nv-key"), patch.object(
        settings, "OPENROUTER_API_KEY", None
    ):
        router = LLMRouter()

        # All attempts return invalid JSON
        broken_result = RawCompletionResult(
            content="Sorry, I cannot provide JSON format for this query.",
            provider="nvidia",
            model="meta/llama-3.1-70b-instruct",
            prompt_tokens=30,
            completion_tokens=10,
            total_tokens=40,
            latency_ms=80.0,
        )
        router.providers["nvidia"].complete = AsyncMock(return_value=broken_result)
        router.providers["ollama"].complete = AsyncMock(return_value=broken_result)

        with patch("app.llm.router.llm_cache", temp_cache):
            with pytest.raises(LLMProviderError) as exc_info:
                await router.complete(
                    agent="coding_agent",
                    messages=[{"role": "user", "content": "Bad format prompt"}],
                    response_model=MedicationAnalysis,
                    sensitivity="normal",
                    max_repairs=2,
                )

            assert "All providers in fallback chain failed" in str(exc_info.value)
