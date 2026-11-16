"""Expo Remote Push Notification Service for MediFlux (Task M7).

Dispatches privacy-safe push notifications for critical events (HITL approvals and Cold-Chain quarantines)
to registered device tokens with role/node filtering, automated invalid token cleanup (DeviceNotRegistered),
and non-blocking error handling.
"""

import logging
from typing import Any

import httpx

from app.api.v1.endpoints.devices import _in_memory_device_tokens
from app.core.config import settings
from app.core.hitl_policy import get_allowed_roles
from app.core.security import get_service_db_client
from app.events.bus import in_process_event_bus
from app.events.models import EventEnvelope
from app.graphs.coldchain import write_audit_entry

logger = logging.getLogger("mediflux.services.push")

# Optional custom client or transport for unit testing
_test_http_client: httpx.AsyncClient | None = None


def set_push_test_client(client: httpx.AsyncClient | None) -> None:
    """Set an injectable httpx.AsyncClient for testing."""
    global _test_http_client
    _test_http_client = client


def get_all_device_tokens() -> list[dict[str, Any]]:
    """Retrieve all device tokens merging in-memory and Supabase."""
    devices: list[dict[str, Any]] = list(_in_memory_device_tokens.values())
    seen_tokens = {d.get("token") for d in devices}

    if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY:
        try:
            client = get_service_db_client()
            if client:
                res = client.table("device_tokens").select("*").execute()
                if res.data:
                    for row in res.data:
                        if row.get("token") not in seen_tokens:
                            devices.append(row)
                            seen_tokens.add(row.get("token"))
        except Exception as exc:
            logger.debug("Supabase device tokens fetch failed: %s", exc)

    return devices


async def delete_invalid_token(token: str) -> None:
    """Remove an invalid or unregistered token from all stores."""
    # 1. In-memory store
    _in_memory_device_tokens.pop(token, None)

    # 2. Supabase DB
    if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY:
        try:
            client = get_service_db_client()
            if client:
                client.table("device_tokens").delete().eq("token", token).execute()
        except Exception as exc:
            logger.debug("Failed deleting invalid token from Supabase: %s", exc)

    # 3. Cryptographic audit entry
    masked_token = f"{token[:12]}...{token[-4:]}" if len(token) > 16 else "***"
    try:
        await write_audit_entry(
            actor="ExpoPushService",
            action="push.notification.cleaned_invalid_token",
            entity_type="device_token",
            entity_id=token,
            payload={"token_masked": masked_token, "reason": "DeviceNotRegistered"},
            explanation=f"Automatically purged invalid push token {masked_token}",
        )
    except Exception as exc:
        logger.debug("Audit logging for invalid token cleanup failed: %s", exc)


def select_recipients_for_hitl(
    task_type: str,
    node_id: str | None = None,
) -> list[dict[str, Any]]:
    """Select device tokens for users eligible to decide the HITL task."""
    allowed = get_allowed_roles(task_type)
    all_devices = get_all_device_tokens()
    recipients: list[dict[str, Any]] = []

    for dev in all_devices:
        prefs = dev.get("preferences") or {}
        # Check preference
        if prefs.get("hitl") is False or prefs.get("approvalAlerts") is False:
            continue

        role = str(dev.get("role") or "")
        # Role check
        if role not in allowed and "admin" not in allowed:
            continue
        if role not in allowed and role != "admin":
            continue

        # Node check: admin and regulator see all; other roles must match node
        dev_node = dev.get("node_id")
        if node_id and dev_node and role not in ("admin", "regulator"):
            if str(dev_node) != str(node_id):
                continue

        recipients.append(dev)

    return recipients


def select_recipients_for_coldchain(
    node_id: str | None = None,
) -> list[dict[str, Any]]:
    """Select device tokens for users affected by cold-chain quarantines."""
    all_devices = get_all_device_tokens()
    recipients: list[dict[str, Any]] = []

    for dev in all_devices:
        prefs = dev.get("preferences") or {}
        # Check preference
        if prefs.get("coldchain") is False or prefs.get("coldchainAlerts") is False:
            continue

        role = str(dev.get("role") or "")
        # Pharmacy, stockist, distributor, manufacturer, admin, regulator
        dev_node = dev.get("node_id")
        if node_id and dev_node and role not in ("admin", "regulator"):
            if str(dev_node) != str(node_id):
                continue

        recipients.append(dev)

    return recipients


async def send_expo_push_messages(messages: list[dict[str, Any]]) -> dict[str, Any]:
    """Send batch of push messages to Expo push service and process receipts."""
    if not messages:
        return {"sent": 0, "cleaned": 0}

    expo_url = getattr(settings, "EXPO_PUSH_URL", "https://exp.host/--/api/v2/push/send")
    sent_count = 0
    cleaned_count = 0

    try:
        if _test_http_client:
            resp = await _test_http_client.post(expo_url, json=messages)
        else:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(expo_url, json=messages)

        if resp.status_code == 200:
            data = resp.json()
            tickets = data.get("data", [])
            for idx, ticket in enumerate(tickets):
                target_token = messages[idx].get("to")
                status_val = ticket.get("status")
                if status_val == "ok":
                    sent_count += 1
                elif status_val == "error":
                    err_code = (ticket.get("details") or {}).get("error")
                    if err_code in ("DeviceNotRegistered", "InvalidCredentials") or "not registered" in str(ticket).lower():
                        if target_token:
                            await delete_invalid_token(target_token)
                            cleaned_count += 1
                    else:
                        logger.warning("Expo push ticket error for token %s: %s", target_token, ticket)
        else:
            logger.warning("Expo push service returned HTTP %s: %s", resp.status_code, resp.text)
    except Exception as exc:
        logger.warning("Expo push delivery exception (non-blocking): %s", exc)

    return {"sent": sent_count, "cleaned": cleaned_count}


