"""Comprehensive automated test suite for Task 29: API Security, RBAC, RLS, and Webhooks.

Validates:
1. Authentication & RBAC (Role-based access control, 401 unauthorized, token validation).
2. RLS Node Isolation (Node boundary filtering and hierarchical visibility).
3. Developer Platform Scoped API Keys (SHA-256 hashing, scope enforcement).
4. In-Memory Token Bucket Rate Limiting (HTTP 429 upon exhaustion).
5. Outbound Webhooks Engine (HMAC-SHA256 signature verification, retry backoff, auto-disable).
"""

from __future__ import annotations

import hashlib

import httpx
from httpx import ASGITransport, AsyncClient
import pytest

from app.core.security import CurrentUser, get_actor, visible_node_ids
from app.main import app
from app.services.api_keys import (
    clear_in_memory_api_keys,
    get_api_key_by_hash,
    rate_limiter,
)
from app.services.webhooks import (
    clear_in_memory_webhooks,
    create_webhook_subscription,
    deliver_webhook,
    verify_webhook_signature,
)


@pytest.fixture(autouse=True)
def clean_security_state():
    """Reset API keys, rate limiter, and webhooks in-memory state before and after each test."""
    clear_in_memory_api_keys()
    clear_in_memory_webhooks()
    rate_limiter.reset()
    yield
    clear_in_memory_api_keys()
    clear_in_memory_webhooks()
    rate_limiter.reset()


