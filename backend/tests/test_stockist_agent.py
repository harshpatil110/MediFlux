"""Deterministic unit and integration tests for Task 12: Stockist Tier Dynamic Balancing Agent."""

import uuid
from unittest.mock import patch

import pytest

from app.agents.pharmacy_agent import clear_in_memory_orders, get_in_memory_orders
from app.agents.stockist_agent import (
    StockistAgent,
)
from app.agents.testing import FakeLLM
from app.core.config import settings
from app.graphs.cascade import CascadeState, cascade_graph
from app.tools.pharmacy_tools import clear_mock_inventory, set_mock_inventory
from app.tools.stockist_tools import (
    clear_in_memory_transfers,
    clear_mock_cluster_inventory,
    clear_mock_demand_trends,
    create_order,
    create_transfer,
    get_cluster_inventory,
    get_demand_trend,
    get_in_memory_transfers,
    list_nodes_in_cluster,
    set_mock_cluster_inventory,
)

STOCKIST_LOCAL_ID = "22222222-2222-2222-2222-222222222222"
STOCKIST_PEER_ID = "22222222-2222-2222-2222-222222222223"
DISTRIBUTOR_ID = "33333333-3333-3333-3333-333333333333"
PHARMACY_ID = "11111111-1111-1111-1111-111111111111"
PRODUCT_AZI = "p-001-azithromycin"
PRODUCT_INSULIN = "p-003-insulin-glargine"


@pytest.fixture(autouse=True)
def clean_test_environment():
    """Reset test state, orders, transfers, and mock inventory before and after each test."""
    clear_in_memory_transfers()
    clear_in_memory_orders()
    clear_mock_inventory()
    clear_mock_cluster_inventory()
    clear_mock_demand_trends()
    with patch.object(settings, "SUPABASE_URL", ""), \
         patch.object(settings, "SUPABASE_SERVICE_ROLE_KEY", ""), \
         patch.object(settings, "NVIDIA_API_KEY", None), \
         patch.object(settings, "OPENROUTER_API_KEY", None), \
         patch.object(settings, "OLLAMA_BASE_URL", ""):
        yield
    clear_in_memory_transfers()
    clear_in_memory_orders()
    clear_mock_inventory()
    clear_mock_cluster_inventory()
    clear_mock_demand_trends()


# -----------------------------------------------------------------------------
# 1. Local Fulfillment Test
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_fulfill_local():
    """Stockist has 100 units; pharmacy requests 20 units.

    Assert action == 'fulfill_local' and no transfers or escalation orders are created.
    """
    corr_id = f"corr-fulfill-local-{uuid.uuid4()}"

    set_mock_inventory(
        STOCKIST_LOCAL_ID,
        [
            {
                "node_id": STOCKIST_LOCAL_ID,
                "product_id": PRODUCT_AZI,
                "quantity": 100,
                "safety_stock": 20,
                "max_capacity": 500,
            }
        ],
    )

    state = {
        "pharmacy_result": {
            "needed": True,
            "quantity": 20,
            "target_stockist_id": STOCKIST_LOCAL_ID,
            "product_id": PRODUCT_AZI,
            "urgency": "medium",
            "compliance_hold": False,
        },
        "stockist_id": STOCKIST_LOCAL_ID,
        "product_id": PRODUCT_AZI,
        "quantity": 20,
        "correlation_id": corr_id,
        "local_stock": 100,
    }

    agent = StockistAgent(router=FakeLLM())
    decision = await agent.run(state=state)

    assert decision.action == "fulfill_local"
    assert decision["action"] == "fulfill_local"
    assert len(decision.transfers) == 0
    assert decision.escalation_order_id is None
    assert "sufficient" in decision.reasoning.lower()

    # Verify NO transfers or distributor escalation orders created
    assert len(get_in_memory_transfers()) == 0
    assert len(get_in_memory_orders()) == 0


