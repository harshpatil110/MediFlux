"""Outbound Webhooks Delivery Engine, HMAC-SHA256 Signing, Retries & Auto-Disable.

Task 22: Developer Platform Webhooks.
"""

import asyncio
import hashlib
import hmac
import json
import logging
import secrets
import uuid
from datetime import UTC, datetime
from typing import Any

import httpx

from app.core.config import settings
from app.core.security import get_service_db_client

logger = logging.getLogger("mediflux.services.webhooks")

# Canonical Webhook Event Types
CANONICAL_WEBHOOK_EVENTS = [
    "order.created",
    "shipment.dispatched",
    "batch.quarantined",
    "hitl.created",
    "hitl.decided",
    "module.activated",
    "*",
]

# Event aliases for cross-task integration
WEBHOOK_EVENT_ALIASES = {
    "coldchain.quarantined": "batch.quarantined",
    "sensor.breach": "batch.quarantined",
    "pos.sales": "order.created",
}

# In-memory subscription and delivery caches
_in_memory_webhook_subs: dict[str, dict[str, Any]] = {}
_in_memory_webhook_deliveries: list[dict[str, Any]] = []


def compute_webhook_signature(payload_bytes: bytes, secret: str) -> str:
    """Compute HMAC-SHA256 hexadecimal digest for webhook payload."""
    return hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()


def verify_webhook_signature(
    raw_body: bytes | str,
    secret: str,
    signature_header: str,
) -> bool:
    """Verify HMAC-SHA256 signature against expected payload digest.

    Supports header formats 'sha256={sig}' or '{sig}'.
    Uses constant-time comparison to prevent timing attacks.
    """
    if not raw_body or not secret or not signature_header:
        return False

    if isinstance(raw_body, str):
        body_bytes = raw_body.encode("utf-8")
    else:
        body_bytes = raw_body

    expected_sig = compute_webhook_signature(body_bytes, secret)
    provided_sig = signature_header.strip()
    if provided_sig.startswith("sha256="):
        provided_sig = provided_sig[len("sha256=") :]

    return hmac.compare_digest(expected_sig, provided_sig)


def create_webhook_subscription(
    url: str,
    events: list[str] | None = None,
    secret: str | None = None,
    node_id: str | None = None,
    api_key_id: str | None = None,
    max_consecutive_failures: int = 3,
) -> dict[str, Any]:
    """Register a new outbound webhook subscription."""
    sub_id = str(uuid.uuid4())
    shared_secret = secret or secrets.token_hex(24)
    event_list = events or ["*"]
    now_iso = datetime.now(UTC).isoformat()

    sub_record: dict[str, Any] = {
        "id": sub_id,
        "url": url,
        "target_url": url,
        "events": event_list,
        "event_types": event_list,
        "secret": shared_secret,
        "secret_key": shared_secret,
        "node_id": node_id,
        "api_key_id": api_key_id,
        "is_active": True,
        "failure_count": 0,
        "max_consecutive_failures": max_consecutive_failures,
        "created_at": now_iso,
    }

    _in_memory_webhook_subs[sub_id] = sub_record

    # Sync to Supabase if configured
    if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY:
        try:
            client = get_service_db_client()
            if client:
                client.table("webhook_subscriptions").insert(
                    {
                        "id": sub_id,
                        "node_id": node_id,
                        "target_url": url,
                        "url": url,
                        "event_types": event_list,
                        "secret_key": shared_secret,
                        "is_active": True,
                        "failure_count": 0,
                        "created_at": now_iso,
                    }
                ).execute()
        except Exception as exc:
            logger.warning("Supabase webhook_subscriptions insert skipped/failed: %s", exc)

    logger.info("Webhook registered: id=%s url=%s events=%s", sub_id, url, event_list)
    return sub_record


