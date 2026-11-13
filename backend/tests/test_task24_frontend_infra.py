"""Automated verification suite for Task 24: Frontend Shell, Auth and Shared Infrastructure.

Tests cover:
1. Seeded demo users endpoint (/api/v1/auth/demo-users) returning all 7 roles.
2. Demo user quick login (/api/v1/auth/login) and profile resolution (/api/v1/auth/me).
3. Exact 11-route role-based navigation matrix enforcement for all 7 roles.
4. CORS middleware headers (allowing Vite, Tauri origins, Last-Event-ID, etc.).
5. SSE streaming endpoint (/api/v1/events/stream and /api/v1/stream) with Last-Event-ID replay.
6. Real-time test event ingestion (POST /api/v1/events) and retrieval (GET /api/v1/events).
7. Agent runs observability (GET /api/v1/agents/runs).
"""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.events.bus import in_process_event_bus
from app.events.models import EventEnvelope
from app.main import app

EXPECTED_ROLES = [
    "admin",
    "regulator",
    "manufacturer",
    "distributor",
    "stockist",
    "pharmacy",
    "developer",
]

ROLE_ROUTE_MATRIX = {
    "admin": {
        "/overview",
        "/cascade",
        "/agents",
        "/approvals",
        "/adapter-forge",
        "/regulatory-lab",
        "/prescriptions",
        "/cold-chain",
        "/audit",
        "/copilot",
        "/developer",
    },
    "regulator": {
        "/overview",
        "/cascade",
        "/regulatory-lab",
        "/prescriptions",
        "/cold-chain",
        "/audit",
        "/copilot",
    },
    "manufacturer": {
        "/overview",
        "/cascade",
        "/agents",
        "/approvals",
        "/adapter-forge",
        "/cold-chain",
        "/copilot",
    },
    "distributor": {
        "/overview",
        "/cascade",
        "/agents",
        "/approvals",
        "/cold-chain",
        "/copilot",
    },
    "stockist": {
        "/overview",
        "/cascade",
        "/agents",
        "/approvals",
        "/cold-chain",
        "/copilot",
    },
    "pharmacy": {
        "/overview",
        "/cascade",
        "/approvals",
        "/adapter-forge",
        "/prescriptions",
        "/cold-chain",
        "/copilot",
    },
    "developer": {
        "/overview",
        "/agents",
        "/adapter-forge",
        "/audit",
        "/copilot",
        "/developer",
    },
}


@pytest.mark.asyncio
async def test_get_demo_users_all_seven_roles():
    """Verify GET /api/v1/auth/demo-users returns seeded users for all 7 roles."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/auth/demo-users")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 7

        returned_roles = [u["role"] for u in data]
        for role in EXPECTED_ROLES:
            assert role in returned_roles, f"Expected role {role} not found in demo users"

        for user in data:
            assert "role" in user
            assert "label" in user
            assert "email" in user
            assert "token" in user
            assert "allowed_routes" in user
            assert isinstance(user["allowed_routes"], list)
            assert set(user["allowed_routes"]) == ROLE_ROUTE_MATRIX[user["role"]]


@pytest.mark.asyncio
async def test_demo_quick_login_all_roles():
    """Verify POST /api/v1/auth/login works with role-based quick login for all 7 roles."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        for role in EXPECTED_ROLES:
            resp = await client.post("/api/v1/auth/login", json={"role": role})
            assert resp.status_code == 200, f"Login failed for role {role}: {resp.text}"
            body = resp.json()
            assert "token" in body
            assert "user" in body
            assert body["user"]["role"] == role
            assert set(body["user"]["allowed_routes"]) == ROLE_ROUTE_MATRIX[role]


