"""Comprehensive unit and integration test suite for Milestone 1 resilience and failure handling.

Covers:
1. SovereignLLMOfflineError (HTTP 503, SOVEREIGN_LOCAL_MODEL_OFFLINE, zero external cloud fallback)
2. Resilient JSON Parser (parse_and_repair_llm_json with fences, unbalanced brackets, commas, unquoted keys, fallback)
3. Fault Injection Context Manager (inject_llm_fault for 429/500/502/503/timeout/connect_error/kill with <100ms failover)
4. HITL Task Expiration (HTTP 409 Conflict, status expired transition, audit log)
5. Cascade Partial Failure Handling (partial_failure status, retained results, HITL escalation, audit entry)
6. Duplicate Event Idempotency (HTTP 200 duplicate response, zero double deductions, zero duplicate cascades)
"""

import time
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI, status
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel

from app.core.audit_ledger import clear_in_memory_audit_ledger, get_in_memory_audit_ledger
from app.core.errors import SovereignLLMOfflineError
from app.core.hitl import (
    _in_memory_hitl_tasks,
    clear_hitl_tasks,
    create_hitl_task,
    get_hitl_task,
    is_task_expired,
)
from app.events.models import SaleEvent
from app.events.service import (
    apply_sale,
    clear_service_state,
    get_in_memory_stock,
    set_in_memory_stock,
)
from app.graphs.cascade import CascadeState, _execute_tier_node, finalize_node
from app.llm.fault import clear_all_faults, inject_llm_fault
from app.llm.parser import parse_and_repair_llm_json
from app.llm.router import LLMRouter
from app.llm.schemas import (
    LLMStructuredOutputError,
    RawCompletionResult,
)
from app.main import app as fastapi_app
from app.workers.hitl_expiry_worker import process_expired_hitl_tasks


# =============================================================================
# Helper Models for Testing
# =============================================================================
class SampleSchema(BaseModel):
    name: str
    count: int
    tags: list[str] = []


# =============================================================================
# 1. Sovereign LLM Offline Error (HTTP 503) Tests
# =============================================================================
@pytest.mark.asyncio
async def test_sovereign_llm_offline_error_raised_on_sensitive_query() -> None:
    """When sensitivity='sensitive' and local Ollama is offline, SovereignLLMOfflineError is raised."""
    router = LLMRouter()

    # Simulate Ollama failure via fault injection
    with inject_llm_fault("ollama", "connect_error"):
        with pytest.raises(SovereignLLMOfflineError) as exc_info:
            await router.complete(
                agent="compliance_agent",
                messages=[{"role": "user", "content": "Patient medical record"}],
                response_model=SampleSchema,
                sensitivity="sensitive",
            )

        err = exc_info.value
        assert err.status_code == 503
        assert err.code == "SOVEREIGN_LOCAL_MODEL_OFFLINE"


@pytest.mark.asyncio
async def test_sovereign_llm_strictly_forbids_cloud_fallback() -> None:
    """Under sensitivity='sensitive', cloud providers (nvidia, openrouter) must NEVER be called."""
    router = LLMRouter()
    nvidia_mock = AsyncMock()
    openrouter_mock = AsyncMock()
    router.providers["nvidia"].complete = nvidia_mock  # type: ignore[method-assign]
    router.providers["openrouter"].complete = openrouter_mock  # type: ignore[method-assign]

    with inject_llm_fault("ollama", "kill"):
        with pytest.raises(SovereignLLMOfflineError):
            await router.complete(
                agent="compliance_agent",
                messages=[{"role": "user", "content": "Sensitive query"}],
                response_model=SampleSchema,
                sensitivity="sensitive",
            )

    nvidia_mock.assert_not_called()
    openrouter_mock.assert_not_called()


@pytest.mark.asyncio
async def test_sovereign_llm_offline_exception_handler_returns_http_503() -> None:
    """FastAPI exception handler for SovereignLLMOfflineError returns HTTP 503 with standardized JSON."""
    test_app = FastAPI()
    from app.core.handlers import register_exception_handlers

    register_exception_handlers(test_app)

    @test_app.get("/test-sovereign-offline")
    async def _fail_endpoint() -> None:
        raise SovereignLLMOfflineError(
            message="Local sovereign Ollama is unreachable",
            details={"provider": "ollama", "host": "http://localhost:11434"},
        )

    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        resp = await client.get("/test-sovereign-offline")
        assert resp.status_code == 503
        data = resp.json()
        assert data["error"]["code"] == "SOVEREIGN_LOCAL_MODEL_OFFLINE"
        assert "Local sovereign Ollama is unreachable" in data["detail"]