def list_webhook_subscriptions(
    node_id: str | None = None, is_admin: bool = False
) -> list[dict[str, Any]]:
    """List webhook subscriptions filtered by node scope."""
    results: list[dict[str, Any]] = []

    for sub in _in_memory_webhook_subs.values():
        if not is_admin and node_id and sub.get("node_id") and sub.get("node_id") != node_id:
            continue
        results.append(sub)

    if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY:
        try:
            client = get_service_db_client()
            if client:
                query = client.table("webhook_subscriptions").select("*")
                if not is_admin and node_id:
                    query = query.eq("node_id", node_id)
                res = query.execute()
                existing_ids = {r["id"] for r in results}
                for row in res.data or []:
                    if row["id"] not in existing_ids:
                        row["url"] = row.get("target_url") or row.get("url")
                        row["events"] = row.get("event_types") or row.get("events", [])
                        row["secret"] = row.get("secret_key") or row.get("secret")
                        results.append(row)
        except Exception as exc:
            logger.warning("Supabase webhook_subscriptions list failed: %s", exc)

    return results


def get_webhook_subscription(subscription_id: str) -> dict[str, Any] | None:
    """Retrieve a webhook subscription by ID."""
    if subscription_id in _in_memory_webhook_subs:
        return _in_memory_webhook_subs[subscription_id]

    if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY:
        try:
            client = get_service_db_client()
            if client:
                res = client.table("webhook_subscriptions").select("*").eq("id", subscription_id).execute()
                if res.data:
                    row = res.data[0]
                    row["url"] = row.get("target_url") or row.get("url")
                    row["events"] = row.get("event_types") or row.get("events", [])
                    row["secret"] = row.get("secret_key") or row.get("secret")
                    _in_memory_webhook_subs[subscription_id] = row
                    return row
        except Exception as exc:
            logger.warning("Supabase webhook_subscriptions query failed: %s", exc)

    return None


def delete_webhook_subscription(subscription_id: str) -> bool:
    """Deactivate or remove a webhook subscription."""
    if subscription_id in _in_memory_webhook_subs:
        _in_memory_webhook_subs[subscription_id]["is_active"] = False

    if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY:
        try:
            client = get_service_db_client()
            if client:
                client.table("webhook_subscriptions").update({"is_active": False}).eq("id", subscription_id).execute()
        except Exception as exc:
            logger.warning("Supabase webhook_subscriptions update failed: %s", exc)

    logger.info("Webhook subscription deactivated: id=%s", subscription_id)
    return True


def list_webhook_deliveries(
    subscription_id: str | None = None, limit: int = 50
) -> list[dict[str, Any]]:
    """List recent webhook delivery attempt logs."""
    logs = _in_memory_webhook_deliveries
    if subscription_id:
        logs = [log for log in logs if log.get("subscription_id") == subscription_id]

    sorted_logs = sorted(logs, key=lambda x: x.get("created_at", ""), reverse=True)
    return sorted_logs[:limit]


