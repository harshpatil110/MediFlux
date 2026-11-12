"""Integration and unit test suite for Task 6: Event Bus, Persistence, and SSE Streaming."""

import asyncio
import time
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.events.bus import in_process_event_bus
from app.events.models import EventEnvelope, SaleEvent
from app.events.service import (
    clear_service_state,
    get_in_memory_audit,
    get_in_memory_stock,
    set_in_memory_stock,
)
from app.events.sse import sse_event_stream
from app.main import app


@pytest.fixture(autouse=True)
def clean_event_environment() -> None:
    """Ensure in-process bus and service state are completely clean for each test."""
    from unittest.mock import patch

    from app.core.config import settings

    in_process_event_bus.clear()
    clear_service_state()
    # Mock SUPABASE_URL to empty to avoid slow remote HTTP network roundtrips in local unit tests
    with patch.object(settings, "SUPABASE_URL", ""):
        yield
    in_process_event_bus.clear()
    clear_service_state()


# -----------------------------------------------------------------------------
# 1. Inventory Decrement & Speed Test (< 1 second)
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_sale_event_ingestion_and_latency() -> None:
    """Verify posting a SaleEvent immediately decrements stock and broadcasts to pos.sales within < 1 second."""
    pharmacy_id = "11111111-1111-1111-1111-111111111111"
    product_id = "a0000000-0000-0000-0000-000000000001"
    batch_id = "b0000000-0000-0000-0000-000000000001"
    initial_stock = 100

    set_in_memory_stock(pharmacy_id, product_id, batch_id, initial_stock)

    # Set up async subscriber to verify broadcast
    received_events: list[EventEnvelope] = []

    async def listener() -> None:
        async for evt in in_process_event_bus.subscribe("pos.sales"):
            received_events.append(evt)
            break

    listener_task = asyncio.create_task(listener())
    # Give listener a brief tick to register queue
    await asyncio.sleep(0.01)

    event_id = str(uuid.uuid4())
    payload = {
        "event_id": event_id,
        "pharmacy_id": pharmacy_id,
        "product_id": product_id,
        "batch_id": batch_id,
        "quantity": 2,
        "source": "pos",
    }

    start_time = time.perf_counter()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.post("/api/v1/events/sale", json=payload)
        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "accepted"
        assert data["event_id"] == event_id

    # Wait for subscriber with timeout < 1.0 second
    await asyncio.wait_for(listener_task, timeout=1.0)
    elapsed_time = time.perf_counter() - start_time

    # Acceptance Criteria 1: Execution and broadcast completed in < 1 second
    assert elapsed_time < 1.0
    assert len(received_events) == 1
    assert received_events[0].event_id == event_id
    assert received_events[0].type == "pos.sales"

    # Verify inventory was decremented by 2
    remaining_stock = get_in_memory_stock(pharmacy_id, product_id, batch_id)
    assert remaining_stock == initial_stock - 2