async def dispatch_push_for_hitl_created(payload: dict[str, Any]) -> None:
    """Prepare and dispatch privacy-safe push notification for a new HITL approval task."""
    if not getattr(settings, "PUSH_ENABLED", True):
        return

    task_id = str(payload.get("task_id") or payload.get("id") or "")
    task_type = str(payload.get("task_type") or "task")
    risk_level = str(payload.get("risk_level") or "high").upper()
    node_id = payload.get("node_id")

    recipients = select_recipients_for_hitl(task_type, node_id=node_id)
    if not recipients:
        return

    human_title = f"MediFlux: Approval Required ({risk_level})"
    human_body = f"New {task_type.replace('_', ' ').title()} requires review. Tap to open."

    messages = [
        {
            "to": dev.get("token"),
            "sound": "default",
            "title": human_title,
            "body": human_body,
            "data": {
                "type": "hitl.created",
                "taskId": task_id,
                "deepLink": f"/approvals/{task_id}",
            },
        }
        for dev in recipients
        if dev.get("token")
    ]

    res = await send_expo_push_messages(messages)

    try:
        await write_audit_entry(
            actor="ExpoPushService",
            action="push.notification.sent",
            entity_type="hitl_task",
            entity_id=task_id,
            payload={
                "event_type": "hitl.created",
                "recipients_count": len(messages),
                "sent_count": res.get("sent", 0),
                "cleaned_count": res.get("cleaned", 0),
            },
            explanation=f"Dispatched push notifications to {len(messages)} devices for HITL task {task_id}",
        )
    except Exception as exc:
        logger.debug("Audit write for HITL push failed: %s", exc)


async def dispatch_push_for_batch_quarantined(payload: dict[str, Any]) -> None:
    """Prepare and dispatch privacy-safe push notification for a cold-chain batch quarantine."""
    if not getattr(settings, "PUSH_ENABLED", True):
        return

    batch_id = str(payload.get("batch_id") or "")
    batch_no = str(payload.get("batch_no") or batch_id)
    node_id = payload.get("node_id")
    node_name = payload.get("node_name") or "Supply Chain Hub"

    recipients = select_recipients_for_coldchain(node_id=node_id)
    if not recipients:
        return

    human_title = "MediFlux Alert: Cold-Chain Quarantined"
    human_body = f"Batch {batch_no} was quarantined at {node_name}. Tap to inspect telemetry."

    messages = [
        {
            "to": dev.get("token"),
            "sound": "default",
            "title": human_title,
            "body": human_body,
            "data": {
                "type": "batch.quarantined",
                "batchId": batch_id,
                "deepLink": f"/cold-chain/{batch_id}",
            },
        }
        for dev in recipients
        if dev.get("token")
    ]

    res = await send_expo_push_messages(messages)

    try:
        await write_audit_entry(
            actor="ExpoPushService",
            action="push.notification.sent",
            entity_type="batch",
            entity_id=batch_id,
            payload={
                "event_type": "batch.quarantined",
                "recipients_count": len(messages),
                "sent_count": res.get("sent", 0),
                "cleaned_count": res.get("cleaned", 0),
            },
            explanation=f"Dispatched push notifications to {len(messages)} devices for quarantined batch {batch_id}",
        )
    except Exception as exc:
        logger.debug("Audit write for coldchain push failed: %s", exc)


async def push_event_bus_listener(event: EventEnvelope) -> None:
    """Direct listener callback for in_process_event_bus."""
    try:
        evt_type = str(event.type or "")
        payload = event.payload or {}

        if evt_type in ("hitl.created", "hitl"):
            if evt_type == "hitl.created" or payload.get("status") == "pending":
                await dispatch_push_for_hitl_created(payload)
        elif evt_type in ("batch.quarantined", "coldchain.quarantined", "coldchain"):
            if evt_type in ("batch.quarantined", "coldchain.quarantined") or payload.get("quarantined"):
                await dispatch_push_for_batch_quarantined(payload)
    except Exception as exc:
        logger.warning("Push event bus listener error (non-blocking): %s", exc)


def register_push_listeners() -> None:
    """Register listener with in-process event bus."""
    in_process_event_bus.register_listener("hitl", push_event_bus_listener)
    in_process_event_bus.register_listener("hitl.created", push_event_bus_listener)
    in_process_event_bus.register_listener("coldchain", push_event_bus_listener)
    in_process_event_bus.register_listener("coldchain.quarantined", push_event_bus_listener)
    in_process_event_bus.register_listener("batch.quarantined", push_event_bus_listener)
