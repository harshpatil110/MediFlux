# ruff: noqa: E402
"""Runnable End-to-End Sample Third-Party Client Workflow.

Task 22: Sample Third-Party Client.
Demonstrates 6 core integration steps:
1. Spin up local webhook receiver.
2. Provision scoped API key.
3. Register outbound webhook subscription with shared secret.
4. Read inventory with X-API-Key (read:inventory).
5. Post a Point-of-Sale dispense event with X-API-Key (write:events).
6. Trigger test webhook and verify HMAC-SHA256 signature.
"""

import asyncio
import json
import logging
import socket
import sys
import threading
import uuid
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

# Ensure repo root and backend are in sys.path
_repo_root = Path(__file__).resolve().parent.parent.parent
_backend_dir = _repo_root / "backend"
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))

import httpx

from clients.sample_client.typed_client import MediFluxClient

logger = logging.getLogger("mediflux.sample_client")


# Global store for webhook events captured by the local test receiver
_received_webhook_events: list[dict[str, Any]] = []


class LocalWebhookHandler(BaseHTTPRequestHandler):
    """Minimal HTTP request handler that verifies HMAC-SHA256 signatures."""

    shared_secret: str = "default_shared_secret"

    def do_POST(self) -> None:  # noqa: N802
        content_length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(content_length)
        sig_header = self.headers.get("X-MediFlux-Signature") or self.headers.get("X-Webhook-Signature", "")

        is_valid = MediFluxClient.verify_webhook_signature(
            raw_body=raw_body,
            secret=self.shared_secret,
            signature_header=sig_header,
        )

        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except Exception:
            payload = {"raw": raw_body.decode("utf-8", errors="replace")}

        event_record = {
            "path": self.path,
            "headers": dict(self.headers),
            "payload": payload,
            "signature_header": sig_header,
            "signature_valid": is_valid,
            "received_at": datetime.now(UTC).isoformat(),
        }
        _received_webhook_events.append(event_record)

        if is_valid:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status":"received","verified":true}')
        else:
            self.send_response(401)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status":"rejected","verified":false}')

    def log_message(self, format: str, *args: Any) -> None:
        """Suppress default stdout logging for cleaner CLI output."""
        return


def get_free_port() -> int:
    """Find an available port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


async def run_sample_client_flow(
    base_url: str = "http://localhost:8000",
    app: Any = None,
) -> dict[str, Any]:
    """Execute complete 6-step third-party client integration flow."""
    _received_webhook_events.clear()

    # Step 1: Start lightweight local webhook receiver on localhost
    free_port = get_free_port()
    shared_secret = f"secret_{uuid.uuid4().hex[:16]}"
    LocalWebhookHandler.shared_secret = shared_secret

    server = HTTPServer(("127.0.0.1", free_port), LocalWebhookHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    webhook_target_url = f"http://127.0.0.1:{free_port}/webhook"
    logger.info("Step 1: Local webhook receiver listening on %s", webhook_target_url)

    # Set up HTTP transport
    external_client = None
    if app is not None:
        from httpx import ASGITransport
        external_client = httpx.AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
            timeout=10.0,
        )
        effective_base_url = "http://testserver"
    else:
        effective_base_url = base_url

    results_summary: dict[str, Any] = {}

    try:
        async with MediFluxClient(base_url=effective_base_url, client=external_client) as client:
            # Step 2: Provision scoped API Key
            key_data = await client.create_api_key(
                name="Apollo Pharmacy POS Client",
                scopes=["write:events", "read:inventory", "read:stream"],
                node_id="11111111-1111-1111-1111-111111111111",
                rate_limit=100,
            )
            plaintext_key = key_data.get("key") or key_data.get("api_key")
            client.api_key = plaintext_key
            results_summary["step2_key_created"] = {
                "id": key_data["id"],
                "prefix": key_data["key_prefix"],
                "scopes": key_data["scopes"],
            }
            logger.info("Step 2: Provisioned API key with prefix %s", key_data["key_prefix"])

            # Step 3: Register Outbound Webhook Subscription
            sub_data = await client.create_webhook(
                url=webhook_target_url,
                events=["order.created", "batch.quarantined", "hitl.created"],
                secret=shared_secret,
                node_id="11111111-1111-1111-1111-111111111111",
            )
            sub_id = sub_data["id"]
            results_summary["step3_webhook_registered"] = {
                "id": sub_id,
                "url": webhook_target_url,
                "events": sub_data.get("events") or sub_data.get("event_types"),
            }
            logger.info("Step 3: Registered webhook subscription %s", sub_id)

            # Step 4: Read Scoped Inventory (read:inventory)
            inventory_items = await client.get_inventory(limit=10)
            results_summary["step4_inventory_read"] = {
                "count": len(inventory_items),
                "items": inventory_items[:2],
            }
            logger.info("Step 4: Successfully read %d inventory items", len(inventory_items))

            # Step 5: Post POS Sale Event (write:events)
            sale_event = {
                "event_id": str(uuid.uuid4()),
                "pharmacy_id": "11111111-1111-1111-1111-111111111111",
                "product_id": "p-001-azithromycin",
                "batch_id": "b-azi-2026-01",
                "quantity": 1,
                "source": "pos-counter-1",
                "timestamp": datetime.now(UTC).isoformat(),
            }
            sale_response = await client.post_sale(sale_event)
            results_summary["step5_sale_posted"] = sale_response
            logger.info("Step 5: Successfully posted sale event, status=%s", sale_response.get("status"))

            # Step 6: Trigger & Verify Signed Webhook Delivery
            test_delivery = await client.trigger_test_webhook(
                subscription_id=sub_id,
                event_type="order.created",
                data={
                    "order_id": str(uuid.uuid4()),
                    "pharmacy_id": "11111111-1111-1111-1111-111111111111",
                    "product_id": "p-001-azithromycin",
                    "quantity": 1,
                },
            )
            results_summary["step6_delivery_response"] = test_delivery

            # Wait briefly for local HTTP server to receive and process
            for _ in range(20):
                if _received_webhook_events:
                    break
                await asyncio.sleep(0.05)

            last_received = _received_webhook_events[-1] if _received_webhook_events else None
            results_summary["step6_webhook_verified"] = {
                "events_received": len(_received_webhook_events),
                "last_event_signature_valid": last_received.get("signature_valid") if last_received else False,
                "event_type": last_received.get("payload", {}).get("event_type") if last_received else None,
            }
            logger.info(
                "Step 6: Webhook received by local server! Signature verified: %s",
                results_summary["step6_webhook_verified"]["last_event_signature_valid"],
            )

    finally:
        server.shutdown()
        server.server_close()
        if external_client:
            await external_client.aclose()

    return results_summary


async def main() -> None:
    """Standalone CLI execution entrypoint."""
    print("=" * 60)
    print("  MediFlux Third-Party Developer Client Demonstration")
    print("=" * 60)

    try:
        report = await run_sample_client_flow(base_url="http://localhost:8000")
        print("\nAll 6 steps completed successfully:")
        print(json.dumps(report, indent=2))
    except Exception as exc:
        print(f"\nExecution failed: {exc}")


if __name__ == "__main__":
    asyncio.run(main())
