"""Developer Platform API Endpoints: Scoped API Keys & Outbound Webhooks.

Task 22: Developer Platform.
"""

import logging
import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Header, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.core.security import get_actor
from app.services.api_keys import (
    create_api_key,
    get_api_key_by_id,
    list_api_keys,
    revoke_api_key,
)
from app.services.webhooks import (
    create_webhook_subscription,
    delete_webhook_subscription,
    deliver_webhook,
    get_webhook_subscription,
    list_webhook_deliveries,
    list_webhook_subscriptions,
)

logger = logging.getLogger("mediflux.api.developer")

router = APIRouter(prefix="/developer", tags=["Developer Platform & API Keys"])
webhooks_alias_router = APIRouter(prefix="/webhooks", tags=["Webhooks Engine"])


# -----------------------------------------------------------------------------
# Request & Response Schemas
# -----------------------------------------------------------------------------
class CreateApiKeyRequest(BaseModel):
    """Schema for provisioning a new scoped developer API key."""

    name: str = Field(default="Default API Key", description="Human-readable label for key")
    scopes: list[str] = Field(
        default_factory=lambda: ["read:inventory", "write:events"],
        description="Allowed scopes: read:inventory, write:events, read:stream, read:audit, use:copilot, manage:adapters, *",
    )
    node_id: str | None = Field(default=None, description="Optional node UUID binding")
    rate_limit: int = Field(default=100, ge=1, le=10000, description="Requests permitted per minute")


class ApiKeyCreatedResponse(BaseModel):
    """Response containing plaintext API key returned once upon creation."""

    id: str
    name: str
    key_prefix: str
    key: str = Field(description="Plaintext key returned once and only once")
    api_key: str = Field(description="Plaintext key alias")
    scopes: list[str]
    node_id: str | None = None
    rate_limit: int
    created_at: str


class CreateWebhookRequest(BaseModel):
    """Schema for registering an outbound webhook subscription."""

    url: str = Field(description="Target HTTPS/HTTP webhook receiver URL")
    events: list[str] = Field(
        default_factory=lambda: ["*"],
        description="Event types: order.created, shipment.dispatched, batch.quarantined, hitl.created, hitl.decided, module.activated, *",
    )
    secret: str | None = Field(default=None, description="Optional shared secret; auto-generated if omitted")
    node_id: str | None = Field(default=None, description="Optional node UUID scoping")


class TestWebhookRequest(BaseModel):
    """Schema for manually triggering a signed test webhook delivery."""

    event_type: str = Field(default="order.created", description="Event type to simulate")
    subscription_id: str | None = Field(default=None, description="Subscription ID to test")
    data: dict[str, Any] = Field(default_factory=dict, description="Payload data")


