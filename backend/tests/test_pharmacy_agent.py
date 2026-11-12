"""Deterministic unit and integration tests for Task 11: Pharmacy Tier Inventory Telemetry Agent."""

import uuid
from unittest.mock import MagicMock, patch

import pytest

from app.agents.pharmacy_agent import (
    PharmacyAgent,
    clear_in_memory_orders,
    get_in_memory_orders,
)
from app.agents.testing import FakeLLM
from app.core.config import settings
from app.graphs.cascade import CascadeState, cascade_graph
from app.tools.pharmacy_tools import (
    check_prescription_link,
    clear_mock_batches,
    clear_mock_events,
    clear_mock_inventory,
    clear_mock_sales,
    get_batches_near_expiry,
    get_inventory,
    set_mock_batches,
    set_mock_event,
    set_mock_inventory,
)

PHARMACY_ID = "11111111-1111-1111-1111-111111111111"
STOCKIST_ID = "22222222-2222-2222-2222-222222222222"
PRODUCT_AZI = "p-001-azithromycin"
PRODUCT_PCM = "p-002-paracetamol"


@pytest.fixture(autouse=True)
def clean_test_environment():
    """Reset test state, orders, mock inventory, batches, and events before and after each test."""
    clear_in_memory_orders()
    clear_mock_inventory()
    clear_mock_batches()
    clear_mock_sales()
    clear_mock_events()
    with patch.object(settings, "SUPABASE_URL", ""), \
         patch.object(settings, "SUPABASE_SERVICE_ROLE_KEY", ""), \
         patch.object(settings, "NVIDIA_API_KEY", None), \
         patch.object(settings, "OPENROUTER_API_KEY", None), \
         patch.object(settings, "OLLAMA_BASE_URL", ""):
        yield
    clear_in_memory_orders()
    clear_mock_inventory()
    clear_mock_batches()
    clear_mock_sales()
    clear_mock_events()


# -----------------------------------------------------------------------------
# 1. Safety Stock Replenishment Test
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_safety_stock_replenishment():
    """Inject a sale event that drops stock below safety_stock.

    Assert PharmacyAgent output returns needed=True, valid quantity, and an orders row
    with status 'requested' is created in Supabase (or in-memory mock store).
    """
    corr_id = f"corr-replenish-{uuid.uuid4()}"

    # Setup inventory with stock (5) below safety_stock (20), max capacity (100)
    set_mock_inventory(
        PHARMACY_ID,
        [
            {
                "node_id": PHARMACY_ID,
                "product_id": PRODUCT_PCM,
                "sku": "MED-PCM-650",
                "quantity": 5,
                "safety_stock": 20,
                "max_capacity": 100,
            }
        ],
    )

    state = {
        "event": {
            "type": "sale",
            "event_id": "evt-sale-001",
            "payload": {
                "product_id": PRODUCT_PCM,
                "sku": "MED-PCM-650",
                "quantity": 2,
                "schedule_type": "OTC",
            },
        },
        "pharmacy_id": PHARMACY_ID,
        "product_id": PRODUCT_PCM,
        "quantity": 2,
        "correlation_id": corr_id,
        "current_stock": 5,
    }

    # Deterministic FakeLLM
    fake_llm = FakeLLM()
    agent = PharmacyAgent(router=fake_llm)

    output = await agent.run(state=state)

    # 1. Assertions on PharmacyAgent output
    assert output.needed is True
    assert output["needed"] is True
    assert output.quantity > 0
    assert output.compliance_hold is False
    assert output.target_stockist_id == STOCKIST_ID
    assert "safety stock" in output.reason.lower()

    # 2. Assert orders row created with status 'requested'
    orders = get_in_memory_orders()
    assert len(orders) == 1
    order = orders[0]
    assert order["status"] == "requested"
    assert order["pharmacy_id"] == PHARMACY_ID
    assert order["stockist_id"] == STOCKIST_ID
    assert order["product_id"] == PRODUCT_PCM
    assert order["quantity"] == output.quantity
    assert order["priority"] == output.urgency
    assert order["correlation_id"] == corr_id
    assert order["metadata"]["is_synthetic"] is True


