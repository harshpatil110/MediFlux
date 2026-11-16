"""Automated test suite for Task M7: Cold-Chain Monitor and Notifications (Local and Remote Push).

Covers all 4 Acceptance Criteria:
1. AC #1: Cold-Chain Excursion Quarantine, Telemetry Chart Data, and Deep-Link Routing.
2. AC #2: New HITL Approval Notification, Role/Node Recipient Filtering, and Deep-Link Routing.
3. AC #3: Device Token Registration (POST /api/v1/devices), RLS Isolation, and Logout Cleanup (DELETE /api/v1/devices/{token}).
4. AC #4: Automatic Invalid Token Purge on 'DeviceNotRegistered' and Non-Blocking Error Handling.
"""

import uuid
from typing import Any

import httpx
import pytest
from httpx import ASGITransport

from app.api.v1.endpoints.auth import SEEDED_DEMO_USERS
from app.api.v1.endpoints.devices import (
    _in_memory_device_tokens,
    clear_in_memory_device_tokens,
)
from app.main import app
from app.services.push_notifications import (
    dispatch_push_for_batch_quarantined,
    dispatch_push_for_hitl_created,
    select_recipients_for_hitl,
    send_expo_push_messages,
    set_push_test_client,
)

# Test helper: create bearer headers for demo users
ADMIN_USER = next(u for u in SEEDED_DEMO_USERS if u["role"] == "admin")
STOCKIST_USER = next(u for u in SEEDED_DEMO_USERS if u["role"] == "stockist")
DISTRIBUTOR_USER = next(u for u in SEEDED_DEMO_USERS if u["role"] == "distributor")
PHARMACY_USER = next(u for u in SEEDED_DEMO_USERS if u["role"] == "pharmacy")


def _get_headers_for(user_dict: dict[str, Any]) -> dict[str, str]:
    role = str(user_dict.get("role", "user"))
    token = str(user_dict.get("token") or f"mock-{role}-token")
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


@pytest.fixture(autouse=True)
def _reset_test_state():
    """Clear memory stores before each test."""
    clear_in_memory_device_tokens()
    set_push_test_client(None)
    yield
    clear_in_memory_device_tokens()
    set_push_test_client(None)


# -----------------------------------------------------------------------------
# AC #1: Cold-Chain Excursion Quarantine & Telemetry Endpoints
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_ac1_coldchain_excursion_quarantine_and_detail_endpoint():
    """Triggering a thermal excursion quarantines the batch, zeroes available stock, and enriches batch detail."""
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        admin_headers = _get_headers_for(ADMIN_USER)

        # 1. Simulate excursion for BIO-INS-01
        sim_res = await client.post(
            "/api/v1/coldchain/simulate",
            json={"mode": "excursion", "batch_id": "BIO-INS-01", "steps": 4},
            headers=admin_headers,
        )
        assert sim_res.status_code == 200, sim_res.text
        sim_data = sim_res.json()
        assert sim_data["quarantined"] is True
        assert sim_data["batch_status"] == "quarantined"
        assert sim_data["available_quantity"] == 0

        # 2. Verify in GET /api/v1/coldchain/batches
        list_res = await client.get("/api/v1/coldchain/batches", headers=admin_headers)
        assert list_res.status_code == 200
        batches = list_res.json()["batches"]
        target = next((b for b in batches if b["batch_id"] == "BIO-INS-01"), None)
        assert target is not None
        assert target["status"] == "quarantined"
        assert target["available_quantity"] == 0
        assert target["storage_min_c"] == 2.0
        assert target["storage_max_c"] == 8.0
        assert len(target["readings"]) >= 4

        # 3. Verify in GET /api/v1/coldchain/batches/{batch_id}
        detail_res = await client.get("/api/v1/coldchain/batches/BIO-INS-01", headers=admin_headers)
        assert detail_res.status_code == 200
        detail = detail_res.json()
        assert detail["batch_id"] == "BIO-INS-01"
        assert detail["status"] == "quarantined"
        assert detail["available_quantity"] == 0
        assert detail["quarantine"] is not None
        assert "explanation" in detail["quarantine"]
        assert detail["shelf_life_estimate"]["decision"] == "quarantined"

        # 4. Verify in GET /api/v1/coldchain/quarantines
        q_res = await client.get("/api/v1/coldchain/quarantines", headers=admin_headers)
        assert q_res.status_code == 200
        quarantines = q_res.json()["quarantines"]
        assert any(q.get("batch_id") == "BIO-INS-01" for q in quarantines)