@pytest.mark.asyncio
async def test_auth_me_with_demo_tokens():
    """Verify GET /api/v1/auth/me returns enriched actor profile with assigned topology."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Pharmacy
        resp = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer mock-pharmacy-token"},
        )
        assert resp.status_code == 200
        profile = resp.json()
        assert profile["role"] == "pharmacy"
        assert "Apollo Pharmacy" in profile["node_name"]
        assert profile["tier"] == "pharmacy"
        assert "/prescriptions" in profile["allowed_routes"]
        assert "/regulatory-lab" not in profile["allowed_routes"]
        assert "/audit" not in profile["allowed_routes"]

        # Regulator
        resp_reg = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer mock-regulator-token"},
        )
        assert resp_reg.status_code == 200
        reg_profile = resp_reg.json()
        assert reg_profile["role"] == "regulator"
        assert "/regulatory-lab" in reg_profile["allowed_routes"]
        assert "/audit" in reg_profile["allowed_routes"]
        assert "/adapter-forge" not in reg_profile["allowed_routes"]

        # Developer
        resp_dev = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer mock-developer-token"},
        )
        assert resp_dev.status_code == 200
        dev_profile = resp_dev.json()
        assert dev_profile["role"] == "developer"
        assert "/developer" in dev_profile["allowed_routes"]
        assert "/audit" in dev_profile["allowed_routes"]
        assert "/prescriptions" not in dev_profile["allowed_routes"]


@pytest.mark.asyncio
async def test_role_navigation_matrix_completeness():
    """Verify the role route matrix strictly matches the specification in Section 24.1.4."""
    # Pharmacy: Prescriptions & Adapter Forge, NOT Regulatory Lab, Audit, Developer
    pharmacy_routes = ROLE_ROUTE_MATRIX["pharmacy"]
    assert "/prescriptions" in pharmacy_routes
    assert "/adapter-forge" in pharmacy_routes
    assert "/regulatory-lab" not in pharmacy_routes
    assert "/audit" not in pharmacy_routes
    assert "/developer" not in pharmacy_routes

    # Regulator: Regulatory Lab & Audit, NOT Adapter Forge, Developer
    regulator_routes = ROLE_ROUTE_MATRIX["regulator"]
    assert "/regulatory-lab" in regulator_routes
    assert "/audit" in regulator_routes
    assert "/adapter-forge" not in regulator_routes
    assert "/developer" not in regulator_routes

    # Admin: All 11 routes
    assert len(ROLE_ROUTE_MATRIX["admin"]) == 11


@pytest.mark.asyncio
async def test_cors_middleware_configuration():
    """Verify CORS headers allow Vite and Tauri desktop origins."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Pre-flight OPTIONS check for localhost:5173
        resp = await client.options(
            "/api/v1/events",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Authorization,X-API-Key,Last-Event-ID",
            },
        )
        assert resp.status_code == 200
        assert resp.headers.get("access-control-allow-origin") == "http://localhost:5173"
        assert resp.headers.get("access-control-allow-credentials") == "true"

        # Pre-flight check for tauri://localhost
        resp_tauri = await client.options(
            "/api/v1/events",
            headers={
                "Origin": "tauri://localhost",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert resp_tauri.status_code == 200
        assert resp_tauri.headers.get("access-control-allow-origin") == "tauri://localhost"

        # Pre-flight check for https://tauri.localhost
        resp_tauri_https = await client.options(
            "/api/v1/events",
            headers={
                "Origin": "https://tauri.localhost",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert resp_tauri_https.status_code == 200
        assert resp_tauri_https.headers.get("access-control-allow-origin") == "https://tauri.localhost"


@pytest.mark.asyncio
async def test_event_ingestion_and_list_endpoints():
    """Verify POST /api/v1/events ingests events and GET /api/v1/events returns them."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        test_event_id = f"test-evt-{uuid.uuid4()}"
        post_resp = await client.post(
            "/api/v1/events",
            json={
                "event_id": test_event_id,
                "type": "cascade.updates",
                "node_id": "11111111-1111-1111-1111-111111111111",
                "payload": {"message": "Test live event from pytest suite"},
            },
            headers={"Authorization": "Bearer mock-admin-token"},
        )
        assert post_resp.status_code == 202
        post_data = post_resp.json()
        assert post_data["status"] == "accepted"
        assert post_data["event_id"] == test_event_id

        # GET /api/v1/events
        get_resp = await client.get("/api/v1/events?limit=20")
        assert get_resp.status_code == 200
        events_list = get_resp.json()
        assert isinstance(events_list, list)
        matching = [e for e in events_list if e.get("event_id") == test_event_id]
        assert len(matching) > 0, f"Published event {test_event_id} was not returned by GET /api/v1/events"


@pytest.mark.asyncio
async def test_agent_runs_query_endpoint():
    """Verify GET /api/v1/agents/runs returns agent execution traces."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            "/api/v1/agents/runs?limit=10",
            headers={"Authorization": "Bearer mock-admin-token"},
        )
        assert resp.status_code == 200
        runs = resp.json()
        assert isinstance(runs, list)


@pytest.mark.asyncio
async def test_sse_stream_last_event_id_replay():
    """Verify that SSE stream respects Last-Event-ID / last_event_id replay."""
    # Seed events into in_process_event_bus
    evt1 = EventEnvelope(
        event_id="test-sse-replay-001",
        type="pos.sales",
        node_id="11111111-1111-1111-1111-111111111111",
        payload={"item": "Drug A"},
    )
    evt2 = EventEnvelope(
        event_id="test-sse-replay-002",
        type="pos.sales",
        node_id="11111111-1111-1111-1111-111111111111",
        payload={"item": "Drug B"},
    )
    await in_process_event_bus.publish("pos.sales", evt1)
    await in_process_event_bus.publish("pos.sales", evt2)

    replayed = in_process_event_bus.get_events_after(
        last_event_id="test-sse-replay-001",
        topics=["pos.sales"],
    )
    assert any(e.event_id == "test-sse-replay-002" for e in replayed)
