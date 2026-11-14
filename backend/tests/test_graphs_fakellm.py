"""Comprehensive deterministic FakeLLM test suite for all 6 MediFlux LangGraph workflows (Task 29).

Verifies end-to-end deterministic execution of:
1. Demand Cascade Graph (app.graphs.cascade)
2. Adapter Forge Graph (app.graphs.forge)
3. Autonomous Regulatory Pipeline Graph (app.graphs.regulatory)
4. Sovereign Prescription Compliance Graph (app.graphs.prescription)
5. Cold-Chain IoT Degradation Graph (app.graphs.coldchain)
6. Network Copilot Tool-Execution Graph (app.graphs.copilot)

Strict constraint: Zero external network calls. Purely deterministic in-process execution.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from app.agents.base import clear_agent_runs
from app.core.config import settings
from app.core.hitl import clear_hitl_tasks
from app.events.service import clear_service_state
from app.graphs.cascade import (
    CascadeState,
    cascade_graph,
    clear_cascade_traces,
    get_in_memory_cascade_trace,
)
from app.graphs.coldchain import (
    reset_coldchain_state,
    run_coldchain_pipeline,
)
from app.graphs.copilot import (
    CopilotScope,
    run_copilot,
)
from app.graphs.forge import (
    clear_adapter_store,
    get_adapter,
    run_forge,
)
from app.graphs.prescription import (
    clear_prescription_store,
    run_prescription_graph,
)
from app.graphs.regulatory import (
    clear_regulatory_store,
    crawl_regulatory_notice,
    ensure_baseline_regulatory_modules,
    run_regulatory_pipeline,
)
from app.llm.embeddings import clear_vector_index, index_network_embeddings
from app.modules_runtime.registry import module_registry


def _resolve_fixture(rel_path: str) -> Path:
    """Find a test fixture relative to repo root or backend/."""
    candidates = [
        Path(rel_path),
        Path("backend") / rel_path,
        Path("..") / rel_path,
    ]
    for c in candidates:
        if c.exists():
            return c
    raise FileNotFoundError(f"Fixture not found at {rel_path}")


@pytest.fixture(autouse=True)
def clean_graph_environment():
    """Ensure clean stores and offline settings before and after each graph test."""
    clear_agent_runs()
    clear_cascade_traces()
    clear_adapter_store()
    clear_service_state()
    clear_regulatory_store()
    clear_prescription_store()
    clear_hitl_tasks()
    reset_coldchain_state()
    clear_vector_index()
    index_network_embeddings()
    module_registry.clear()

    with patch.object(settings, "SUPABASE_URL", ""), \
         patch.object(settings, "NVIDIA_API_KEY", None), \
         patch.object(settings, "OPENROUTER_API_KEY", None), \
         patch.object(settings, "OLLAMA_BASE_URL", ""):
        ensure_baseline_regulatory_modules()
        yield

    clear_agent_runs()
    clear_cascade_traces()
    clear_adapter_store()
    clear_service_state()
    clear_regulatory_store()
    clear_prescription_store()
    clear_hitl_tasks()
    reset_coldchain_state()
    clear_vector_index()
    module_registry.clear()


# =============================================================================
# 1. Demand Cascade Graph (4-Tier In-Memory Execution)
# =============================================================================
@pytest.mark.asyncio
async def test_cascade_graph_fakellm_deterministic() -> None:
    """Cascade Graph: 4-tier propagation executes deterministically with in-memory agents."""
    corr_id = "test-cascade-fakellm-001"
    initial_state: CascadeState = {
        "event": {"source": "pos", "receipt_id": "REC-DET-001"},
        "correlation_id": corr_id,
        "pharmacy_id": "11111111-1111-1111-1111-111111111111",
        "product_id": "p-001-azithromycin",
        "batch_id": "b-azi-2026-01",
        "quantity": 3,
        "active_tiers": ["pharmacy", "stockist", "distributor", "manufacturer"],
        "pharmacy_result": None,
        "stockist_result": None,
        "distributor_result": None,
        "manufacturer_result": None,
        "hitl_status": None,
        "trace": [],
        "errors": [],
        "status": "pending",
    }

    result = await cascade_graph.ainvoke(
        initial_state,
        config={"configurable": {"thread_id": corr_id}},
    )

    assert result["status"] == "completed"
    assert result["pharmacy_result"] is not None
    assert result["stockist_result"] is not None
    assert result["distributor_result"] is not None
    assert result["manufacturer_result"] is not None
    assert len(result["trace"]) >= 4

    saved_trace = get_in_memory_cascade_trace(corr_id)
    assert saved_trace is not None
    assert saved_trace["status"] == "completed"


# =============================================================================
# 2. Adapter Forge Graph (Autonomous Code Synthesis & Validation)
# =============================================================================
@pytest.mark.asyncio
async def test_adapter_forge_graph_fakellm_deterministic() -> None:
    """Adapter Forge Graph: Generates, validates via AST, and registers translation adapter."""
    csv_fix = _resolve_fixture("fixtures/legacy/pharmacy_billing_sample.csv")
    exp_fix = _resolve_fixture("fixtures/legacy/pharmacy_billing_expected.json")

    csv_raw = csv_fix.read_text(encoding="utf-8")
    expected_output = json.loads(exp_fix.read_text(encoding="utf-8"))

    state = await run_forge(
        name="fakellm_csv_adapter",
        raw_sample=csv_raw,
        expected_output=expected_output,
        target_schema="SaleEvent",
    )

    assert state.get("status") == "succeeded"
    assert state.get("adapter_id") is not None
    assert state.get("version") == 1

    adapter = get_adapter("fakellm_csv_adapter")
    assert adapter is not None
    assert adapter["status"] == "active"
    assert adapter["test_results"]["passed"] is True
    code = adapter.get("generated_parser_code") or adapter.get("source_code") or ""
    assert "def run(" in code or "def transform(" in code


# =============================================================================
# 3. Regulatory Pipeline Graph (Diff Staging & Zero-Downtime Hot-Swap)
# =============================================================================
@pytest.mark.asyncio
async def test_regulatory_pipeline_graph_fakellm_deterministic() -> None:
    """Regulatory Graph: Parses gazette notification, extracts rules, executes staging test."""
    reg_fix = _resolve_fixture("fixtures/regulatory/nppa_price_ceiling_notice.txt")
    notice_text = reg_fix.read_text(encoding="utf-8")
    notice = crawl_regulatory_notice(text=notice_text, source="nppa", title="DPCO Notice")

    result = await run_regulatory_pipeline(
        notification_id=notice["id"],
        notification_text=notice["full_text"],
    )

    assert result["status"] == "awaiting_approval"
    assert result["target_module_name"] == "pricing_engine"
    assert result["v_new_code"] != ""
    assert result["diff"] != ""
    assert result["test_results"]["passed"] is True
    assert result["hitl_task_id"] is not None


# =============================================================================
# 4. Sovereign Prescription Compliance Graph (Vision & CDSCO Schedule H)
# =============================================================================
@pytest.mark.asyncio
async def test_prescription_graph_fakellm_deterministic() -> None:
    """Prescription Graph: OCR extraction, doctor verification, and CDSCO Schedule check."""
    rx_fix = _resolve_fixture("fixtures/prescriptions/valid_prescription.png")
    img_bytes = rx_fix.read_bytes()

    result = await run_prescription_graph(image_bytes=img_bytes)

    assert result["status"] == "approved"
    assert result["decision"] == "approve_dispense"
    assert result["doctor_verified"] is True
    assert result["doctor_name"] == "Dr. A. K. Sharma"
    assert result["doctor_registration_no"] == "MCI-2019-88412"


# =============================================================================
# 5. Cold-Chain Telemetry Graph (Arrhenius Degradation & Auto-Quarantine)
# =============================================================================
@pytest.mark.asyncio
async def test_coldchain_graph_fakellm_deterministic() -> None:
    """Cold-Chain Graph: Arrhenius degree-hour calculation and autonomous quarantine recommendation."""
    readings = {
        "temperature_c": 17.5,
        "humidity": 60.0,
        "shock_g": 0.2,
        "duration_minutes": 45.0,
        "mode": "excursion",
    }

    result = await run_coldchain_pipeline(
        batch_id="BIO-INS-01",
        readings=readings,
        node_id="22222222-2222-2222-2222-222222222222",
    )

    assert result["decision"] == "quarantine"
    assert result["quarantined"] is True
    assert result.get("rebalance_result") is not None


# =============================================================================
# 6. Network Copilot Graph (Read-Only Tool Executor Loop)
# =============================================================================
@pytest.mark.asyncio
async def test_copilot_graph_fakellm_deterministic() -> None:
    """Network Copilot Graph: Planner, read-only tool invocation, and answer generation."""
    scope = CopilotScope(
        user_id="usr-test-auditor",
        role="admin",
        node_id="00000000-0000-0000-0000-000000000000",
    )

    result = await run_copilot(
        question="Which pharmacies are at risk of running out of Paracetamol in North region?",
        scope=scope,
    )

    assert "get_stockout_risk" in result["tools_used"]
    assert result["answer"] != ""
    assert len(result["references"]) > 0


@pytest.mark.asyncio
async def test_copilot_graph_pharmacy_rls_disclaimer() -> None:
    """Network Copilot Graph: Enforces sovereign RLS isolation disclaimer for pharmacy callers."""
    pharmacy_node = "11111111-1111-1111-1111-111111111111"
    scope = CopilotScope(
        user_id="usr-pharm-01",
        role="pharmacy",
        node_id=pharmacy_node,
        tier="pharmacy",
    )

    result = await run_copilot(
        question="What is the current stockout risk across all North region pharmacies?",
        scope=scope,
    )

    assert result["answer"] != ""
    # Enforces sovereign RLS notice for pharmacy callers
    assert "sovereign rls isolation" in result["answer"].lower() or "restricted" in result["answer"].lower()
    assert pharmacy_node in result["answer"] or "your authorized pharmacy" in result["answer"].lower()

