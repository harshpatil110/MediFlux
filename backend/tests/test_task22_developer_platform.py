# ruff: noqa: E402
"""Test suite for Task 22: Developer Scoped API Keys, Rate Limiting, Outbound Webhooks & Sample Client.

Acceptance Criteria:
1. Plaintext API key returned once; stored as SHA-256 hash in storage/db; never exposed on GET.
2. Scope enforcement: key with 'read:inventory' receives 403 Forbidden on POS sale ingestion;
   key with 'write:events' succeeds (200/202) and increments usage_count / updates last_used.
3. Token-Bucket rate limiter: key with rate_limit=3 allows 3 rapid requests and returns 429 on 4th request.
4. Webhook delivery and HMAC-SHA256 signature verification (verify_webhook_signature).
5. Webhook retry with exponential backoff and auto-disable after consecutive failures (is_active=False).
6. Sample third-party client end-to-end execution.
"""

import hashlib
import sys
import uuid
from pathlib import Path

# Add repo root to sys.path
repo_root = Path(__file__).resolve().parent.parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

import httpx
import pytest
from clients.sample_client.client import run_sample_client_flow
from httpx import ASGITransport

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
    list_webhook_deliveries,
    verify_webhook_signature,
)


@pytest.fixture(autouse=True)
def reset_developer_state():
    """Reset API keys, rate limiter, and webhooks in-memory state before each test."""
    clear_in_memory_api_keys()
    clear_in_memory_webhooks()
    rate_limiter.reset()
    yield
    clear_in_memory_api_keys()
    clear_in_memory_webhooks()
    rate_limiter.reset()


@pytest.mark.asyncio
async def test_api_key_hashing_and_never_exposed() -> None:
    """Verify plaintext API key is returned once upon creation and never exposed at rest."""
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Create API key via POST /api/v1/developer/keys
        res = await client.post(
            "/api/v1/developer/keys",
            json={
                "name": "Integration Test Key",
                "scopes": ["read:inventory"],
                "node_id": "11111111-1111-1111-1111-111111111111",
                "rate_limit": 50,
            },
        )
        assert res.status_code == 201
        data = res.json()

        # Plaintext key returned in creation response
        plaintext_key = data.get("key") or data.get("api_key")
        assert plaintext_key is not None
        assert plaintext_key.startswith("mfx_live_")
        key_id = data["id"]
        key_prefix = data["key_prefix"]
        assert plaintext_key.startswith(key_prefix)

        # 2. Verify stored record has SHA-256 hash, NOT plaintext key
        computed_hash = hashlib.sha256(plaintext_key.encode("utf-8")).hexdigest()
        stored_record = get_api_key_by_hash(computed_hash)
        assert stored_record is not None
        assert stored_record["key_hash"] == computed_hash
        assert "key" not in stored_record or stored_record.get("key") != plaintext_key

        # 3. Query GET /api/v1/developer/keys -> verify plaintext key & raw hash are omitted
        list_res = await client.get("/api/v1/developer/keys")
        assert list_res.status_code == 200
        keys_list = list_res.json()
        assert len(keys_list) >= 1

        matched_key = next((k for k in keys_list if k["id"] == key_id), None)
        assert matched_key is not None
        assert matched_key["key_prefix"] == key_prefix
        assert "key" not in matched_key
        assert "api_key" not in matched_key
        assert "key_hash" not in matched_key


@pytest.mark.asyncio
async def test_scope_enforcement_403_and_200() -> None:
    """Verify 403 on missing scope and 200/202 on valid scope, with usage increment."""
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Provision key with only 'read:inventory' (omitting 'write:events')
        key_res1 = await client.post(
            "/api/v1/developer/keys",
            json={
                "name": "Read Only Key",
                "scopes": ["read:inventory"],
                "node_id": "11111111-1111-1111-1111-111111111111",
            },
        )
        read_only_key = key_res1.json()["key"]

        # 2. Attempt POS sale ingestion -> expect 403 Forbidden
        sale_payload = {
            "pharmacy_id": "11111111-1111-1111-1111-111111111111",
            "product_id": "p-001-azithromycin",
            "batch_id": "b-azi-2026-01",
            "quantity": 1,
            "source": "pos-terminal-1",
        }
        forbidden_res = await client.post(
            "/api/v1/events/sale",
            json=sale_payload,
            headers={"X-API-Key": read_only_key},
        )
        assert forbidden_res.status_code == 403
        assert "Insufficient API key scope" in forbidden_res.json()["detail"]
        assert "write:events" in forbidden_res.json()["detail"]

        # 3. Read inventory with read_only_key -> expect 200 OK
        inv_res = await client.get(
            "/api/v1/inventory",
            headers={"X-API-Key": read_only_key},
        )
        assert inv_res.status_code == 200

        # 4. Provision key with 'write:events' and 'read:inventory'
        key_res2 = await client.post(
            "/api/v1/developer/keys",
            json={
                "name": "Read Write Key",
                "scopes": ["write:events", "read:inventory"],
                "node_id": "11111111-1111-1111-1111-111111111111",
            },
        )
        rw_key_data = key_res2.json()
        rw_key = rw_key_data["key"]
        rw_key_id = rw_key_data["id"]
        assert rw_key_id is not None

        # 5. Ingest sale with rw_key -> expect 202 Accepted
        success_sale_res = await client.post(
            "/api/v1/events/sale",
            json=sale_payload,
            headers={"X-API-Key": rw_key},
        )
        assert success_sale_res.status_code in (200, 202)

        # 6. Verify usage_count incremented and last_used updated
        rw_key_hash = hashlib.sha256(rw_key.encode("utf-8")).hexdigest()
        updated_key = get_api_key_by_hash(rw_key_hash)
        assert updated_key is not None
        assert updated_key["usage_count"] >= 1
        assert updated_key["last_used_at"] is not None