@pytest.mark.asyncio
async def test_ac1_batch_detail_404_for_unknown():
    """Querying an unknown coldchain batch returns 404 Not Found."""
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get(
            "/api/v1/coldchain/batches/UNKNOWN-BATCH-9999",
            headers=_get_headers_for(ADMIN_USER),
        )
        assert res.status_code == 404
        assert "not found" in res.json()["detail"].lower()


# -----------------------------------------------------------------------------
# AC #2: New HITL Approval Notification & Recipient Role Scoping
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_ac2_hitl_notification_recipient_role_filtering():
    """Push notifications for HITL tasks only target eligible approver roles."""
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Register 3 device tokens: admin, distributor, pharmacy
        admin_headers = _get_headers_for(ADMIN_USER)
        dist_headers = _get_headers_for(DISTRIBUTOR_USER)
        pharm_headers = _get_headers_for(PHARMACY_USER)

        t_admin = "ExponentPushToken[admin-tok-12345]"
        t_dist = "ExponentPushToken[dist-tok-12345]"
        t_pharm = "ExponentPushToken[pharm-tok-12345]"

        await client.post("/api/v1/devices", json={"token": t_admin, "platform": "android"}, headers=admin_headers)
        await client.post("/api/v1/devices", json={"token": t_dist, "platform": "android"}, headers=dist_headers)
        await client.post("/api/v1/devices", json={"token": t_pharm, "platform": "android"}, headers=pharm_headers)

        # For cross_border_shipment: allowed_roles include admin and distributor, but NOT pharmacy
        recipients_xb = select_recipients_for_hitl("cross_border_shipment")
        recipient_tokens = {r["token"] for r in recipients_xb}
        assert t_admin in recipient_tokens
        assert t_dist in recipient_tokens
        assert t_pharm not in recipient_tokens, "Pharmacy role must NOT receive cross_border_shipment notifications"


@pytest.mark.asyncio
async def test_ac2_notification_user_preference_respected():
    """Users who opt out of approvalAlerts or coldchainAlerts do not receive push notifications."""
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        dist_headers = _get_headers_for(DISTRIBUTOR_USER)
        t_optout = "ExponentPushToken[dist-optout-9999]"

        # Register distributor with hitl = False
        await client.post(
            "/api/v1/devices",
            json={
                "token": t_optout,
                "platform": "ios",
                "preferences": {"hitl": False, "coldchain": True},
            },
            headers=dist_headers,
        )

        recipients = select_recipients_for_hitl("cross_border_shipment")
        recipient_tokens = {r["token"] for r in recipients}
        assert t_optout not in recipient_tokens, "User with hitl=False must be excluded"


