"""Task 29 Unit Tests: Core Engine Safety, AST Guard, Registry, and Tamper Detection.

Verifies:
1. AST Guard static analysis (blocks forbidden modules, builtins, dunder traversals, and infinite loops).
2. Dynamic module registry atomic hot-swapping, isolated test execution, and rollback.
3. Cryptographic audit ledger genesis block linking ("0"*64), monotonic sequence numbering, SHA-256 hash chaining, and tamper detection.
4. LLM Router provider routing fallback, token accounting, and sovereign sensitive local routing.
5. EventBus deduplication (_seen_event_ids), queue delivery, and in-process pub/sub delivery.
"""

from __future__ import annotations

import asyncio
import copy
from typing import Any
from unittest.mock import patch

import pytest
from pydantic import BaseModel

from app.core.audit_ledger import (
    _in_memory_audit_ledger,
    clear_in_memory_audit_ledger,
    compute_entry_hash,
    verify_audit_chain,
    write_audit_entry,
)
from app.core.config import settings
from app.core.errors import SovereignLLMOfflineError
from app.events.bus import InProcessEventBus
from app.events.models import EventEnvelope
from app.llm.fault import inject_llm_fault
from app.llm.router import LLMRouter
from app.llm.schemas import RawCompletionResult
from app.modules_runtime.guard import (
    ASTGuard,
    GuardViolationError,
    ModuleExecutionError,
    ModuleTimeoutError,
    SubprocessRunner,
)
from app.modules_runtime.registry import ModuleRegistry


class TestASTGuardSecurity:
    """Validate AST safety policies against unsafe code synthesis."""

    def test_ast_guard_blocks_forbidden_imports(self) -> None:
        forbidden_snippets = [
            "import os\nx = os.listdir('.')",
            "import subprocess\nsubprocess.run(['dir'])",
            "import sys\nsys.exit(0)",
            "import socket\ns = socket.socket()",
            "from pathlib import Path\np = Path('.')",
        ]
        for snippet in forbidden_snippets:
            with pytest.raises(GuardViolationError):
                ASTGuard.validate_code(snippet)

    def test_ast_guard_blocks_dangerous_builtins_and_dunders(self) -> None:
        dangerous_snippets = [
            "eval('1 + 1')",
            "exec('a = 1')",
            "open('passwords.txt', 'r')",
            "__import__('os').system('dir')",
            "x = ().__class__.__bases__[0]",
            "getattr(x, '__subclasses__')()",
            "x = f.__globals__",
        ]
        for snippet in dangerous_snippets:
            with pytest.raises(GuardViolationError):
                ASTGuard.validate_code(snippet)

    def test_ast_guard_allows_safe_transformations(self) -> None:
        safe_code = """
def transform(payload):
    qty = int(payload.get('quantity', 1))
    rate = float(payload.get('unit_price', 10.0))
    return {
        'sku': str(payload.get('sku', '')).upper(),
        'total': round(qty * rate, 2),
        'valid': True
    }
"""
        # Should not raise any GuardViolationError
        ASTGuard.validate_code(safe_code)

    def test_guard_timeout_and_infinite_loops(self) -> None:
        """Module execution with infinite loop or timeout is terminated and raises ModuleTimeoutError."""
        infinite_loop_code = """
def run(input_data):
    while True:
        pass
    return {}
"""
        with pytest.raises(ModuleTimeoutError):
            SubprocessRunner.execute_module(
                source_code=infinite_loop_code,
                input_data={"test": 1},
                timeout=0.3,
            )