# =============================================================================
# 2. Resilient JSON Parser (parse_and_repair_llm_json) Tests
# =============================================================================
def test_parse_and_repair_strips_markdown_code_fences() -> None:
    """Markdown fences with or without 'json' are cleanly stripped."""
    raw = "```json\n{\n  \"name\": \"Paracetamol\",\n  \"count\": 50,\n  \"tags\": [\"analgesic\"]\n}\n```"
    result = parse_and_repair_llm_json(raw, SampleSchema)
    assert result.name == "Paracetamol"
    assert result.count == 50
    assert result.tags == ["analgesic"]


def test_parse_and_repair_balances_unbalanced_brackets() -> None:
    """Unbalanced closing brackets and unclosed object/array structures are healed."""
    # Missing closing brace and bracket
    raw = "{\"name\": \"Amoxicillin\", \"count\": 20, \"tags\": [\"antibiotic\""
    result = parse_and_repair_llm_json(raw, SampleSchema)
    assert result.name == "Amoxicillin"
    assert result.count == 20
    assert result.tags == ["antibiotic"]


def test_parse_and_repair_fixes_trailing_commas() -> None:
    """Trailing commas in objects and arrays are removed."""
    raw = "{\"name\": \"Ibuprofen\", \"count\": 10, \"tags\": [\"nsaid\",],}"
    result = parse_and_repair_llm_json(raw, SampleSchema)
    assert result.name == "Ibuprofen"
    assert result.count == 10
    assert result.tags == ["nsaid"]


def test_parse_and_repair_fixes_single_and_unquoted_keys() -> None:
    """Single-quoted and unquoted object keys are converted to valid double-quoted JSON."""
    raw = "{name: 'Metformin', count: 100, tags: ['diabetes']}"
    result = parse_and_repair_llm_json(raw, SampleSchema)
    assert result.name == "Metformin"
    assert result.count == 100
    assert result.tags == ["diabetes"]


def test_parse_and_repair_normalizes_python_literals() -> None:
    """Unquoted Python literals True, False, None are converted to JSON true, false, null."""
    class TierModel(BaseModel):
        tier: str
        valid: bool
        notes: str | None = None

    raw = "{tier: 'pharmacy', valid: True, notes: None}"
    result = parse_and_repair_llm_json(raw, TierModel)
    assert result.tier == "pharmacy"
    assert result.valid is True
    assert result.notes is None


def test_parse_and_repair_uses_fallback_factory_on_unrecoverable_input() -> None:
    """When input is completely corrupted, fallback_factory is safely called without raising JSONDecodeError."""
    corrupted_raw = "<<<TOTAL_NONSENSE_NOT_JSON>>>"

    def default_fallback() -> SampleSchema:
        return SampleSchema(name="FallbackProduct", count=0, tags=["safe_default"])

    result = parse_and_repair_llm_json(corrupted_raw, SampleSchema, fallback_factory=default_fallback)
    assert result.name == "FallbackProduct"
    assert result.count == 0
    assert result.tags == ["safe_default"]


def test_parse_and_repair_raises_llm_structured_error_when_no_fallback() -> None:
    """When input is unrecoverable and no fallback_factory is provided, LLMStructuredOutputError is raised."""
    corrupted_raw = "<<<CORRUPTED>>>"
    with pytest.raises(LLMStructuredOutputError):
        parse_and_repair_llm_json(corrupted_raw, SampleSchema)


# =============================================================================
# 3. Fault Injection Context Manager (inject_llm_fault) Tests
# =============================================================================
@pytest.mark.asyncio
async def test_inject_llm_fault_rate_limit_429_failover() -> None:
    """Simulating primary provider HTTP 429 triggers failover to next provider in < 100ms."""
    router = LLMRouter()

    # Mock openrouter to succeed
    async def mock_openrouter_complete(*args: Any, **kwargs: Any) -> RawCompletionResult:
        return RawCompletionResult(
            content='{"name": "FailoverProduct", "count": 42, "tags": ["resilience"]}',
            provider="openrouter",
            model="meta-llama/llama-3.1-8b-instruct:free",
        )

    router.providers["openrouter"].complete = mock_openrouter_complete  # type: ignore[method-assign]

    start_t = time.perf_counter()
    with inject_llm_fault("nvidia", "rate_limit_429"):
        response = await router.complete(
            agent="analytics_agent",
            messages=[{"role": "user", "content": "test"}],
            response_model=SampleSchema,
        )
    elapsed_ms = (time.perf_counter() - start_t) * 1000

    assert response.provider == "openrouter"
    assert response.data.name == "FailoverProduct"
    # Automatic failover must occur in < 100ms without crashing agent
    assert elapsed_ms < 100.0


