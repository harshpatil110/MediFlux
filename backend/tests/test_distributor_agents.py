"""Unit and integration tests for Distributor Tier agents (SettlementAgent, TransitOptimizationAgent).

Covers:
1. Dynamic AST/WASM module margin change hot-swapping without code edits or server restart.
2. Partner trade financing fallback on credit limit breach.
3. Cold-chain strict reefer-only vehicle assignment constraint.
4. Lifesaving therapeutics emergency priority sequencing (sequence=1, priority='critical').
5. Cross-border HITL requirement flagging.
6. Cascade graph distributor tier end-to-end integration and partial rejection halting.
"""

import uuid
from unittest.mock import patch

import pytest

from app.agents.bootstrap_agent import bootstrap_agent
from app.agents.settlement_agent import SettlementAgent, SettlementDecision
from app.agents.transit_agent import DispatchPlan, TransitOptimizationAgent
from app.core.config import settings
from app.graphs.cascade import CascadeState, build_cascade_graph
from app.modules_runtime.registry import module_registry
from app.tools.distributor_tools import (
    clear_in_memory_settlements,
    clear_in_memory_shipments,
    clear_mock_bank_finance_override,
    clear_mock_credit_accounts,
    clear_mock_vehicles,
    set_mock_bank_finance_decision,
    set_mock_credit_account,
    set_mock_vehicles,
)


@pytest.fixture(autouse=True)
def setup_distributor_environment():
    """Setup and clean in-memory stores, mock settings offline, and bootstrap modules before each test."""
    with patch.object(settings, "SUPABASE_URL", ""), \
         patch.object(settings, "NVIDIA_API_KEY", None), \
         patch.object(settings, "OPENROUTER_API_KEY", None), \
         patch.object(settings, "OLLAMA_BASE_URL", ""):
        clear_in_memory_settlements()
        clear_in_memory_shipments()
        clear_mock_bank_finance_override()
        clear_mock_credit_accounts()
        clear_mock_vehicles()
        bootstrap_agent.bootstrap_all_modules()
        yield
        clear_in_memory_settlements()
        clear_in_memory_shipments()
        clear_mock_bank_finance_override()
        clear_mock_credit_accounts()
        clear_mock_vehicles()


@pytest.mark.asyncio
async def test_dynamic_module_margin_change():
    """Verify that updating the active margin_rules module dynamically changes settlement calculations."""
    agent = SettlementAgent()
    buyer_id = "test-buyer-dynamic-margin"
    set_mock_credit_account(
        buyer_id,
        {
            "node_id": buyer_id,
            "credit_limit": 500000.0,
            "current_balance": 10000.0,
            "outstanding_balance": 10000.0,
        },
    )

    state = {
        "buyer_id": buyer_id,
        "quantity": 100,
        "unit_price": 100.0,
        "correlation_id": "corr-margin-v1",
    }

    # 1. Execute under default v1 margin_rules (cost=85, selling=100 -> 15% margin)
    decision_v1: SettlementDecision = await agent.evaluate_settlement(state)
    assert decision_v1.approved is True
    assert decision_v1.margin_percentage == 15.0

    # 2. Hot-swap margin_rules to v2 with 20% margin policy
    v2_code = """def run(input: dict) -> dict:
    cost = float(input.get("cost_price", 0.0))
    selling = float(input.get("selling_price", 0.0))
    if selling <= 0:
        return {"margin_percentage": 0.20, "margin_inr": 0.0, "meets_minimum": True, "flagged": False}
    return {
        "margin_percentage": 0.20,
        "margin_inr": round(selling * 0.20, 2),
        "meets_minimum": True,
        "flagged": False,
    }
"""
    v2_tests = """def test_run():
    assert run({})["margin_percentage"] == 0.20
"""
    ver = module_registry.create_version("margin_rules", "margin_rules", v2_code, v2_tests)
    module_registry.activate("margin_rules", ver.version)

    # 3. Re-execute SettlementAgent with zero code change or restart
    state["correlation_id"] = "corr-margin-v2"
    decision_v2: SettlementDecision = await agent.evaluate_settlement(state)
    assert decision_v2.approved is True
    # Assert margin changed dynamically to 20%
    assert decision_v2.margin_percentage == 20.0

    # Roll back to previous version for fixture hygiene
    module_registry.rollback("margin_rules")