# -----------------------------------------------------------------------------
# 2. Event Type Handling Test (return & expiry_alert)
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_return_and_expiry_events():
    """Verify return event (damaged item) reflects replacement logic and expiry_alert populates FEFO flags."""
    corr_id = f"corr-events-{uuid.uuid4()}"

    # A) Test Damaged Return Event
    set_mock_inventory(
        PHARMACY_ID,
        [
            {
                "node_id": PHARMACY_ID,
                "product_id": PRODUCT_AZI,
                "sku": "MED-AZI-500",
                "quantity": 8,
                "safety_stock": 20,
                "max_capacity": 100,
            }
        ],
    )

    damaged_state = {
        "event": {
            "type": "return",
            "event_id": "evt-ret-001",
            "payload": {
                "condition": "damaged",
                "quantity": 5,
                "product_id": PRODUCT_AZI,
                "return_reason": "Broken blister seal during transit",
            },
        },
        "pharmacy_id": PHARMACY_ID,
        "product_id": PRODUCT_AZI,
        "correlation_id": corr_id,
    }

    agent = PharmacyAgent(router=FakeLLM())
    res_damaged = await agent.run(state=damaged_state)

    assert res_damaged.needed is True
    assert res_damaged.compliance_hold is False
    assert res_damaged.quantity >= 5
    assert "damaged return" in res_damaged.reason.lower()
    assert "disposal" in res_damaged.reason.lower()

    # Verify order was created for replacement
    orders = get_in_memory_orders()
    assert len(orders) >= 1
    assert orders[-1]["status"] == "requested"
    assert orders[-1]["product_id"] == PRODUCT_AZI

    # B) Test Expiry Alert Event
    clear_in_memory_orders()
    set_mock_batches(
        PHARMACY_ID,
        [
            {
                "batch_id": "b-azi-exp-001",
                "sku": "MED-AZI-500",
                "product_id": PRODUCT_AZI,
                "days_to_expiry": 14,
                "quantity_affected": 30,
            },
            {
                "batch_id": "b-azi-exp-002",
                "sku": "MED-AZI-500",
                "product_id": PRODUCT_AZI,
                "days_to_expiry": -2,
                "quantity_affected": 10,
            },
        ],
    )

    expiry_state = {
        "event": {
            "type": "expiry_alert",
            "event_id": "evt-exp-001",
            "payload": {
                "pharmacy_id": PHARMACY_ID,
                "threshold_days": 30,
            },
        },
        "pharmacy_id": PHARMACY_ID,
        "product_id": PRODUCT_AZI,
        "correlation_id": corr_id,
    }

    res_expiry = await agent.run(state=expiry_state)

    assert len(res_expiry.expiry_flags) == 2
    fefo_flag = next(f for f in res_expiry.expiry_flags if f.batch_id == "b-azi-exp-001")
    assert fefo_flag.recommendation == "FEFO_ORDER_REQUIRED"
    assert fefo_flag.days_to_expiry == 14
    assert fefo_flag.quantity_affected == 30

    expired_flag = next(f for f in res_expiry.expiry_flags if f.batch_id == "b-azi-exp-002")
    assert expired_flag.recommendation == "MARK_FOR_REMOVAL"
    assert expired_flag.days_to_expiry == -2
    assert expired_flag.quantity_affected == 10

    assert res_expiry.urgency == "critical"
    assert "fefo" in res_expiry.reason.lower()


# -----------------------------------------------------------------------------
# 3. Schedule H Compliance Hold Test
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_schedule_h_compliance_hold():
    """Inject a sale event for a Schedule H product with missing prescription reference.

    Assert output returns compliance_hold=True, urgency='high', and NO purchase order
    is created in orders table.
    """
    corr_id = f"corr-hold-{uuid.uuid4()}"

    set_mock_inventory(
        PHARMACY_ID,
        [
            {
                "node_id": PHARMACY_ID,
                "product_id": PRODUCT_AZI,
                "sku": "MED-AZI-500",
                "quantity": 2,  # Critically low stock
                "safety_stock": 20,
                "max_capacity": 100,
            }
        ],
    )

    # Sale event without prescription reference for Schedule H antibiotic
    state = {
        "event": {
            "type": "sale",
            "event_id": "evt-sale-sch-h-unlinked",
            "payload": {
                "product_id": PRODUCT_AZI,
                "sku": "MED-AZI-500",
                "quantity": 1,
                "schedule_type": "Schedule H",
                "prescription_ref": None,
            },
        },
        "pharmacy_id": PHARMACY_ID,
        "product_id": PRODUCT_AZI,
        "quantity": 1,
        "correlation_id": corr_id,
        "current_stock": 2,
    }

    agent = PharmacyAgent(router=FakeLLM())
    output = await agent.run(state=state)

    # Assert compliance hold triggered
    assert output.compliance_hold is True
    assert output["compliance_hold"] is True
    assert output.urgency == "high"
    assert "schedule h compliance hold" in output.reason.lower()
    assert "prescription" in output.reason.lower()

    # Crucial assertion: NO purchase order created in orders table
    orders = get_in_memory_orders()
    assert len(orders) == 0, "No purchase order should be created when compliance hold is active"