# -----------------------------------------------------------------------------
# 2. Idempotency Test
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_duplicate_sale_event_idempotency() -> None:
    """Verify posting the exact same event_id twice results in exactly one decrement and one audit entry."""
    pharmacy_id = "11111111-1111-1111-1111-111111111111"
    product_id = "a0000000-0000-0000-0000-000000000002"
    batch_id = "b0000000-0000-0000-0000-000000000002"
    initial_stock = 50

    set_in_memory_stock(pharmacy_id, product_id, batch_id, initial_stock)

    event_id = "evt-idempotent-test-001"
    payload = {
        "event_id": event_id,
        "pharmacy_id": pharmacy_id,
        "product_id": product_id,
        "batch_id": batch_id,
        "quantity": 5,
        "source": "pos",
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        # 1st Ingestion: Should succeed and decrement
        res1 = await client.post("/api/v1/events/sale", json=payload)
        assert res1.status_code == 202
        assert res1.json()["status"] == "accepted"

        # 2nd Ingestion with duplicate event_id: Should detect duplicate and NOT decrement again
        res2 = await client.post("/api/v1/events/sale", json=payload)
        assert res2.status_code == 200
        assert res2.json()["status"] == "duplicate"
        assert res2.json()["applied"] is False

    # Stock must have decremented only ONCE (50 - 5 = 45)
    assert get_in_memory_stock(pharmacy_id, product_id, batch_id) == 45

    # Audit ledger must have only 1 entry for this event
    audit_records = [r for r in get_in_memory_audit() if r.get("event_id") == event_id]
    assert len(audit_records) == 1


# -----------------------------------------------------------------------------
# 3. Batch Sale Ingestion Test
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_batch_sale_ingestion() -> None:
    """Verify POST /api/v1/events/sale/batch processes multiple sales atomically."""
    pharmacy_id = "11111111-1111-1111-1111-111111111111"
    product_id = "a0000000-0000-0000-0000-000000000003"
    batch_id = "b0000000-0000-0000-0000-000000000003"

    set_in_memory_stock(pharmacy_id, product_id, batch_id, 30)

    events_payload = [
        {
            "event_id": f"evt-batch-{i}",
            "pharmacy_id": pharmacy_id,
            "product_id": product_id,
            "batch_id": batch_id,
            "quantity": 1,
            "source": "pos",
        }
        for i in range(5)
    ]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.post("/api/v1/events/sale/batch", json=events_payload)
        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "accepted"
        assert data["processed"] == 5

    assert get_in_memory_stock(pharmacy_id, product_id, batch_id) == 25


# -----------------------------------------------------------------------------
# 4. SSE Stream Last-Event-ID Replay Test
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_sse_replay_mechanism_with_last_event_id() -> None:
    """Verify that a client supplying Last-Event-ID receives all missed events created after that ID."""
    node_id = "11111111-1111-1111-1111-111111111111"

    # Pre-publish 3 events to the event bus
    for i in range(1, 4):
        envelope = EventEnvelope(
            event_id=f"evt-replay-{i}",
            type="pos.sales",
            node_id=node_id,
            payload={"item": i},
        )
        await in_process_event_bus.publish("pos.sales", envelope)

    # Replay stream starting after evt-replay-1
    stream_gen = sse_event_stream(
        topics=["pos.sales"],
        last_event_id="evt-replay-1",
        visible_nodes={node_id},
    )

    # First event should be evt-replay-2
    first_replayed = await anext(stream_gen)
    assert first_replayed.id == "evt-replay-2"
    assert first_replayed.event == "pos.sales"

    # Second event should be evt-replay-3
    second_replayed = await anext(stream_gen)
    assert second_replayed.id == "evt-replay-3"
    assert second_replayed.event == "pos.sales"

    # Clean up generator
    await stream_gen.aclose()


# -----------------------------------------------------------------------------
# 5. Node Isolation Security Test
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_node_isolation_filtering() -> None:
    """Verify that a pharmacy user only receives events for their visible node and NOT unrelated nodes."""
    pharmacy_a = "11111111-1111-1111-1111-111111111111"
    pharmacy_b = "55555555-5555-5555-5555-555555555555"

    # Stream consumer scoped ONLY to pharmacy_a
    stream_gen = sse_event_stream(
        topics=["pos.sales"],
        visible_nodes={pharmacy_a},
    )

    # Initial connection event
    init_msg = await anext(stream_gen)
    assert init_msg.event == "connected"

    # Emit event for pharmacy_b (unrelated node)
    unrelated_event = EventEnvelope(
        event_id="evt-pharm-b",
        type="pos.sales",
        node_id=pharmacy_b,
        payload={"pharmacy": "b"},
    )
    await in_process_event_bus.publish("pos.sales", unrelated_event)

    # Emit event for pharmacy_a (authorized node)
    authorized_event = EventEnvelope(
        event_id="evt-pharm-a",
        type="pos.sales",
        node_id=pharmacy_a,
        payload={"pharmacy": "a"},
    )
    await in_process_event_bus.publish("pos.sales", authorized_event)

    # Next received event on Pharmacy A stream MUST be evt-pharm-a, never evt-pharm-b
    received = await asyncio.wait_for(anext(stream_gen), timeout=1.0)
    assert received.id == "evt-pharm-a"
    assert received.id != "evt-pharm-b"

    await stream_gen.aclose()


# -----------------------------------------------------------------------------
# 6. Stream Endpoint HTTP Authentication Test
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_stream_endpoint_requires_auth() -> None:
    """Verify accessing /api/v1/stream without valid authentication returns HTTP 401."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.get("/api/v1/stream")
        assert response.status_code == 401
        data = response.json()
        assert data["error"]["code"] == "UNAUTHORIZED"


# -----------------------------------------------------------------------------
# 7. Supabase RPC Execution Path Test
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_apply_sale_rpc_invocation_path() -> None:
    """Verify apply_sale properly calls client.rpc when Supabase client is configured."""
    from unittest.mock import MagicMock, patch

    from app.core.config import settings
    from app.events.service import apply_sale

    mock_client = MagicMock()
    mock_rpc = MagicMock()
    mock_rpc.execute.return_value = MagicMock(
        data={"status": "success", "applied": True, "event_id": "rpc-test-01", "remaining_quantity": 42}
    )
    mock_client.rpc.return_value = mock_rpc

    event = SaleEvent(
        event_id="rpc-test-01",
        pharmacy_id="11111111-1111-1111-1111-111111111111",
        product_id="a0000000-0000-0000-0000-000000000001",
        batch_id="b0000000-0000-0000-0000-000000000001",
        quantity=1,
    )

    with patch.object(settings, "SUPABASE_URL", "https://mock.supabase.co"), patch.object(
        settings, "SUPABASE_SERVICE_ROLE_KEY", "mock-service-key"
    ), patch("app.events.service.get_service_db_client", return_value=mock_client):
        res = await apply_sale(event, correlation_id="rpc-corr-123")
        assert res["status"] == "success"
        assert res["applied"] is True
        assert res["remaining_quantity"] == 42
        mock_client.rpc.assert_called_once_with(
            "apply_sale",
            {
                "p_event_id": "rpc-test-01",
                "p_pharmacy_id": "11111111-1111-1111-1111-111111111111",
                "p_product_id": "a0000000-0000-0000-0000-000000000001",
                "p_batch_id": "b0000000-0000-0000-0000-000000000001",
                "p_quantity": 1,
                "p_correlation_id": "rpc-corr-123",
            },
        )