class TestModuleRegistryLifecycle:
    """Validate dynamic module versioning, isolated test execution, atomic hot-swapping, and rollback."""

    def test_module_registry_hot_swap_and_rollback(self) -> None:
        registry = ModuleRegistry()
        mod_name = "pricing_calculator"

        # 1. Create v1
        v1_code = "def calculate(x): return x * 10\ndef run(p): return {'res': calculate(p['x'])}"
        v1_tests = "assert calculate(2) == 20"
        v1 = registry.create_version(mod_name, "pricing", v1_code, v1_tests)
        assert v1.version == 1

        # Isolated test execution
        assert registry.run_tests(mod_name, 1) is True

        # Activate v1
        active_v1 = registry.activate(mod_name, 1)
        assert active_v1.version == 1
        assert active_v1.status == "active"

        # 2. Create and hot-swap to v2
        v2_code = "def calculate(x): return x * 15\ndef run(p): return {'res': calculate(p['x'])}"
        v2_tests = "assert calculate(2) == 30"
        v2 = registry.create_version(mod_name, "pricing", v2_code, v2_tests)
        assert v2.version == 2

        active_v2 = registry.activate(mod_name, 2)
        assert active_v2.version == 2
        assert active_v2.status == "active"

        # 3. Rollback to v1
        rolled_back = registry.rollback(mod_name)
        assert rolled_back.version == 1
        assert rolled_back.status == "active"

    def test_module_registry_failing_tests_prevent_activation(self) -> None:
        """If module verification tests fail, isolated execution raises ModuleExecutionError and prevents activation."""
        registry = ModuleRegistry()
        mod_name = "failing_calc"

        code = "def calculate(x): return x + 1\ndef run(p): return {'res': calculate(p['x'])}"
        failing_tests = "assert calculate(2) == 999"  # Will fail

        v = registry.create_version(mod_name, "calc", code, failing_tests)
        assert v.version == 1

        with pytest.raises(ModuleExecutionError):
            registry.run_tests(mod_name, 1)

        with pytest.raises(ModuleExecutionError):
            registry.activate(mod_name, 1)


class TestAuditLedgerTamperDetection:
    """Validate Genesis block linking, monotonic sequence numbering, SHA-256 hash-chaining, and tamper detection."""

    @pytest.mark.asyncio
    async def test_audit_ledger_genesis_linking_and_monotonic_seq(self) -> None:
        """Genesis block must link to '0'*64 and sequence numbers must be monotonic."""
        original_ledger = copy.deepcopy(_in_memory_audit_ledger)
        clear_in_memory_audit_ledger()

        try:
            with patch.object(settings, "SUPABASE_URL", ""):
                entry1 = await write_audit_entry(
                    actor="system",
                    action="GENESIS_INIT",
                    entity_type="system",
                    entity_id="node-0",
                    payload={"init": True},
                    explanation="Genesis ledger block",
                )
                assert entry1["seq"] == 1
                assert entry1["prev_hash"] == "0" * 64
                assert len(entry1["hash"]) == 64

                entry2 = await write_audit_entry(
                    actor="pharmacist:1",
                    action="DISPENSE",
                    entity_type="prescription",
                    entity_id="rx-101",
                    payload={"drug": "Azithromycin", "qty": 1},
                    explanation="Dispensed at counter",
                )
                assert entry2["seq"] == 2
                assert entry2["prev_hash"] == entry1["hash"]
                assert entry2["seq"] > entry1["seq"]

                verification = verify_audit_chain()
                assert verification["valid"] is True
                assert verification["total_entries"] == 2
        finally:
            clear_in_memory_audit_ledger()
            _in_memory_audit_ledger.extend(original_ledger)

    def test_audit_ledger_tamper_detection(self) -> None:
        original_ledger = copy.deepcopy(_in_memory_audit_ledger)
        clear_in_memory_audit_ledger()

        try:
            prev_hash = "0" * 64
            # Build 3 sequential chained blocks
            for i in range(1, 4):
                ts = f"2026-11-14T10:0{i}:00Z"
                action = f"ACTION_{i}"
                payload = {"seq": i, "val": i * 100}
                h = compute_entry_hash(
                    prev_hash, i, ts, "actor:test", action, "entity", f"id-{i}", payload, "audit"
                )
                _in_memory_audit_ledger.append({
                    "id": f"entry-{i}",
                    "seq": i,
                    "ts": ts,
                    "actor": "actor:test",
                    "action": action,
                    "entity_type": "entity",
                    "entity_id": f"id-{i}",
                    "node_id": "00000000-0000-0000-0000-000000000000",
                    "prev_hash": prev_hash,
                    "hash": h,
                    "payload": payload,
                    "explanation": "audit",
                })
                prev_hash = h

            # Initial chain must be verified
            res_clean = verify_audit_chain()
            assert res_clean["valid"] is True
            assert res_clean.get("broken_at_id") is None

            # Tamper with block 2's payload without updating hash
            _in_memory_audit_ledger[1]["payload"]["val"] = 999999

            # Verification must catch tampering and identify broken block
            res_tampered = verify_audit_chain()
            assert res_tampered["valid"] is False
            assert res_tampered.get("broken_at_id") == "entry-2"
            assert res_tampered.get("broken_at_seq") == 2

        finally:
            clear_in_memory_audit_ledger()
            _in_memory_audit_ledger.extend(original_ledger)


class DummyLLMResult(BaseModel):
    decision: str
    tokens_counted: int