@pytest.mark.asyncio
async def test_trade_financing_fallback():
    """Verify trade financing fallback when order amount exceeds buyer available credit."""
    agent = SettlementAgent()
    buyer_id = "test-buyer-credit-limit-breach"

    # Set buyer credit limit to 10,000 INR with 9,500 INR used -> available credit is 500 INR
    set_mock_credit_account(
        buyer_id,
        {
            "node_id": buyer_id,
            "credit_limit": 10000.0,
            "current_balance": 9500.0,
            "outstanding_balance": 9500.0,
        },
    )

    # Order of 50 units @ 100 INR = 5,000 INR (far exceeds 500 INR available)
    state = {
        "buyer_id": buyer_id,
        "quantity": 50,
        "unit_price": 100.0,
        "correlation_id": "corr-trade-fin-001",
    }

    # Case A: Bank financing approved
    set_mock_bank_finance_decision(approved=True, reason="Underwriting approved based on 750 score")
    decision_approved: SettlementDecision = await agent.evaluate_settlement(state)
    assert decision_approved.approved is True
    assert decision_approved.financing_needed is True
    assert decision_approved.financing_approved is True
    assert "Trade Financing" in decision_approved.reasoning

    # Case B: Bank financing rejected
    set_mock_bank_finance_decision(approved=False, reason="Debt-to-income ratio exceeded")
    decision_rejected: SettlementDecision = await agent.evaluate_settlement(state)
    assert decision_rejected.approved is False
    assert decision_rejected.financing_needed is True
    assert decision_rejected.financing_approved is False
    assert "Credit limit exceeded and trade financing rejected by bank." in decision_rejected.reasoning


@pytest.mark.asyncio
async def test_cold_chain_vehicle_assignment():
    """Verify cold-chain orders are STRICTLY assigned to reefer vehicles and never to ambient vehicles."""
    agent = TransitOptimizationAgent()
    distributor_id = "test-distributor-cold-chain"

    # Setup mixed fleet: 1 ambient van, 1 reefer truck
    set_mock_vehicles([
        {
            "id": "dry-van-01",
            "distributor_id": distributor_id,
            "license_plate": "DL-01-DRY-101",
            "capacity_kg": 1500,
            "is_reefer": False,
            "is_available": True,
            "status": "available",
        },
        {
            "id": "reefer-truck-02",
            "distributor_id": distributor_id,
            "license_plate": "DL-02-REF-202",
            "capacity_kg": 2500,
            "is_reefer": True,
            "status": "available",
            "is_available": True,
        },
    ])

    state = {
        "distributor_id": distributor_id,
        "order_id": "ord-cold-insulin-001",
        "product_id": "p-insulin-r",
        "is_cold_chain": True,
        "is_lifesaving": False,
        "quantity": 200,
        "correlation_id": "corr-cold-chain-001",
    }

    plan: DispatchPlan = await agent.evaluate_dispatch(state)
    assert len(plan.shipments) == 1
    shipment = plan.shipments[0]

    # Must be strictly assigned to the reefer vehicle
    assert shipment.is_cold_chain is True
    assert shipment.vehicle_id == "reefer-truck-02"
    assert shipment.vehicle_plate == "DL-02-REF-202"
    assert shipment.priority in ("high", "critical")


@pytest.mark.asyncio
async def test_lifesaving_priority_sequencing():
    """Verify orders with is_lifesaving=True receive top dispatch sequence (1) and critical priority."""
    agent = TransitOptimizationAgent()
    distributor_id = "test-distributor-lifesaving"

    set_mock_vehicles([
        {
            "id": "veh-std-1",
            "distributor_id": distributor_id,
            "license_plate": "DL-01-STD-001",
            "is_reefer": False,
            "is_available": True,
        },
        {
            "id": "veh-ref-2",
            "distributor_id": distributor_id,
            "license_plate": "DL-02-REF-002",
            "is_reefer": True,
            "is_available": True,
        },
        {
            "id": "veh-std-3",
            "distributor_id": distributor_id,
            "license_plate": "DL-03-STD-003",
            "is_reefer": False,
            "is_available": True,
        },
    ])

    # Batch containing standard, cold-chain, and lifesaving medicines
    state = {
        "distributor_id": distributor_id,
        "orders": [
            {
                "order_id": "ord-std-paracetamol",
                "product_id": "p-paracetamol-500",
                "is_cold_chain": False,
                "is_lifesaving": False,
                "quantity": 500,
            },
            {
                "order_id": "ord-cold-vaccine",
                "product_id": "p-covaxin",
                "is_cold_chain": True,
                "is_lifesaving": False,
                "quantity": 100,
            },
            {
                "order_id": "ord-life-epinephrine",
                "product_id": "p-epinephrine-inj",
                "is_cold_chain": False,
                "is_lifesaving": True,
                "quantity": 50,
            },
        ],
        "correlation_id": "corr-lifesaving-001",
    }

    plan: DispatchPlan = await agent.evaluate_dispatch(state)
    assert len(plan.shipments) == 3

    # Find the lifesaving shipment
    life_shipment = next(s for s in plan.shipments if "ord-life-epinephrine" in s.order_ids)
    cold_shipment = next(s for s in plan.shipments if "ord-cold-vaccine" in s.order_ids)
    std_shipment = next(s for s in plan.shipments if "ord-std-paracetamol" in s.order_ids)

    # Lifesaving order must have sequence 1 and priority 'critical'
    assert life_shipment.sequence == 1
    assert life_shipment.priority == "critical"
    assert life_shipment.eta_hours <= 1.0

    # Cold chain must be assigned to reefer
    assert cold_shipment.is_cold_chain is True
    assert cold_shipment.vehicle_id == "veh-ref-2"

    # Standard order sequenced after critical
    assert std_shipment.sequence > 1


