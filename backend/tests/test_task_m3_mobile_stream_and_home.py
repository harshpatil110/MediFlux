"""Task M3: Live Event Stream, Home Dashboard and Mobile Summary Endpoint Verification Tests.

Validates:
1. GET /api/v1/mobile/summary returns valid KPI metrics and RLS-scoped user/node context.
2. GET /api/v1/events/recent returns chronologically ordered normalized events with cursor support.
3. GET /api/v1/stream supports Last-Event-ID replay and topics filtering.
4. Acceptance Criterion #1: Real-time event publication arrives and appears in recent feed.
5. Acceptance Criterion #2: Last-Event-ID replay yields missed events.
6. Acceptance Criterion #3 & #4: Polling fallback and AppState mobile hook file structures.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.events.bus import in_process_event_bus
from app.events.models import EventEnvelope
from app.main import app

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
MOBILE_DIR = ROOT_DIR / "mobile"


class TestMobileStreamAndHomeTaskM3:
    """Automated test suite verifying full compliance of Task M3."""

    def test_mobile_m3_file_structure(self) -> None:
        """Verify presence of all Task M3 required files and hooks."""
        required_paths = [
            MOBILE_DIR / "src" / "hooks" / "useEventStream.ts",
            MOBILE_DIR / "src" / "hooks" / "useNetworkStatus.ts",
            MOBILE_DIR / "src" / "features" / "cascade" / "CascadeTimeline.tsx",
            MOBILE_DIR / "app" / "(tabs)" / "index.tsx",
            MOBILE_DIR / "app" / "cascade" / "[id].tsx",
        ]
        for path in required_paths:
            assert path.exists(), f"Required Task M3 file missing: {path}"

    @pytest.mark.asyncio
    async def test_get_mobile_summary_pharmacy(self) -> None:
        """Verify GET /api/v1/mobile/summary returns 200 with pharmacy RLS scope."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            headers = {"Authorization": "Bearer mock-pharmacist-token"}
            res = await client.get("/api/v1/mobile/summary", headers=headers)
            assert res.status_code == 200
            data = res.json()

            assert "events_today" in data
            assert data["events_today"] >= 1
            assert "low_stock_count" in data
            assert "open_approvals" in data
            assert "quarantined_batches" in data
            assert "last_cascade_correlation_id" in data
            assert data["scope"]["role"] == "pharmacy"
            assert "Apollo Pharmacy" in data["scope"]["node_name"]
            assert data["generated_at"] is not None

    @pytest.mark.asyncio
    async def test_get_mobile_summary_stockist(self) -> None:
        """Verify GET /api/v1/mobile/summary returns 200 with stockist RLS scope."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            headers = {"Authorization": "Bearer mock-stockist-token"}
            res = await client.get("/api/v1/mobile/summary", headers=headers)
            assert res.status_code == 200
            data = res.json()

            assert data["scope"]["role"] == "stockist"
            assert "Stockist Hub" in data["scope"]["node_name"]

    @pytest.mark.asyncio
    async def test_get_recent_events_format_and_cursor(self) -> None:
        """Verify GET /api/v1/events/recent returns rich normalized events with cursor."""
        # Publish a test event to in-process event bus
        test_event = EventEnvelope(
            event_id="test-m3-evt-001",
            type="pos.sales",
            node_id="11111111-1111-1111-1111-111111111111",
            correlation_id="test-casc-m3-001",
            payload={"product_name": "Azithromycin 500mg", "quantity": 1},
        )
        await in_process_event_bus.publish("pos.sales", test_event)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            headers = {"Authorization": "Bearer mock-pharmacist-token"}
            res = await client.get("/api/v1/events/recent?limit=20", headers=headers)
            assert res.status_code == 200
            data = res.json()

            assert "events" in data
            assert data["count"] > 0
            assert "latest_event_id" in data
            assert "server_ts" in data

            # Verify normalized structure
            first = data["events"][0]
            assert "id" in first
            assert "event_id" in first
            assert "event_type" in first
            assert "agent_name" in first
            assert "tier" in first
            assert "summary" in first
            assert "correlation_id" in first
            assert "created_at" in first

    @pytest.mark.asyncio
    async def test_get_recent_events_since_filter(self) -> None:
        """Verify GET /api/v1/events/recent with since filters out older events."""
        # Publish two sequential events
        evt_a = EventEnvelope(
            event_id="test-since-a",
            type="pos.sales",
            node_id="11111111-1111-1111-1111-111111111111",
            correlation_id="test-casc-since",
            payload={"summary": "Event A"},
        )
        evt_b = EventEnvelope(
            event_id="test-since-b",
            type="pos.sales",
            node_id="11111111-1111-1111-1111-111111111111",
            correlation_id="test-casc-since",
            payload={"summary": "Event B"},
        )
        await in_process_event_bus.publish("pos.sales", evt_a)
        await in_process_event_bus.publish("pos.sales", evt_b)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            headers = {"Authorization": "Bearer mock-pharmacist-token"}
            res = await client.get("/api/v1/events/recent?since=test-since-a", headers=headers)
            assert res.status_code == 200
            data = res.json()
            event_ids = [e["event_id"] for e in data["events"]]

            assert "test-since-a" not in event_ids
            assert "test-since-b" in event_ids

    @pytest.mark.asyncio
    async def test_get_recent_events_topic_filter(self) -> None:
        """Verify GET /api/v1/events/recent filters by requested topic."""
        cold_evt = EventEnvelope(
            event_id="test-cold-m3-01",
            type="coldchain",
            node_id="11111111-1111-1111-1111-111111111111",
            correlation_id="test-casc-cold",
            payload={"current_temp": 4.5},
        )
        await in_process_event_bus.publish("coldchain", cold_evt)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            headers = {"Authorization": "Bearer mock-admin-token"}
            res = await client.get("/api/v1/events/recent?topics=coldchain", headers=headers)
            assert res.status_code == 200
            data = res.json()
            for ev in data["events"]:
                assert ev["event_type"] == "coldchain"

    @pytest.mark.asyncio
    async def test_stream_endpoint_replay_with_last_event_id(self) -> None:
        """Verify sse_event_stream generator replays missed events with Last-Event-ID."""
        from app.events.sse import sse_event_stream

        # Publish prior and subsequent events
        evt_prior = EventEnvelope(
            event_id="replay-test-m3-prior",
            type="pos.sales",
            node_id="11111111-1111-1111-1111-111111111111",
            correlation_id="replay-casc-1",
            payload={"summary": "Prior event"},
        )
        evt_after = EventEnvelope(
            event_id="replay-test-m3-after",
            type="pos.sales",
            node_id="11111111-1111-1111-1111-111111111111",
            correlation_id="replay-casc-1",
            payload={"summary": "Missed event that must be replayed"},
        )
        await in_process_event_bus.publish("pos.sales", evt_prior)
        await in_process_event_bus.publish("pos.sales", evt_after)

        # Replay via generator
        gen = sse_event_stream(
            topics=["pos.sales"],
            last_event_id="replay-test-m3-prior",
        )
        first_event = await anext(gen)
        assert first_event.id == "replay-test-m3-after"
        data = json.loads(first_event.data)
        assert data["event_id"] == "replay-test-m3-after"
        assert "summary" in data

    @pytest.mark.asyncio
    async def test_stream_endpoint_requires_auth(self) -> None:
        """Verify accessing /api/v1/stream without valid authentication returns HTTP 401."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.get("/api/v1/stream")
            assert res.status_code == 401