@pytest.mark.asyncio
async def test_token_bucket_rate_limiter_429() -> None:
    """Verify Token-Bucket rate limiter rejects requests with HTTP 429 when capacity exhausted."""
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Provision key with rate_limit=3
        key_res = await client.post(
            "/api/v1/developer/keys",
            json={
                "name": "Burst Test Key",
                "scopes": ["read:inventory"],
                "rate_limit": 3,
            },
        )
        assert key_res.status_code == 201
        test_key = key_res.json()["key"]

        # 2. Send 3 rapid requests -> all 3 must succeed
        for i in range(1, 4):
            res = await client.get("/api/v1/inventory", headers={"X-API-Key": test_key})
            assert res.status_code == 200, f"Request {i} failed unexpectedly with status {res.status_code}"

        # 3. Send 4th immediate request -> must return 429 Too Many Requests
        rate_limited_res = await client.get("/api/v1/inventory", headers={"X-API-Key": test_key})
        assert rate_limited_res.status_code == 429
        assert "Rate limit exceeded" in rate_limited_res.json()["detail"]
        assert "Retry-After" in rate_limited_res.headers
        assert int(rate_limited_res.headers["Retry-After"]) >= 1


@pytest.mark.asyncio
async def test_webhook_hmac_signature_and_delivery() -> None:
    """Verify outbound webhook HMAC-SHA256 signing and verify_webhook_signature helper."""
    secret = "test_super_secret_key_12345"
    sub = create_webhook_subscription(
        url="http://mock-receiver.local/webhook",
        events=["order.created"],
        secret=secret,
        node_id="11111111-1111-1111-1111-111111111111",
    )
    assert sub["secret"] == secret
    assert sub["is_active"] is True

    # 1. Simulate webhook delivery with custom mock transport
    received_requests: list[httpx.Request] = []

    def mock_handler(request: httpx.Request) -> httpx.Response:
        received_requests.append(request)
        return httpx.Response(200, json={"status": "ok"})

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler))

    delivery_log = await deliver_webhook(
        subscription=sub,
        event_type="order.created",
        event_id=str(uuid.uuid4()),
        data={"order_id": "ord-001", "units": 5},
        client=mock_client,
    )

    assert delivery_log["success"] is True
    assert delivery_log["status_code"] == 200
    assert len(received_requests) == 1

    # 2. Inspect signature header and verify with helper
    sent_request = received_requests[0]
    sig_header = sent_request.headers.get("X-MediFlux-Signature")
    assert sig_header is not None
    assert sig_header.startswith("sha256=")

    # Verify signature
    assert verify_webhook_signature(
        raw_body=sent_request.content,
        secret=secret,
        signature_header=sig_header,
    ) is True

    # Tampered body must fail verification
    assert verify_webhook_signature(
        raw_body=b'{"tampered": true}',
        secret=secret,
        signature_header=sig_header,
    ) is False

    # Incorrect secret must fail verification
    assert verify_webhook_signature(
        raw_body=sent_request.content,
        secret="wrong_secret",
        signature_header=sig_header,
    ) is False


@pytest.mark.asyncio
async def test_webhook_retries_and_auto_disable() -> None:
    """Verify exponential backoff retries and auto-disable after repeated failures."""
    secret = "secret_fail_test"
    sub = create_webhook_subscription(
        url="http://failing-endpoint.local/webhook",
        events=["batch.quarantined"],
        secret=secret,
        max_consecutive_failures=2,
    )

    attempt_count = 0

    def failing_handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempt_count
        attempt_count += 1
        return httpx.Response(500, text="Internal Server Error")

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(failing_handler))

    # Delivery 1: Max 3 attempts, all return 500
    log1 = await deliver_webhook(
        subscription=sub,
        event_type="batch.quarantined",
        event_id=str(uuid.uuid4()),
        data={"batch_id": "b-test"},
        max_attempts=3,
        base_delay=0.001,
        client=mock_client,
    )
    assert log1["success"] is False
    assert log1["attempt"] == 3
    assert attempt_count == 3
    assert sub["failure_count"] == 1
    assert sub["is_active"] is True

    # Delivery 2: Max 3 attempts, all return 500 -> reaches max_consecutive_failures (2)
    log2 = await deliver_webhook(
        subscription=sub,
        event_type="batch.quarantined",
        event_id=str(uuid.uuid4()),
        data={"batch_id": "b-test"},
        max_attempts=3,
        base_delay=0.001,
        client=mock_client,
    )
    assert log2["success"] is False
    assert sub["failure_count"] == 2
    # Subscription must now be auto-disabled!
    assert sub["is_active"] is False

    # Deliveries are logged in history
    deliveries = list_webhook_deliveries(subscription_id=sub["id"])
    assert len(deliveries) >= 6


@pytest.mark.asyncio
async def test_sample_third_party_client_flow() -> None:
    """Verify complete 6-step sample third-party client execution end-to-end."""
    results = await run_sample_client_flow(app=app)

    assert "step2_key_created" in results
    assert results["step2_key_created"]["prefix"].startswith("mfx_live_")

    assert "step3_webhook_registered" in results
    assert "step4_inventory_read" in results
    assert results["step4_inventory_read"]["count"] >= 1

    assert "step5_sale_posted" in results
    assert results["step5_sale_posted"].get("status") in ("accepted", "duplicate")

    assert "step6_webhook_verified" in results
    assert results["step6_webhook_verified"]["last_event_signature_valid"] is True