# =============================================================================
# 1. Authentication & RBAC Tests
# =============================================================================
@pytest.mark.asyncio
async def test_authentication_missing_and_invalid_tokens() -> None:
    """Unauthenticated requests or invalid tokens receive HTTP 401 Unauthorized."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Missing auth header
        res_no_auth = await client.get("/api/v1/me")
        assert res_no_auth.status_code == 401
        assert res_no_auth.json()["error"]["code"] == "UNAUTHORIZED"

        # Invalid token
        res_bad_token = await client.get(
            "/api/v1/me",
            headers={"Authorization": "Bearer completely-invalid-jwt-token"},
        )
        assert res_bad_token.status_code == 401
        assert res_bad_token.json()["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_rbac_actor_resolution_and_roles() -> None:
    """Actor dependency resolves human users across all 7 platform roles."""
    # 1. Pharmacist role
    actor_pharm = await get_actor(authorization="Bearer mock-pharmacist-token")
    assert actor_pharm.is_agent is False
    assert actor_pharm.role == "pharmacy"
    assert actor_pharm.node_id == "11111111-1111-1111-1111-111111111111"

    # 2. Stockist role
    actor_stock = await get_actor(authorization="Bearer mock-stockist-token")
    assert actor_stock.is_agent is False
    assert actor_stock.role == "stockist"
    assert actor_stock.node_id == "22222222-2222-2222-2222-222222222222"

    # 3. Distributor role
    actor_dist = await get_actor(authorization="Bearer mock-distributor-token")
    assert actor_dist.is_agent is False
    assert actor_dist.role == "distributor"
    assert actor_dist.node_id == "33333333-3333-3333-3333-333333333333"

    # 4. Manufacturer role
    actor_mfg = await get_actor(authorization="Bearer mock-manufacturer-token")
    assert actor_mfg.is_agent is False
    assert actor_mfg.role == "manufacturer"
    assert actor_mfg.node_id == "44444444-4444-4444-4444-444444444444"

    # 5. Admin role
    actor_admin = await get_actor(authorization="Bearer mock-admin-token")
    assert actor_admin.is_agent is False
    assert actor_admin.role == "admin"

    # 6. Regulator role
    actor_reg = await get_actor(authorization="Bearer mock-regulator-token")
    assert actor_reg.is_agent is False
    assert actor_reg.role == "regulator"

    # 7. Developer role
    actor_dev = await get_actor(authorization="Bearer mock-developer-token")
    assert actor_dev.is_agent is False
    assert actor_dev.role == "developer"


# =============================================================================
# 2. RLS Node Isolation & Hierarchical Visibility Tests
# =============================================================================
def test_rls_visible_node_ids_hierarchy() -> None:
    """RLS visible_node_ids enforces strict tree boundaries across supply chain tiers."""
    pharmacy_id = "11111111-1111-1111-1111-111111111111"
    stockist_id = "22222222-2222-2222-2222-222222222222"
    distributor_id = "33333333-3333-3333-3333-333333333333"
    manufacturer_id = "44444444-4444-4444-4444-444444444444"

    # 1. Pharmacy user only sees own node
    user_pharm = CurrentUser(user_id="u-pharm", role="pharmacy", node_id=pharmacy_id)
    pharm_visible = visible_node_ids(user_pharm)
    assert pharm_visible == [pharmacy_id]

    # 2. Stockist sees own node and downstream child pharmacy
    user_stock = CurrentUser(user_id="u-stock", role="stockist", node_id=stockist_id)
    stock_visible = visible_node_ids(user_stock)
    assert stockist_id in stock_visible
    assert pharmacy_id in stock_visible
    assert distributor_id not in stock_visible
    assert manufacturer_id not in stock_visible

    # 3. Distributor sees own node and downstream stockist & pharmacy
    user_dist = CurrentUser(user_id="u-dist", role="distributor", node_id=distributor_id)
    dist_visible = visible_node_ids(user_dist)
    assert distributor_id in dist_visible
    assert stockist_id in dist_visible
    assert pharmacy_id in dist_visible
    assert manufacturer_id not in dist_visible

    # 4. Manufacturer sees entire supply chain tree
    user_mfg = CurrentUser(user_id="u-mfg", role="manufacturer", node_id=manufacturer_id)
    mfg_visible = visible_node_ids(user_mfg)
    assert manufacturer_id in mfg_visible
    assert distributor_id in mfg_visible
    assert stockist_id in mfg_visible
    assert pharmacy_id in mfg_visible

    # 5. Admin has global visibility across all nodes
    user_admin = CurrentUser(user_id="u-admin", role="admin", node_id=None)
    admin_visible = visible_node_ids(user_admin)
    assert pharmacy_id in admin_visible
    assert stockist_id in admin_visible
    assert distributor_id in admin_visible
    assert manufacturer_id in admin_visible


@pytest.mark.asyncio
async def test_inventory_endpoint_node_isolation() -> None:
    """Pharmacy user accessing /api/v1/inventory only receives items belonging to their node."""
    headers = {"Authorization": "Bearer mock-pharmacist-token"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/api/v1/inventory", headers=headers)
        assert res.status_code == 200
        items = res.json()["items"]
        assert len(items) > 0

        pharmacy_node = "11111111-1111-1111-1111-111111111111"
        for item in items:
            assert item["node_id"] == pharmacy_node


# =============================================================================
# 3. Developer Platform Scoped API Keys Tests
# =============================================================================
@pytest.mark.asyncio
async def test_developer_api_key_hashing_and_scope_enforcement() -> None:
    """API key is stored as SHA-256 hash and enforces strict granular scopes."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        admin_headers = {"Authorization": "Bearer mock-admin-token"}

        # 1. Create key with 'read:inventory' scope only
        create_res = await client.post(
            "/api/v1/developer/keys",
            headers=admin_headers,
            json={
                "name": "Read-Only Inventory Client",
                "scopes": ["read:inventory"],
                "rate_limit": 60,
            },
        )
        assert create_res.status_code in (200, 201)
        created_data = create_res.json()
        plaintext_key = created_data["key"]
        key_id = created_data["id"]
        assert plaintext_key.startswith("mfx_live_")

        # Key stored at rest must be SHA-256 hash, never plaintext
        expected_hash = hashlib.sha256(plaintext_key.encode("utf-8")).hexdigest()
        stored_entry = get_api_key_by_hash(expected_hash)
        assert stored_entry is not None
        assert stored_entry["id"] == key_id
        assert "key" not in stored_entry or stored_entry["key_hash"] == expected_hash

        # 2. Scope check: Attempt to write to sale events with read-only key -> 403 Forbidden
        key_headers = {"X-API-Key": plaintext_key}
        pos_write_res = await client.post(
            "/api/v1/events/sale",
            headers=key_headers,
            json={
                "pharmacy_id": "11111111-1111-1111-1111-111111111111",
                "product_id": "p-001-paracetamol",
                "batch_id": "b-pcm-001",
                "quantity": 1,
                "source": "pos-terminal-1",
            },
        )
        assert pos_write_res.status_code == 403
        assert "write:events" in pos_write_res.text.lower() or "scope" in pos_write_res.text.lower()