# -----------------------------------------------------------------------------
# 2. Peer Transfer Test
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_transfer_from_peer():
    """Local stockist has 5 units (shortage); peer stockist in cluster has 80 units.

    Pharmacy requests 30 units.
    Assert action == 'transfer_from_peer', transfers list contains valid transfer spec,
    and transfers table row is created in Supabase / in-memory store.
    """
    corr_id = f"corr-peer-transfer-{uuid.uuid4()}"

    # Setup local stockist shortage (5) and peer stockist surplus (80 with safety stock 20 -> 60 surplus)
    set_mock_inventory(
        STOCKIST_LOCAL_ID,
        [{"node_id": STOCKIST_LOCAL_ID, "product_id": PRODUCT_AZI, "quantity": 5, "safety_stock": 20}],
    )

    set_mock_cluster_inventory(
        "CLUSTER-DELHI-NORTH",
        PRODUCT_AZI,
        [
            {"node_id": STOCKIST_LOCAL_ID, "quantity": 5, "safety_stock": 20, "surplus": 0},
            {"node_id": STOCKIST_PEER_ID, "quantity": 80, "safety_stock": 20, "surplus": 60},
        ],
    )

    state = {
        "pharmacy_result": {
            "needed": True,
            "quantity": 30,
            "target_stockist_id": STOCKIST_LOCAL_ID,
            "product_id": PRODUCT_AZI,
            "urgency": "medium",
            "compliance_hold": False,
        },
        "stockist_id": STOCKIST_LOCAL_ID,
        "product_id": PRODUCT_AZI,
        "quantity": 30,
        "correlation_id": corr_id,
        "local_stock": 5,
    }

    agent = StockistAgent(router=FakeLLM())
    decision = await agent.run(state=state)

    assert decision.action == "transfer_from_peer"
    assert decision["action"] == "transfer_from_peer"
    assert len(decision.transfers) >= 1
    assert decision.escalation_order_id is None

    # Check spec values
    transfer_spec = decision.transfers[0]
    assert transfer_spec.from_stockist_id == STOCKIST_PEER_ID
    assert transfer_spec.to_stockist_id == STOCKIST_LOCAL_ID
    assert transfer_spec.product_id == PRODUCT_AZI
    assert transfer_spec.quantity == 25  # 30 requested - 5 local = 25 shortfall

    # Check transfer table row created
    transfers = get_in_memory_transfers()
    assert len(transfers) >= 1
    row = transfers[0]
    assert row["from_node_id"] == STOCKIST_PEER_ID
    assert row["to_node_id"] == STOCKIST_LOCAL_ID
    assert row["product_id"] == PRODUCT_AZI
    assert row["quantity"] == 25
    assert row["status"] == "pending"
    assert row["correlation_id"] == corr_id


# -----------------------------------------------------------------------------
# 3. Cluster Escalation Test
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_escalate_to_distributor():
    """Entire cluster stockist inventory is 10 units; pharmacy requests 100 units.

    Assert action == 'escalate_to_distributor' and an escalation order to the distributor
    is inserted into orders table.
    """
    corr_id = f"corr-cluster-escalate-{uuid.uuid4()}"

    set_mock_inventory(
        STOCKIST_LOCAL_ID,
        [{"node_id": STOCKIST_LOCAL_ID, "product_id": PRODUCT_AZI, "quantity": 10, "safety_stock": 20}],
    )

    set_mock_cluster_inventory(
        "CLUSTER-DELHI-NORTH",
        PRODUCT_AZI,
        [
            {"node_id": STOCKIST_LOCAL_ID, "quantity": 10, "safety_stock": 20, "surplus": 0},
            {"node_id": STOCKIST_PEER_ID, "quantity": 0, "safety_stock": 20, "surplus": 0},
        ],
    )

    state = {
        "pharmacy_result": {
            "needed": True,
            "quantity": 100,
            "target_stockist_id": STOCKIST_LOCAL_ID,
            "product_id": PRODUCT_AZI,
            "urgency": "medium",
            "compliance_hold": False,
        },
        "stockist_id": STOCKIST_LOCAL_ID,
        "product_id": PRODUCT_AZI,
        "quantity": 100,
        "correlation_id": corr_id,
        "local_stock": 10,
    }

    agent = StockistAgent(router=FakeLLM())
    decision = await agent.run(state=state)

    assert decision.action == "escalate_to_distributor"
    assert decision["action"] == "escalate_to_distributor"
    assert decision.escalation_order_id is not None
    assert len(decision.transfers) == 0

    # Assert escalation purchase order is created in orders store
    orders = get_in_memory_orders()
    assert len(orders) >= 1
    esc_order = next(o for o in orders if o["id"] == decision.escalation_order_id)
    assert esc_order["status"] == "requested"
    assert esc_order["pharmacy_id"] == STOCKIST_LOCAL_ID  # Escalating node
    assert esc_order["stockist_id"] == DISTRIBUTOR_ID     # Target distributor
    assert esc_order["product_id"] == PRODUCT_AZI
    assert esc_order["quantity"] == 90                     # 100 - 10 = 90 deficit
    assert esc_order["correlation_id"] == corr_id