@pytest.mark.asyncio
async def test_cross_border_hitl_requirement():
    """Verify shipments crossing regional/international borders flag requires_hitl=True."""
    agent = TransitOptimizationAgent()
    distributor_id = "test-distributor-cross-border"

    set_mock_vehicles([
        {
            "id": "veh-cross-1",
            "distributor_id": distributor_id,
            "license_plate": "DL-09-CB-909",
            "is_reefer": False,
            "is_available": True,
        },
    ])

    state = {
        "distributor_id": distributor_id,
        "order_id": "ord-cross-border-001",
        "product_id": "p-export-medicine",
        "is_cold_chain": False,
        "is_lifesaving": False,
        "is_cross_border": True,
        "quantity": 1000,
        "correlation_id": "corr-cross-border-001",
    }

    plan: DispatchPlan = await agent.evaluate_dispatch(state)
    assert len(plan.shipments) == 1
    shipment = plan.shipments[0]

    assert shipment.requires_hitl is True
    assert shipment.eta_hours >= 4.0


@pytest.mark.asyncio
async def test_cascade_distributor_integration():
    """Verify distributor tier in full cascade execution properly populates settlement_result and distributor_result."""
    graph = build_cascade_graph()
    corr_id = f"test-corr-dist-cascade-{uuid.uuid4().hex[:6]}"

    initial_state: CascadeState = {
        "event": {"source": "pos", "quantity": 10},
        "correlation_id": corr_id,
        "pharmacy_id": "11111111-1111-1111-1111-111111111111",
        "product_id": "p-001-azithromycin",
        "batch_id": "b-azi-2026-01",
        "quantity": 10,
        "active_tiers": ["pharmacy", "stockist", "distributor", "manufacturer"],
        "pharmacy_result": None,
        "stockist_result": None,
        "settlement_result": None,
        "distributor_result": None,
        "manufacturer_result": None,
        "hitl_status": None,
        "trace": [],
        "errors": [],
        "status": "pending",
    }

    result = await graph.ainvoke(
        initial_state,
        config={"configurable": {"thread_id": corr_id}},
    )

    assert result["status"] == "completed"
    assert result["settlement_result"] is not None
    assert result["settlement_result"]["approved"] is True
    assert result["distributor_result"] is not None
    assert len(result["distributor_result"]["shipments"]) >= 1


@pytest.mark.asyncio
async def test_cascade_distributor_rejection_halts_propagation():
    """Verify that if settlement is rejected, cascade stops at distributor and halts propagation to manufacturer."""
    graph = build_cascade_graph()
    corr_id = f"test-corr-dist-reject-{uuid.uuid4().hex[:6]}"
    buyer_id = "test-buyer-insolvent"

    # Set buyer with 0 available credit and reject bank financing
    set_mock_credit_account(
        buyer_id,
        {
            "node_id": buyer_id,
            "credit_limit": 5000.0,
            "current_balance": 5000.0,
            "outstanding_balance": 5000.0,
        },
    )
    set_mock_bank_finance_decision(approved=False, reason="Insolvency risk")

    initial_state: CascadeState = {
        "event": {"source": "pos", "quantity": 500},
        "correlation_id": corr_id,
        "pharmacy_id": buyer_id,
        "product_id": "p-001-azithromycin",
        "batch_id": "b-azi-2026-01",
        "quantity": 500,
        "active_tiers": ["pharmacy", "stockist", "distributor", "manufacturer"],
        "pharmacy_result": None,
        "stockist_result": None,
        "settlement_result": None,
        "distributor_result": None,
        "manufacturer_result": None,
        "hitl_status": None,
        "trace": [],
        "errors": [],
        "status": "pending",
    }

    result = await graph.ainvoke(
        initial_state,
        config={"configurable": {"thread_id": corr_id}},
    )

    # Status must be partial due to halted settlement
    assert result["status"] == "partial"
    assert result["settlement_result"] is not None
    assert result["settlement_result"]["approved"] is False
    # Manufacturer tier must NOT have executed
    assert result["manufacturer_result"] is None