# =============================================================================
# 4. In-Memory Token Bucket Rate Limiting Tests
# =============================================================================
@pytest.mark.asyncio
async def test_token_bucket_rate_limiter_exhaustion() -> None:
    """Burst requests exceeding the configured rate limit return HTTP 429."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        admin_headers = {"Authorization": "Bearer mock-admin-token"}

        # Create key with very low limit: 2 requests per minute
        res = await client.post(
            "/api/v1/developer/keys",
            headers=admin_headers,
            json={
                "name": "Strict Rate Limit Test Key",
                "scopes": ["read:inventory", "write:events"],
                "rate_limit": 2,
            },
        )
        plaintext_key = res.json()["key"]
        key_headers = {"X-API-Key": plaintext_key}

        # First request succeeds
        res1 = await client.get("/api/v1/inventory", headers=key_headers)
        assert res1.status_code == 200

        # Second request succeeds
        res2 = await client.get("/api/v1/inventory", headers=key_headers)
        assert res2.status_code == 200

        # Third rapid request must be blocked with HTTP 429 and Retry-After header
        res3 = await client.get("/api/v1/inventory", headers=key_headers)
        assert res3.status_code == 429
        assert "retry-after" in res3.headers or "Retry-After" in res3.headers
        assert "RATE_LIMIT_EXCEEDED" in res3.text or "rate limit" in res3.text.lower()


# =============================================================================
# 5. Outbound Webhooks Engine & Signature Verification Tests
# =============================================================================
@pytest.mark.asyncio
async def test_webhook_hmac_signature_verification() -> None:
    """Webhooks engine signs payloads with HMAC-SHA256 and detects tampering."""
    secret = "test-webhook-secret-xyz-789"
    sub = create_webhook_subscription(
        url="http://mock-receiver.local/webhook",
        events=["order.created"],
        secret=secret,
        node_id="11111111-1111-1111-1111-111111111111",
    )

    received_requests: list[httpx.Request] = []

    def mock_handler(request: httpx.Request) -> httpx.Response:
        received_requests.append(request)
        return httpx.Response(200, json={"status": "ok"})

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler))

    delivery_log = await deliver_webhook(
        subscription=sub,
        event_type="order.created",
        event_id="test-evt-hmac-01",
        data={"order_id": "ord-999", "amount": 1250.0},
        client=mock_client,
    )
    assert delivery_log["success"] is True
    assert len(received_requests) == 1

    sent_request = received_requests[0]
    sig_header = sent_request.headers.get("X-MediFlux-Signature")
    assert sig_header is not None
    assert sig_header.startswith("sha256=")

    # Valid signature check
    assert verify_webhook_signature(
        raw_body=sent_request.content,
        secret=secret,
        signature_header=sig_header,
    ) is True

    # Tampered body must fail
    assert verify_webhook_signature(
        raw_body=b'{"tampered": true}',
        secret=secret,
        signature_header=sig_header,
    ) is False

    # Wrong secret must fail
    assert verify_webhook_signature(
        raw_body=sent_request.content,
        secret="wrong-secret",
        signature_header=sig_header,
    ) is False


@pytest.mark.asyncio
async def test_webhook_failure_backoff_and_auto_disable() -> None:
    """Repeated delivery failures trigger retry and auto-disable subscription."""
    sub = create_webhook_subscription(
        url="http://failing-target.local/webhook",
        events=["cascade.completed"],
        secret="whsec_test_secret_123",
        max_consecutive_failures=2,
    )

    def failing_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="Internal Server Error")

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(failing_handler))

    # First failing batch of attempts
    log1 = await deliver_webhook(
        subscription=sub,
        event_type="cascade.completed",
        event_id="evt-fail-01",
        data={"cascade_id": "casc-001"},
        max_attempts=2,
        base_delay=0.001,
        client=mock_client,
    )
    assert log1["success"] is False
    assert sub["failure_count"] == 1
    assert sub["is_active"] is True

    # Second failing batch -> triggers auto-disable
    log2 = await deliver_webhook(
        subscription=sub,
        event_type="cascade.completed",
        event_id="evt-fail-02",
        data={"cascade_id": "casc-002"},
        max_attempts=2,
        base_delay=0.001,
        client=mock_client,
    )
    assert log2["success"] is False
    assert sub["failure_count"] == 2
    assert sub["is_active"] is False, "Subscription must be auto-disabled after reaching max_consecutive_failures"