# -----------------------------------------------------------------------------
# 4. Schedule H with Valid Registered Doctor Prescription
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_schedule_h_with_valid_prescription():
    """Verify that Schedule H sale with valid registered doctor reference passes compliance and triggers order."""
    corr_id = f"corr-valid-rx-{uuid.uuid4()}"

    set_mock_inventory(
        PHARMACY_ID,
        [
            {
                "node_id": PHARMACY_ID,
                "product_id": PRODUCT_AZI,
                "sku": "MED-AZI-500",
                "quantity": 4,
                "safety_stock": 20,
                "max_capacity": 100,
            }
        ],
    )

    state = {
        "event": {
            "type": "sale",
            "event_id": "evt-sale-valid-rx",
            "payload": {
                "product_id": PRODUCT_AZI,
                "sku": "MED-AZI-500",
                "quantity": 2,
                "schedule_type": "Schedule H",
                "prescription_ref": "DOC-IND-001",  # Dr. Rajesh Sharma
            },
        },
        "pharmacy_id": PHARMACY_ID,
        "product_id": PRODUCT_AZI,
        "quantity": 2,
        "correlation_id": corr_id,
        "current_stock": 4,
    }

    agent = PharmacyAgent(router=FakeLLM())
    output = await agent.run(state=state)

    assert output.compliance_hold is False
    assert output.needed is True
    assert output.quantity > 0

    orders = get_in_memory_orders()
    assert len(orders) == 1
    assert orders[0]["status"] == "requested"
    assert orders[0]["product_id"] == PRODUCT_AZI


# -----------------------------------------------------------------------------
# 5. Sellable Return Restores Stock
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_sellable_return_restores_stock():
    """Verify that sellable returns restore inventory and do not create unnecessary replenishment."""
    corr_id = f"corr-sellable-{uuid.uuid4()}"

    set_mock_inventory(
        PHARMACY_ID,
        [
            {
                "node_id": PHARMACY_ID,
                "product_id": PRODUCT_PCM,
                "sku": "MED-PCM-650",
                "quantity": 40,
                "safety_stock": 20,
                "max_capacity": 100,
            }
        ],
    )

    state = {
        "event": {
            "type": "return",
            "event_id": "evt-ret-sellable",
            "payload": {
                "condition": "sellable",
                "quantity": 5,
                "product_id": PRODUCT_PCM,
            },
        },
        "pharmacy_id": PHARMACY_ID,
        "product_id": PRODUCT_PCM,
        "correlation_id": corr_id,
    }

    agent = PharmacyAgent(router=FakeLLM())
    output = await agent.run(state=state)

    assert output.needed is False
    assert output.compliance_hold is False
    assert output.quantity == 0
    assert len(get_in_memory_orders()) == 0