# -----------------------------------------------------------------------------
# 4. Lifesaving / Cold-Chain Priority Elevation Test
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_lifesaving_priority_elevation():
    """Request a lifesaving/cold-chain product under stock scarcity.

    Assert output priority is elevated to 'critical' or 'high'.
    """
    corr_id = f"corr-prio-elevate-{uuid.uuid4()}"

    set_mock_inventory(
        STOCKIST_LOCAL_ID,
        [{"node_id": STOCKIST_LOCAL_ID, "product_id": PRODUCT_INSULIN, "quantity": 0, "safety_stock": 10}],
    )

    set_mock_cluster_inventory(
        "CLUSTER-DELHI-NORTH",
        PRODUCT_INSULIN,
        [
            {"node_id": STOCKIST_LOCAL_ID, "quantity": 0, "safety_stock": 10, "surplus": 0},
            {"node_id": STOCKIST_PEER_ID, "quantity": 0, "safety_stock": 10, "surplus": 0},
        ],
    )

    state = {
        "pharmacy_result": {
            "needed": True,
            "quantity": 15,
            "target_stockist_id": STOCKIST_LOCAL_ID,
            "product_id": PRODUCT_INSULIN,
            "urgency": "low",  # Injected low, should be boosted
            "compliance_hold": False,
        },
        "stockist_id": STOCKIST_LOCAL_ID,
        "product_id": PRODUCT_INSULIN,
        "quantity": 15,
        "correlation_id": corr_id,
        "local_stock": 0,
        "is_lifesaving": True,
        "is_cold_chain": True,
    }

    agent = StockistAgent(router=FakeLLM())
    decision = await agent.run(state=state)

    # Priority must be elevated to critical or high
    assert decision.priority in ("critical", "high")
    assert decision.action == "escalate_to_distributor"


# -----------------------------------------------------------------------------
# 5. Direct Stockist Tools Execution Test
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_stockist_tools_direct_execution():
    """Verify list_nodes_in_cluster, get_cluster_inventory, get_demand_trend, create_transfer, create_order."""
    # 1. list_nodes_in_cluster
    nodes = await list_nodes_in_cluster(node_id=STOCKIST_LOCAL_ID)
    assert len(nodes) >= 2
    assert any(n["id"] == STOCKIST_LOCAL_ID for n in nodes)
    assert any(n["id"] == STOCKIST_PEER_ID for n in nodes)

    # 2. get_cluster_inventory
    set_mock_cluster_inventory(
        "CLUSTER-DELHI-NORTH",
        PRODUCT_AZI,
        [
            {"node_id": STOCKIST_LOCAL_ID, "quantity": 40, "safety_stock": 20, "surplus": 20},
            {"node_id": STOCKIST_PEER_ID, "quantity": 60, "safety_stock": 20, "surplus": 40},
        ],
    )
    inv = await get_cluster_inventory(cluster_id="CLUSTER-DELHI-NORTH", product_id=PRODUCT_AZI)
    assert len(inv) == 2
    assert inv[0]["surplus"] == 20
    assert inv[1]["surplus"] == 40

    # 3. get_demand_trend
    trend = await get_demand_trend(node_id=STOCKIST_LOCAL_ID, product_id=PRODUCT_AZI)
    assert "velocity_units_per_hour" in trend
    assert "predicted_depletion_hours" in trend

    # 4. create_transfer
    xfer = await create_transfer(
        from_node_id=STOCKIST_PEER_ID,
        to_node_id=STOCKIST_LOCAL_ID,
        product_id=PRODUCT_AZI,
        quantity=15,
        priority="high",
        correlation_id="test-xfer-direct",
    )
    assert xfer["status"] == "pending"
    assert xfer["quantity"] == 15
    assert len(get_in_memory_transfers()) >= 1

    # 5. create_order
    ord_rec = await create_order(
        from_node_id=STOCKIST_LOCAL_ID,
        to_node_id=DISTRIBUTOR_ID,
        product_id=PRODUCT_AZI,
        quantity=50,
        priority="high",
        correlation_id="test-order-direct",
    )
    assert ord_rec["status"] == "requested"
    assert ord_rec["quantity"] == 50
    assert len(get_in_memory_orders()) >= 1


# -----------------------------------------------------------------------------
# 6. Cascade Graph Execution with StockistAgent Integration
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_cascade_graph_invokes_stockist_agent():
    """Verify that cascade_graph executes stockist_node with StockistAgent, updating trace and state."""
    corr_id = f"test-cascade-stk-{uuid.uuid4()}"

    set_mock_inventory(
        PHARMACY_ID,
        [{"node_id": PHARMACY_ID, "product_id": PRODUCT_AZI, "quantity": 2, "safety_stock": 10, "max_capacity": 50}],
    )
    set_mock_inventory(
        STOCKIST_LOCAL_ID,
        [{"node_id": STOCKIST_LOCAL_ID, "product_id": PRODUCT_AZI, "quantity": 100, "safety_stock": 20, "max_capacity": 500}],
    )

    initial_state: CascadeState = {
        "event": {
            "type": "sale",
            "source": "pos",
            "payload": {
                "product_id": PRODUCT_AZI,
                "schedule_type": "Schedule H",
                "prescription_ref": "DOC-IND-001",
            },
        },
        "correlation_id": corr_id,
        "pharmacy_id": PHARMACY_ID,
        "product_id": PRODUCT_AZI,
        "batch_id": "b-azi-001",
        "quantity": 2,
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
    assert result["stockist_result"]["action"] in ("fulfill_local", "transfer_from_peer", "escalate_to_distributor")

    # Check trace includes StockistAgent
    stk_trace = next(t for t in result["trace"] if t["tier"] == "stockist")
    assert stk_trace["agent_name"] == "StockistAgent"
    assert stk_trace["status"] == "success"