# -----------------------------------------------------------------------------
# API Key Endpoints
# -----------------------------------------------------------------------------
@router.post(
    "/keys",
    summary="Provision Scoped Developer API Key",
    description="Generate a cryptographically random API key. Plaintext key is returned ONCE and only once.",
    status_code=status.HTTP_201_CREATED,
    response_model=ApiKeyCreatedResponse,
)
async def provision_api_key(
    req: CreateApiKeyRequest,
    authorization: Annotated[str | None, Header()] = None,
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> ApiKeyCreatedResponse:
    """Provision a new scoped API key."""
    # Resolve caller identity if provided (allowing bootstrap in dev/test)
    bound_node_id = req.node_id
    if authorization or x_api_key:
        try:
            actor = await get_actor(authorization=authorization, x_api_key=x_api_key)
            if actor.role not in ("admin", "developer", "system_admin") and actor.node_id:
                bound_node_id = actor.node_id
        except Exception:
            pass

    record, plaintext_key = create_api_key(
        name=req.name,
        scopes=req.scopes,
        node_id=bound_node_id,
        rate_limit=req.rate_limit,
    )

    return ApiKeyCreatedResponse(
        id=record["id"],
        name=record["name"],
        key_prefix=record["key_prefix"],
        key=plaintext_key,
        api_key=plaintext_key,
        scopes=record["scopes"],
        node_id=record.get("node_id"),
        rate_limit=record["rate_limit"],
        created_at=record["created_at"],
    )


@router.get(
    "/keys",
    summary="List Developer API Keys",
    description="List active API keys without exposing plaintext keys or raw hashes.",
)
async def list_keys(
    authorization: Annotated[str | None, Header()] = None,
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> list[dict[str, Any]]:
    """Retrieve API key metadata scoped to caller."""
    is_admin = True
    node_id = None
    if authorization or x_api_key:
        try:
            actor = await get_actor(authorization=authorization, x_api_key=x_api_key)
            is_admin = actor.role in ("admin", "developer", "system_admin")
            node_id = actor.node_id
        except Exception:
            pass

    return list_api_keys(node_id=node_id, is_admin=is_admin)


@router.delete(
    "/keys/{key_id}",
    summary="Revoke Developer API Key",
    description="Revoke an API key so subsequent requests return 401 Unauthorized.",
)
async def revoke_key(key_id: str) -> dict[str, Any]:
    """Revoke an API key."""
    existing = get_api_key_by_id(key_id)
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")

    revoke_api_key(key_id)
    return {"status": "revoked", "id": key_id}


# -----------------------------------------------------------------------------
# Webhook Endpoints (Mounted under /api/v1/developer/webhooks & /api/v1/webhooks)
# -----------------------------------------------------------------------------
@router.post(
    "/webhooks",
    summary="Register Webhook Subscription",
    description="Register an outbound HTTP webhook subscription with HMAC-SHA256 signing.",
    status_code=status.HTTP_201_CREATED,
)
@webhooks_alias_router.post("", status_code=status.HTTP_201_CREATED)
async def register_webhook(
    req: CreateWebhookRequest,
    authorization: Annotated[str | None, Header()] = None,
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> dict[str, Any]:
    """Register a new webhook subscription."""
    bound_node_id = req.node_id
    if authorization or x_api_key:
        try:
            actor = await get_actor(authorization=authorization, x_api_key=x_api_key)
            if actor.role not in ("admin", "developer") and actor.node_id:
                bound_node_id = actor.node_id
        except Exception:
            pass

    sub = create_webhook_subscription(
        url=req.url,
        events=req.events,
        secret=req.secret,
        node_id=bound_node_id,
    )
    return sub


@router.get(
    "/webhooks",
    summary="List Webhook Subscriptions",
    description="List active webhook subscriptions filtered by caller scope.",
)
@webhooks_alias_router.get("")
async def get_webhooks(
    authorization: Annotated[str | None, Header()] = None,
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> list[dict[str, Any]]:
    """List webhook subscriptions."""
    is_admin = True
    node_id = None
    if authorization or x_api_key:
        try:
            actor = await get_actor(authorization=authorization, x_api_key=x_api_key)
            is_admin = actor.role in ("admin", "developer")
            node_id = actor.node_id
        except Exception:
            pass

    return list_webhook_subscriptions(node_id=node_id, is_admin=is_admin)


@router.delete(
    "/webhooks/{subscription_id}",
    summary="Deactivate Webhook Subscription",
)
@webhooks_alias_router.delete("/{subscription_id}")
async def deactivate_webhook(subscription_id: str) -> dict[str, Any]:
    """Deactivate or remove a webhook subscription."""
    sub = get_webhook_subscription(subscription_id)
    if not sub:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found")

    delete_webhook_subscription(subscription_id)
    return {"status": "deactivated", "id": subscription_id}


@router.get(
    "/webhooks/deliveries",
    summary="List Webhook Deliveries",
    description="List recent webhook delivery attempt logs.",
)
@webhooks_alias_router.get("/deliveries")
async def get_deliveries(
    limit: int = Query(default=50, ge=1, le=200),
) -> list[dict[str, Any]]:
    """List delivery logs."""
    return list_webhook_deliveries(limit=limit)


@router.get(
    "/webhooks/{subscription_id}/deliveries",
    summary="List Deliveries for Subscription",
)
@webhooks_alias_router.get("/{subscription_id}/deliveries")
async def get_subscription_deliveries(
    subscription_id: str,
    limit: int = Query(default=50, ge=1, le=200),
) -> list[dict[str, Any]]:
    """List delivery logs for a specific subscription."""
    return list_webhook_deliveries(subscription_id=subscription_id, limit=limit)


@router.post(
    "/webhooks/{subscription_id}/test",
    summary="Test Webhook Delivery",
    description="Trigger an immediate signed test delivery to a subscription endpoint.",
)
@webhooks_alias_router.post("/{subscription_id}/test")
async def test_webhook_by_id(
    subscription_id: str,
    req: TestWebhookRequest | None = None,
) -> dict[str, Any]:
    """Deliver a test webhook event to a subscription."""
    sub = get_webhook_subscription(subscription_id)
    if not sub:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found")

    event_type = req.event_type if req else "order.created"
    data = req.data if req and req.data else {
        "order_id": str(uuid.uuid4()),
        "product_id": "p-001-azithromycin",
        "quantity": 10,
        "note": "Test webhook delivery from MediFlux platform",
    }

    delivery_log = await deliver_webhook(
        subscription=sub,
        event_type=event_type,
        event_id=str(uuid.uuid4()),
        data=data,
    )
    return delivery_log


@router.post(
    "/webhooks/test",
    summary="Test Webhook Delivery (General)",
    description="Deliver a test webhook event to the specified or most recent subscription.",
)
@webhooks_alias_router.post("/test")
async def test_webhook_general(req: TestWebhookRequest) -> dict[str, Any]:
    """Deliver a test webhook event."""
    sub = None
    if req.subscription_id:
        sub = get_webhook_subscription(req.subscription_id)
    else:
        subs = list_webhook_subscriptions(is_admin=True)
        if subs:
            sub = subs[-1]

    if not sub:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active webhook subscription found")

    data = req.data or {
        "order_id": str(uuid.uuid4()),
        "product_id": "p-001-azithromycin",
        "quantity": 5,
        "note": "General test webhook delivery",
    }

    delivery_log = await deliver_webhook(
        subscription=sub,
        event_type=req.event_type or "order.created",
        event_id=str(uuid.uuid4()),
        data=data,
    )
    return delivery_log