# -----------------------------------------------------------------------------
# 6. Direct Pharmacy Tools Unit Tests
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_pharmacy_tools_direct_execution():
    """Verify direct tool invocations: get_inventory, get_recent_sales, get_batches_near_expiry, check_prescription_link."""
    # 1. get_inventory
    set_mock_inventory(PHARMACY_ID, [{"node_id": PHARMACY_ID, "product_id": PRODUCT_AZI, "quantity": 12, "safety_stock": 10}])
    inv = await get_inventory(node_id=PHARMACY_ID, product_id=PRODUCT_AZI)
    assert len(inv) == 1
    assert inv[0]["quantity"] == 12

    # 2. check_prescription_link
    rx_valid = await check_prescription_link(event_id="e-1", prescription_ref="DOC-IND-002")
    assert rx_valid["valid"] is True
    assert rx_valid["doctor_id"] == "DOC-IND-002"

    rx_invalid = await check_prescription_link(event_id="e-2", prescription_ref="UNKNOWN-DOC-999")
    assert rx_invalid["valid"] is False
    assert rx_invalid["doctor_id"] is None

    # 3. check_prescription_link via event metadata
    set_mock_event("evt-meta-rx", {"id": "evt-meta-rx", "payload": {"prescription_ref": "DOC-IND-003"}})
    rx_meta = await check_prescription_link(event_id="evt-meta-rx", prescription_ref=None)
    assert rx_meta["valid"] is True
    assert rx_meta["doctor_id"] == "DOC-IND-003"

    # 4. get_batches_near_expiry
    set_mock_batches(PHARMACY_ID, [{"batch_id": "b-1", "days_to_expiry": 10, "quantity_affected": 5}])
    batches = await get_batches_near_expiry(node_id=PHARMACY_ID, threshold_days=30)
    assert len(batches) == 1
    assert batches[0]["days_to_expiry"] == 10


# -----------------------------------------------------------------------------
# 7. Mock Supabase Client Order Insertion Call
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_mock_supabase_client_order_insertion():
    """Verify that when a Supabase client is present, client.table('orders').insert().execute() is called."""
    mock_client = MagicMock()
    mock_table = MagicMock()
    mock_insert = MagicMock()
    mock_client.table.return_value = mock_table
    mock_table.insert.return_value = mock_insert
    mock_insert.execute.return_value = MagicMock(data=[{"id": "order-123"}])

    set_mock_inventory(
        PHARMACY_ID,
        [{"node_id": PHARMACY_ID, "product_id": PRODUCT_PCM, "quantity": 3, "safety_stock": 15, "max_capacity": 50}],
    )

    state = {
        "event": {"type": "sale", "payload": {"product_id": PRODUCT_PCM, "schedule_type": "OTC"}},
        "pharmacy_id": PHARMACY_ID,
        "product_id": PRODUCT_PCM,
        "current_stock": 3,
        "correlation_id": "test-supabase-mock-001",
    }

    with patch("app.agents.pharmacy_agent.get_service_db_client", return_value=mock_client):
        agent = PharmacyAgent(router=FakeLLM())
        res = await agent.run(state=state)

        assert res.needed is True
        mock_client.table.assert_called_with("orders")
        mock_table.insert.assert_called_once()
        inserted_order = mock_table.insert.call_args[0][0]
        assert inserted_order["status"] == "requested"
        assert inserted_order["pharmacy_id"] == PHARMACY_ID
        assert inserted_order["product_id"] == PRODUCT_PCM


# -----------------------------------------------------------------------------
# 8. Full Cascade Graph Execution with PharmacyAgent Integration
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_cascade_graph_invokes_pharmacy_agent():
    """Verify that cascade_graph executes pharmacy_node with PharmacyAgent, updating state and trace."""
    corr_id = f"test-cascade-pharm-{uuid.uuid4()}"

    set_mock_inventory(
        PHARMACY_ID,
        [
            {
                "node_id": PHARMACY_ID,
                "product_id": PRODUCT_PCM,
                "sku": "MED-PCM-650",
                "quantity": 5,
                "safety_stock": 20,
                "max_capacity": 100,
            }
        ],
    )

    initial_state: CascadeState = {
        "event": {"type": "sale", "source": "pos", "payload": {"product_id": PRODUCT_PCM, "schedule_type": "OTC"}},
        "correlation_id": corr_id,
        "pharmacy_id": PHARMACY_ID,
        "product_id": PRODUCT_PCM,
        "batch_id": "b-pcm-001",
        "quantity": 1,
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
    assert result["pharmacy_result"]["needed"] is True
    assert result["pharmacy_result"]["compliance_hold"] is False

    # Check trace includes PharmacyAgent
    pharm_trace = next(t for t in result["trace"] if t["tier"] == "pharmacy")
    assert pharm_trace["agent_name"] == "PharmacyAgent"
    assert pharm_trace["status"] == "success"

    # Verify orders table recorded the purchase order
    orders = get_in_memory_orders()
    assert any(o["correlation_id"] == corr_id and o["status"] == "requested" for o in orders)