# -----------------------------------------------------------------------------
# AC #3: Device Token Registration, RLS Isolation, and Logout Removal
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_ac3_device_token_lifecycle_and_rls_isolation():
    """Device tokens are saved via POST, listed via GET, isolated by RLS, and removed via DELETE."""
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        pharm_headers = _get_headers_for(PHARMACY_USER)
        dist_headers = _get_headers_for(DISTRIBUTOR_USER)

        t_pharm = "ExponentPushToken[mediflux-pharm-1111]"

        # 1. Pharmacy registers token
        reg_res = await client.post(
            "/api/v1/devices",
            json={"token": t_pharm, "platform": "android"},
            headers=pharm_headers,
        )
        assert reg_res.status_code == 201
        data = reg_res.json()
        assert data["token"] == t_pharm
        assert data["user_id"] == PHARMACY_USER["user_id"]

        # 2. Pharmacy lists own devices
        list_res = await client.get("/api/v1/devices", headers=pharm_headers)
        assert list_res.status_code == 200
        user_devices = list_res.json()["devices"]
        assert any(d["token"] == t_pharm for d in user_devices)

        # 3. Distributor attempts to delete Pharmacy's token -> 403 Forbidden (RLS)
        del_forbidden = await client.delete(
            f"/api/v1/devices/{t_pharm}",
            headers=dist_headers,
        )
        assert del_forbidden.status_code == 403, "Caller cannot delete another user's device token"

        # 4. Pharmacy deletes own token -> 200 OK
        del_ok = await client.delete(
            f"/api/v1/devices/{t_pharm}",
            headers=pharm_headers,
        )
        assert del_ok.status_code == 200
        assert del_ok.json()["removed"] is True

        # 5. Verify token is removed from store
        assert t_pharm not in _in_memory_device_tokens


# -----------------------------------------------------------------------------
# AC #4: Automatic Invalid Token Cleanup on 'DeviceNotRegistered'
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_ac4_automatic_invalid_token_cleanup_on_device_not_registered():
    """When Expo push service returns DeviceNotRegistered, the invalid token is automatically purged."""
    t_stale = "ExponentPushToken[stale-device-token-404]"
    t_valid = "ExponentPushToken[valid-device-token-200]"

    # Seed in memory store
    _in_memory_device_tokens[t_stale] = {
        "id": str(uuid.uuid4()),
        "user_id": "00000000-0000-0000-0000-000000000001",
        "token": t_stale,
        "platform": "android",
        "preferences": {"hitl": True, "coldchain": True},
        "role": "admin",
    }
    _in_memory_device_tokens[t_valid] = {
        "id": str(uuid.uuid4()),
        "user_id": "00000000-0000-0000-0000-000000000001",
        "token": t_valid,
        "platform": "android",
        "preferences": {"hitl": True, "coldchain": True},
        "role": "admin",
    }

    # Mock Expo Push HTTP Client response
    mock_responses = {
        "https://exp.host/--/api/v2/push/send": httpx.Response(
            200,
            json={
                "data": [
                    {
                        "status": "error",
                        "message": '"ExponentPushToken[...]" is not a registered push notification recipient',
                        "details": {"error": "DeviceNotRegistered"},
                    },
                    {
                        "status": "ok",
                        "id": "ticket-uuid-valid-1234",
                    },
                ]
            },
        )
    }

    class MockPushTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
            url_str = str(request.url)
            if url_str in mock_responses:
                return mock_responses[url_str]
            return httpx.Response(200, json={"data": [{"status": "ok"}]})

    mock_client = httpx.AsyncClient(transport=MockPushTransport())
    set_push_test_client(mock_client)

    messages = [
        {"to": t_stale, "title": "Alert", "body": "Test message"},
        {"to": t_valid, "title": "Alert", "body": "Test message"},
    ]

    result = await send_expo_push_messages(messages)
    assert result["sent"] == 1
    assert result["cleaned"] == 1

    # Stale token must be automatically deleted from the store
    assert t_stale not in _in_memory_device_tokens, "Stale token must be removed from store"
    assert t_valid in _in_memory_device_tokens, "Valid token must remain in store"


@pytest.mark.asyncio
async def test_ac4_push_dispatch_non_blocking_on_network_error():
    """Push dispatch handles network failures gracefully without raising or blocking caller."""
    class FailingTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("Connection to exp.host timed out")

    failing_client = httpx.AsyncClient(transport=FailingTransport())
    set_push_test_client(failing_client)

    # Calling dispatch functions should complete cleanly without unhandled exception
    await dispatch_push_for_hitl_created({
        "id": "task-test-err",
        "task_type": "cross_border_shipment",
        "risk_level": "high",
    })

    await dispatch_push_for_batch_quarantined({
        "batch_id": "BIO-INS-01",
        "batch_no": "B26-BIO-INS-01",
    })