@pytest.mark.asyncio
async def test_inject_llm_fault_kill_failover() -> None:
    """Simulating provider process kill triggers transparent failover."""
    router = LLMRouter()

    async def mock_openrouter_complete(*args: Any, **kwargs: Any) -> RawCompletionResult:
        return RawCompletionResult(
            content='{"name": "SurvivedKill", "count": 99, "tags": ["resilient"]}',
            provider="openrouter",
            model="meta-llama/llama-3.1-8b-instruct:free",
        )

    router.providers["openrouter"].complete = mock_openrouter_complete  # type: ignore[method-assign]

    with inject_llm_fault("nvidia", "kill"):
        response = await router.complete(
            agent="default",
            messages=[{"role": "user", "content": "hello"}],
            response_model=SampleSchema,
        )

    assert response.provider == "openrouter"
    assert response.data.name == "SurvivedKill"


def test_inject_llm_fault_clears_on_context_exit() -> None:
    """Injected fault is cleanly removed when the context manager exits."""
    clear_all_faults()
    from app.llm.fault import get_injected_fault

    assert get_injected_fault("nvidia") is None
    with inject_llm_fault("nvidia", "server_error_500"):
        assert get_injected_fault("nvidia") == "server_error_500"
    assert get_injected_fault("nvidia") is None


# =============================================================================
# 4. HITL Task Expiration & HTTP 409 Conflict Tests
# =============================================================================
@pytest.mark.asyncio
async def test_submit_hitl_decision_rejects_expired_task_with_http_409() -> None:
    """Expired HITL tasks past expires_at reject decisions with HTTP 409 Conflict."""
    clear_hitl_tasks()
    clear_in_memory_audit_ledger()

    # Create task with expires_at in the past
    past_iso = (datetime.now(UTC) - timedelta(hours=2)).isoformat()
    task = create_hitl_task(
        task_type="regulatory_hot_swap",
        payload={"module_name": "pricing_engine", "version": 2},
        correlation_id="test-corr-expired-01",
    )
    task_id = task["id"]
    task["expires_at"] = past_iso
    _in_memory_hitl_tasks[task_id] = task

    assert is_task_expired(task) is True

    # Use actual FastAPI test client to verify HTTP 409 response
    from app.core.security import get_current_user
    from app.schemas.base import UserProfile

    user_id_str = str(uuid.uuid4())
    mock_user = UserProfile(
        id=user_id_str,
        user_id=user_id_str,
        email="compliance@mediflux.in",
        role="compliance_officer",
    )
    fastapi_app.dependency_overrides[get_current_user] = lambda: mock_user

    try:
        async with AsyncClient(
            transport=ASGITransport(app=fastapi_app), base_url="http://test"
        ) as client:
            resp = await client.post(
                f"/api/v1/hitl/tasks/{task_id}/decide",
                json={"decision": "approve", "reason": "Late approval attempt"},
            )
            assert resp.status_code == status.HTTP_409_CONFLICT
            data = resp.json()
            assert "Task has expired and cannot be approved" in data["detail"]
            assert _in_memory_hitl_tasks[task_id]["status"] == "expired"

            # Verify audit ledger recorded rejection
            audit_entries = get_in_memory_audit_ledger()
            assert any(
                e.get("action") == "HITL_TASK_EXPIRED_REJECTED"
                for e in audit_entries
            )
    finally:
        fastapi_app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_hitl_expiry_worker_marks_tasks_expired() -> None:
    """hitl_expiry_worker identifies pending tasks past deadline and transitions status to 'expired'."""
    clear_hitl_tasks()
    task = create_hitl_task(
        task_type="reorder_approval",
        payload={"order_id": "ORD-123"},
    )
    task_id = task["id"]
    task["expires_at"] = (datetime.now(UTC) - timedelta(minutes=30)).isoformat()
    _in_memory_hitl_tasks[task_id] = task

    processed = await process_expired_hitl_tasks()
    assert len(processed) >= 1
    updated = get_hitl_task(task_id)
    assert updated is not None
    assert updated["status"] == "expired"