async def deliver_webhook(
    subscription: dict[str, Any],
    event_type: str,
    event_id: str,
    data: dict[str, Any],
    node_id: str | None = None,
    max_attempts: int = 3,
    base_delay: float = 0.05,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    """Execute HMAC-signed webhook delivery with exponential backoff retries and auto-disable.

    Returns the delivery log record.
    """
    sub_id = subscription["id"]
    target_url = subscription.get("url") or subscription.get("target_url", "")
    secret = subscription.get("secret") or subscription.get("secret_key", "")
    now_iso = datetime.now(UTC).isoformat()
    delivery_id = str(uuid.uuid4())

    envelope = {
        "delivery_id": delivery_id,
        "event_id": event_id,
        "event_type": event_type,
        "timestamp": now_iso,
        "node_id": node_id or subscription.get("node_id"),
        "data": data,
    }

    raw_body = json.dumps(envelope, separators=(",", ":"), sort_keys=True).encode("utf-8")
    sig = compute_webhook_signature(raw_body, secret)
    headers = {
        "Content-Type": "application/json",
        "X-MediFlux-Signature": f"sha256={sig}",
        "X-Webhook-Signature": f"sha256={sig}",
        "X-MediFlux-Event": event_type,
        "X-MediFlux-Delivery": delivery_id,
    }

    last_log: dict[str, Any] = {}
    delivery_succeeded = False

    # Use caller-provided client or instantiate temporary client
    owns_client = client is None
    async_client = client or httpx.AsyncClient(timeout=5.0)

    try:
        for attempt in range(1, max_attempts + 1):
            attempt_time = datetime.now(UTC).isoformat()
            status_code: int | None = None
            response_body: str | None = None
            error_str: str | None = None

            try:
                resp = await async_client.post(target_url, content=raw_body, headers=headers)
                status_code = resp.status_code
                response_body = resp.text[:500] if resp.text else None
                delivery_succeeded = 200 <= resp.status_code < 300
            except Exception as exc:
                error_str = str(exc)
                delivery_succeeded = False

            log_entry = {
                "id": str(uuid.uuid4()),
                "subscription_id": sub_id,
                "event_id": event_id,
                "event_type": event_type,
                "payload": envelope,
                "status_code": status_code,
                "response_body": response_body,
                "error": error_str,
                "success": delivery_succeeded,
                "attempt": attempt,
                "delivered_at": attempt_time,
                "created_at": attempt_time,
            }
            _in_memory_webhook_deliveries.append(log_entry)
            last_log = log_entry

            if delivery_succeeded:
                # Reset consecutive failure counter
                subscription["failure_count"] = 0
                logger.info("Webhook %s delivered successfully on attempt %d", sub_id, attempt)
                break
            else:
                logger.warning(
                    "Webhook %s delivery failed on attempt %d/%d: status=%s error=%s",
                    sub_id,
                    attempt,
                    max_attempts,
                    status_code,
                    error_str,
                )
                if attempt < max_attempts:
                    delay = base_delay * (2 ** (attempt - 1))
                    await asyncio.sleep(delay)

        # After all retry attempts exhausted
        if not delivery_succeeded:
            subscription["failure_count"] = subscription.get("failure_count", 0) + 1
            max_failures = subscription.get("max_consecutive_failures", 3)
            if subscription["failure_count"] >= max_failures:
                subscription["is_active"] = False
                logger.error(
                    "Webhook %s auto-disabled: reached %d consecutive failed deliveries",
                    sub_id,
                    subscription["failure_count"],
                )
                # Sync deactivation to Supabase
                if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY:
                    try:
                        db = get_service_db_client()
                        if db:
                            db.table("webhook_subscriptions").update({"is_active": False}).eq("id", sub_id).execute()
                    except Exception:
                        pass
    finally:
        if owns_client:
            await async_client.aclose()

    return last_log


async def dispatch_webhook_event(
    event_type: str,
    data: dict[str, Any],
    node_id: str | None = None,
    event_id: str | None = None,
    client: httpx.AsyncClient | None = None,
) -> list[dict[str, Any]]:
    """Dispatch an event to all matching active webhook subscriptions."""
    eid = event_id or str(uuid.uuid4())
    canonical_type = WEBHOOK_EVENT_ALIASES.get(event_type, event_type)

    matching_subs: list[dict[str, Any]] = []
    for sub in _in_memory_webhook_subs.values():
        if not sub.get("is_active", True):
            continue

        # Check node RLS scope: if sub has node_id, only receive events for that node
        sub_node = sub.get("node_id")
        if sub_node and node_id and sub_node != node_id:
            continue

        events = sub.get("events") or sub.get("event_types", [])
        if "*" in events or "all" in events or canonical_type in events or event_type in events:
            matching_subs.append(sub)

    delivery_results: list[dict[str, Any]] = []
    for sub in matching_subs:
        log = await deliver_webhook(
            subscription=sub,
            event_type=canonical_type,
            event_id=eid,
            data=data,
            node_id=node_id,
            client=client,
        )
        delivery_results.append(log)

    return delivery_results


def clear_in_memory_webhooks() -> None:
    """Clear in-memory subscriptions and delivery logs (for tests)."""
    _in_memory_webhook_subs.clear()
    _in_memory_webhook_deliveries.clear()