@pytest.mark.asyncio
class TestLLMRouterAndFakeLLM:
    """Validate provider fallback chain, token accounting, and sovereign offline error."""

    async def test_llm_router_fallback_and_token_accounting(self) -> None:
        router = LLMRouter()

        # Primary provider fails (e.g. simulated 429), router falls back to secondary provider
        async def mock_openrouter_complete(*args: Any, **kwargs: Any) -> RawCompletionResult:
            return RawCompletionResult(
                content='{"decision": "fallback_accepted", "tokens_counted": 42}',
                provider="openrouter",
                model="openrouter/free-model",
                prompt_tokens=30,
                completion_tokens=12,
                total_tokens=42,
                latency_ms=8.5,
            )

        router.providers["openrouter"].complete = mock_openrouter_complete  # type: ignore[method-assign]

        with inject_llm_fault("nvidia", "rate_limit_429"):
            response = await router.complete(
                agent="analytics_agent",
                messages=[{"role": "user", "content": "Analyze demand velocity"}],
                response_model=DummyLLMResult,
            )
            assert response.data.decision == "fallback_accepted"
            assert response.provider == "openrouter"
            # Token accounting verification
            assert response.prompt_tokens == 30
            assert response.completion_tokens == 12
            assert response.total_tokens == 42
            assert response.latency_ms > 0

    async def test_sensitive_sovereignty_raises_sovereign_error(self) -> None:
        """When sensitivity='sensitive', failure of local Ollama raises SovereignLLMOfflineError with zero cloud calls."""
        router = LLMRouter()

        # Inject offline fault on Ollama and ensure cache is bypassed for sovereignty test
        with (
            inject_llm_fault("ollama", "connect_error"),
            patch.object(settings, "LLM_CACHE_MODE", "off"),
            patch.object(settings, "DEMO_MODE", False),
        ):
            with pytest.raises(SovereignLLMOfflineError) as exc_info:
                await router.complete(
                    agent="compliance_agent",
                    messages=[{"role": "user", "content": "Sensitive patient prescription MCI registry"}],
                    response_model=DummyLLMResult,
                    sensitivity="sensitive",
                )
            assert "sensitive" in str(exc_info.value).lower() or "ollama" in str(exc_info.value).lower()


@pytest.mark.asyncio
class TestEventBusDeduplication:
    """Validate in-process asynchronous EventBus deduplication, queue delivery, and pub/sub."""

    async def test_event_bus_deduplication(self) -> None:
        bus = InProcessEventBus()
        received = []

        def _listener(evt: EventEnvelope) -> None:
            received.append(evt.event_id)

        bus.register_listener("orders", _listener)

        # Publish unique event
        evt1 = EventEnvelope(
            type="orders",
            node_id="00000000-0000-0000-0000-000000000001",
            payload={"order_id": "ord-100"},
            event_id="evt-uniq-100",
        )
        await bus.publish("orders", evt1)
        assert len(bus._history) == 1
        assert len(received) == 1
        assert "evt-uniq-100" in bus._seen_event_ids

        # Publish duplicate event with identical event_id
        await bus.publish("orders", evt1)
        assert len(bus._history) == 1, "Duplicate event_id must not be added to history"
        assert len(received) == 1, "Duplicate event_id must not trigger listeners"

        # Publish second unique event
        evt2 = EventEnvelope(
            type="orders",
            node_id="00000000-0000-0000-0000-000000000001",
            payload={"order_id": "ord-200"},
            event_id="evt-uniq-200",
        )
        await bus.publish("orders", evt2)
        assert len(bus._history) == 2
        assert len(received) == 2
        assert received == ["evt-uniq-100", "evt-uniq-200"]
        assert "evt-uniq-200" in bus._seen_event_ids

    async def test_event_bus_queue_subscription_delivery(self) -> None:
        """Verify queue delivery via async subscription stream."""

        bus = InProcessEventBus()

        async def _publish_later() -> None:
            await asyncio.sleep(0.01)
            evt = EventEnvelope(
                type="inventory.alerts",
                node_id="node-1",
                payload={"sku": "PARA-650", "stock": 5},
                event_id="alert-evt-01",
            )
            await bus.publish("inventory.alerts", evt)

        task = asyncio.create_task(_publish_later())
        sub_iter = bus.subscribe("inventory.alerts")
        delivered = await asyncio.wait_for(anext(sub_iter), timeout=2.0)
        await task

        assert delivered.event_id == "alert-evt-01"
        assert delivered.payload["sku"] == "PARA-650"
