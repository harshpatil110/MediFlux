"""Tests for Milestone 2: Deterministic LLM Replay Cache & Demo Reset Tools."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel
from scripts.reset_demo import reset_demo_state

from app.llm.cache import LLMReplayCache, SQLiteLLMCache
from app.llm.schemas import LLMCacheMissError
from app.main import app as fastapi_app


class SamplePayload(BaseModel):
    name: str
    quantity: int


class TestReplayCache:
    """Test suite for deterministic LLM replay cache persistence and lookup."""

    def test_canonical_sha256_computation(self) -> None:
        """Cache keys match canonical SHA-256 hash across agent, messages, and model schema."""
        messages = [{"role": "user", "content": "Test prompt"}]
        key = SQLiteLLMCache.compute_cache_key("test_agent", messages, SamplePayload)
        assert isinstance(key, str)
        assert len(key) == 64  # SHA-256 hex string

        # Key is deterministic
        key2 = SQLiteLLMCache.compute_cache_key("test_agent", messages, SamplePayload)
        assert key == key2

    def test_replay_cache_loads_fixtures(self) -> None:
        """LLMReplayCache loads complete 6-act cassettes from fixtures/demo_cache/llm_replay_cache.json."""
        cache = LLMReplayCache(mode="replay")
        count = cache.count()
        assert count >= 6  # At least 6 demo acts recorded

    def test_replay_mode_serves_cached_response_without_network(self) -> None:
        """In replay mode, matching entries are returned instantly as LLMResponse."""
        cache = LLMReplayCache(mode="replay")
        # Direct lookup by agent for known demo act
        resp = cache.get(
            cache_key="non_existent_key",
            response_model=None,
            agent="prescription_scanner_agent",
            messages=[{"role": "user", "content": "Scan prescription"}],
        )
        assert resp is not None
        assert resp.cached is True
        assert resp.provider == "cached_replay"
        assert resp.data is not None

    def test_replay_mode_miss_raises_error(self) -> None:
        """In replay mode, complete cache miss raises LLMCacheMissError to prevent external network calls."""
        cache = LLMReplayCache(mode="replay")
        with pytest.raises(LLMCacheMissError):
            cache.get(
                cache_key="definitely_not_a_cached_key_1234567890",
                response_model=SamplePayload,
                agent="unknown_agent_xyz",
                messages=[{"role": "user", "content": "Uncached prompt"}],
            )


class TestDemoResetAndStatus:
    """Test suite for Demo Reset and Status API endpoints and standalone reset tool."""

    def test_standalone_reset_demo_state_idempotent(self) -> None:
        """reset_demo_state executes cleanly and returns standard summary."""
        result = reset_demo_state()
        assert result["status"] == "ok"
        assert "modules_reset" in result
        assert "quarantines_cleared" in result
        assert "tasks_cleared" in result
        assert "prescriptions_reset" in result
        assert result["stock_reset"] is True
        assert result["audit_ledger_cleared"] is True

        # Second run is idempotent
        result2 = reset_demo_state()
        assert result2["status"] == "ok"

    @pytest.mark.asyncio
    async def test_demo_status_endpoint(self) -> None:
        """GET /api/v1/demo/status returns baseline module status, quarantine count, and pending HITL."""
        async with AsyncClient(
            transport=ASGITransport(app=fastapi_app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/demo/status")
            assert resp.status_code == 200
            data = resp.json()
            assert "demo_mode" in data
            assert "cache_mode" in data
            assert "baseline_module_status" in data or "modules_status" in data
            assert "quarantine_count" in data
            assert "pending_hitl_tasks" in data or "pending_hitl_count" in data

    @pytest.mark.asyncio
    async def test_demo_reset_endpoint(self) -> None:
        """POST /api/v1/demo/reset executes clean baseline reset and returns 200 OK."""
        async with AsyncClient(
            transport=ASGITransport(app=fastapi_app), base_url="http://test"
        ) as client:
            resp = await client.post("/api/v1/demo/reset")
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "ok"
            assert "message" in data
            assert "modules_reset" in data
            assert "batches_reset" in data
            assert data.get("stock_reset") is True