# =============================================================================
# 5. Cascade Partial Failure Handling Tests
# =============================================================================
@pytest.mark.asyncio
async def test_cascade_partial_failure_retains_earlier_results_and_escalates() -> None:
    """When a downstream tier fails in cascade, status is marked partial_failure, earlier tiers are preserved, and HITL is created."""
    clear_hitl_tasks()
    clear_in_memory_audit_ledger()
    from app.core.hitl_policy import clear_policy_cache
    clear_policy_cache()

    initial_state: CascadeState = {
        "correlation_id": "casc-partial-test-01",
        "pharmacy_id": "11111111-1111-1111-1111-111111111111",
        "product_id": "PARA-500",
        "quantity": 10,
        "active_tiers": ["pharmacy", "stockist", "distributor"],
        "pharmacy_result": {"status": "success", "stock_deducted": 10},
        "stockist_result": {"status": "success", "action": "fulfill_local"},
        "trace": [
            {"tier": "pharmacy", "status": "success"},
            {"tier": "stockist", "status": "success"},
        ],
        "errors": [],
    }

    # Simulate failure in distributor tier node
    with patch("app.agents.base.BaseAgent.run", side_effect=RuntimeError("Distributor connection timeout")):
        result = await _execute_tier_node("distributor", initial_state)

    assert result["status"] == "partial_failure"
    assert len(result["errors"]) == 1
    assert "Distributor connection timeout" in result["errors"][0]["error"]

    # Finalize node must preserve partial_failure and create high-priority HITL escalation
    final_state: CascadeState = {
        **initial_state,
        "distributor_result": result["distributor_result"],
        "status": "partial_failure",
        "errors": result["errors"],
        "trace": result["trace"],
    }

    final_res = await finalize_node(final_state)
    assert final_res["status"] == "partial_failure"

    # Verify HITL escalation task created
    hitl_tasks = _in_memory_hitl_tasks.values()
    escalation_task = next(
        (t for t in hitl_tasks if t.get("action_type") == "cascade_partial_failure_escalation" or t.get("task_type") == "cascade_partial_failure_escalation"),
        None,
    )
    assert escalation_task is not None
    assert escalation_task["task_data"]["risk_level"] == "high"

    # Verify audit ledger entry recorded
    audit_entries = get_in_memory_audit_ledger()
    assert any(
        e.get("action") in ("CASCADE_TIER_PARTIAL_FAILURE", "CASCADE_PARTIAL_FAILURE_FINALIZED")
        for e in audit_entries
    )


# =============================================================================
# 6. Duplicate Event Idempotency Check Tests
# =============================================================================
@pytest.mark.asyncio
async def test_duplicate_pos_sale_returns_http_200_without_double_deduction() -> None:
    """Duplicate POS sale events return HTTP 200 with status='duplicate' and do not deduct stock twice."""
    clear_service_state()
    pharmacy_id = str(uuid.uuid4())
    product_id = str(uuid.uuid4())
    batch_id = "BATCH-IDEMP-01"
    event_id = str(uuid.uuid4())

    # Seed initial inventory = 50 units
    set_in_memory_stock(pharmacy_id, product_id, batch_id, 50)

    sale_evt = SaleEvent(
        event_id=event_id,
        pharmacy_id=pharmacy_id,
        product_id=product_id,
        batch_id=batch_id,
        quantity=5,
    )

    # 1. First ingestion -> Applied
    first_res = await apply_sale(sale_evt, correlation_id="idemp-corr-01")
    assert first_res["applied"] is True
    assert get_in_memory_stock(pharmacy_id, product_id, batch_id) == 45

    # 2. Second ingestion with SAME event_id -> Duplicate
    second_res = await apply_sale(sale_evt, correlation_id="idemp-corr-02")
    assert second_res["status"] == "duplicate"
    assert second_res["applied"] is False
    # Stock must remain 45, NOT decremented to 40
    assert get_in_memory_stock(pharmacy_id, product_id, batch_id) == 45


@pytest.mark.asyncio
async def test_duplicate_pos_sale_endpoint_response() -> None:
    """POS /events/sale endpoint returns HTTP 202 on initial sale and HTTP 200 on duplicate."""
    clear_service_state()
    event_id = str(uuid.uuid4())
    pharmacy_id = str(uuid.uuid4())
    product_id = str(uuid.uuid4())

    payload = {
        "event_id": event_id,
        "pharmacy_id": pharmacy_id,
        "product_id": product_id,
        "batch_id": "BATCH-EP-01",
        "quantity": 2,
    }

    async with AsyncClient(
        transport=ASGITransport(app=fastapi_app), base_url="http://test"
    ) as client:
        # First call -> 202 Accepted
        r1 = await client.post("/api/v1/events/sale", json=payload)
        assert r1.status_code == status.HTTP_202_ACCEPTED
        assert r1.json()["status"] == "accepted"

        # Second call with duplicate event_id -> 200 OK duplicate
        r2 = await client.post("/api/v1/events/sale", json=payload)
        assert r2.status_code == status.HTTP_200_OK
        data2 = r2.json()
        assert data2["status"] == "duplicate"
        assert data2["applied"] is False
        assert data2["event_id"] == event_id
