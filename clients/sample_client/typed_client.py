"""MediFlux Typed Python SDK Client for Third-Party Developers.

Task 22: Sample Third-Party Client.
"""

import hashlib
import hmac
import json
import logging
from collections.abc import AsyncIterator
from typing import Any

import httpx
from pydantic import BaseModel, Field

logger = logging.getLogger("mediflux.client")


class ApiKeyModel(BaseModel):
    """API Key metadata model."""

    id: str
    name: str
    key_prefix: str
    key: str | None = None
    scopes: list[str] = Field(default_factory=list)
    node_id: str | None = None
    rate_limit: int = 100
    created_at: str


class WebhookSubscriptionModel(BaseModel):
    """Webhook subscription metadata model."""

    id: str
    url: str
    events: list[str] = Field(default_factory=list)
    secret: str
    node_id: str | None = None
    is_active: bool = True
    created_at: str


class MediFluxClient:
    """Async Python SDK client for third-party integrations with the MediFlux platform."""

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        api_key: str | None = None,
        client: httpx.AsyncClient | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.transport = transport
        self._external_client = client
        self._owned_client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._external_client is not None:
            return self._external_client
        if self._owned_client is None or self._owned_client.is_closed:
            self._owned_client = httpx.AsyncClient(
                base_url=self.base_url,
                transport=self.transport,
                timeout=10.0,
            )
        return self._owned_client

    def _headers(self, custom_headers: dict[str, str] | None = None) -> dict[str, str]:
        headers: dict[str, str] = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        if custom_headers:
            headers.update(custom_headers)
        return headers

    async def close(self) -> None:
        """Close client connection pool."""
        if self._owned_client and not self._owned_client.is_closed:
            await self._owned_client.aclose()

    async def __aenter__(self) -> "MediFluxClient":
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.close()

    # -------------------------------------------------------------------------
    # 1. Developer API Key Management
    # -------------------------------------------------------------------------
    async def create_api_key(
        self,
        name: str = "Default Client Key",
        scopes: list[str] | None = None,
        node_id: str | None = None,
        rate_limit: int = 100,
    ) -> dict[str, Any]:
        """Provision a new scoped API key. Plaintext key is returned once."""
        client = await self._get_client()
        payload = {
            "name": name,
            "scopes": scopes or ["read:inventory", "write:events"],
            "node_id": node_id,
            "rate_limit": rate_limit,
        }
        resp = await client.post(
            f"{self.base_url}/api/v1/developer/keys",
            json=payload,
            headers=self._headers(),
        )
        resp.raise_for_status()
        data = resp.json()
        if "key" in data and not self.api_key:
            self.api_key = data["key"]
        return data

    async def list_api_keys(self) -> list[dict[str, Any]]:
        """List active API keys."""
        client = await self._get_client()
        resp = await client.get(
            f"{self.base_url}/api/v1/developer/keys",
            headers=self._headers(),
        )
        resp.raise_for_status()
        return resp.json()

    async def revoke_api_key(self, key_id: str) -> dict[str, Any]:
        """Revoke an API key."""
        client = await self._get_client()
        resp = await client.delete(
            f"{self.base_url}/api/v1/developer/keys/{key_id}",
            headers=self._headers(),
        )
        resp.raise_for_status()
        return resp.json()

    # -------------------------------------------------------------------------
    # 2. Outbound Webhook Subscriptions
    # -------------------------------------------------------------------------
    async def create_webhook(
        self,
        url: str,
        events: list[str] | None = None,
        secret: str | None = None,
        node_id: str | None = None,
    ) -> dict[str, Any]:
        """Register an outbound webhook endpoint."""
        client = await self._get_client()
        payload = {
            "url": url,
            "events": events or ["*"],
            "secret": secret,
            "node_id": node_id,
        }
        resp = await client.post(
            f"{self.base_url}/api/v1/developer/webhooks",
            json=payload,
            headers=self._headers(),
        )
        resp.raise_for_status()
        return resp.json()

    async def list_webhooks(self) -> list[dict[str, Any]]:
        """List active webhook subscriptions."""
        client = await self._get_client()
        resp = await client.get(
            f"{self.base_url}/api/v1/developer/webhooks",
            headers=self._headers(),
        )
        resp.raise_for_status()
        return resp.json()

    async def trigger_test_webhook(
        self,
        subscription_id: str,
        event_type: str = "order.created",
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Trigger immediate signed test webhook delivery."""
        client = await self._get_client()
        payload = {
            "subscription_id": subscription_id,
            "event_type": event_type,
            "data": data or {"test": True, "ping": "pong"},
        }
        resp = await client.post(
            f"{self.base_url}/api/v1/developer/webhooks/{subscription_id}/test",
            json=payload,
            headers=self._headers(),
        )
        resp.raise_for_status()
        return resp.json()

    # -------------------------------------------------------------------------
    # 3. Inventory Queries (read:inventory)
    # -------------------------------------------------------------------------
    async def get_inventory(
        self,
        product_id: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Query inventory balances visible under caller node RLS scope."""
        client = await self._get_client()
        params: dict[str, Any] = {"limit": limit}
        if product_id:
            params["product_id"] = product_id

        resp = await client.get(
            f"{self.base_url}/api/v1/inventory",
            params=params,
            headers=self._headers(),
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("items", [])

    # -------------------------------------------------------------------------
    # 4. Point-of-Sale Event Ingestion (write:events)
    # -------------------------------------------------------------------------
    async def post_sale(self, sale_event: dict[str, Any]) -> dict[str, Any]:
        """Ingest single Point-of-Sale event."""
        client = await self._get_client()
        resp = await client.post(
            f"{self.base_url}/api/v1/events/sale",
            json=sale_event,
            headers=self._headers(),
        )
        resp.raise_for_status()
        return resp.json()

    # -------------------------------------------------------------------------
    # 5. Real-Time SSE Stream (read:stream)
    # -------------------------------------------------------------------------
    async def stream_events(
        self,
        topics: str = "pos.sales",
        max_events: int = 5,
    ) -> AsyncIterator[dict[str, Any]]:
        """Stream domain events over SSE."""
        client = await self._get_client()
        headers = self._headers({"Accept": "text/event-stream"})
        async with client.stream(
            "GET",
            f"{self.base_url}/api/v1/stream?topics={topics}",
            headers=headers,
            timeout=15.0,
        ) as response:
            count = 0
            async for line in response.aiter_lines():
                if line.startswith("data:"):
                    raw_data = line[len("data:") :].strip()
                    if raw_data:
                        try:
                            parsed = json.loads(raw_data)
                            yield parsed
                            count += 1
                            if count >= max_events:
                                break
                        except Exception:
                            continue

    # -------------------------------------------------------------------------
    # 6. Webhook Signature Verification Utility
    # -------------------------------------------------------------------------
    @staticmethod
    def verify_webhook_signature(
        raw_body: bytes | str,
        secret: str,
        signature_header: str,
    ) -> bool:
        """Verify HMAC-SHA256 signature against received payload."""
        if not raw_body or not secret or not signature_header:
            return False

        if isinstance(raw_body, str):
            body_bytes = raw_body.encode("utf-8")
        else:
            body_bytes = raw_body

        expected = hmac.new(secret.encode("utf-8"), body_bytes, hashlib.sha256).hexdigest()
        provided = signature_header.strip()
        if provided.startswith("sha256="):
            provided = provided[len("sha256=") :]

        return hmac.compare_digest(expected, provided)
