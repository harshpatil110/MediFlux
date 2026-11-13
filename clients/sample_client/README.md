# MediFlux Sample Third-Party Client

This package provides a reference integration client and SDK demonstrating how third-party systems (such as Hospital Information Systems, retail Pharmacy Point-of-Sale software, distributor ERPs, and IoT logistics gateways) integrate securely with the MediFlux platform.

---

## 1. Architecture & Security Model

MediFlux third-party integrations adhere to zero-trust sovereign supply chain principles:

1. **Scoped API Keys:**
   - Keys are provisioned with explicit capability scopes (`read:inventory`, `write:events`, `read:stream`, `read:audit`, `use:copilot`, `manage:adapters`).
   - Plaintext keys (e.g., `mfx_live_...`) are returned **once upon creation** and hashed at rest with SHA-256 (`key_hash`).
   - Requests provide the key via HTTP header: `X-API-Key: mfx_live_...`.
2. **Node RLS Binding:**
   - Keys can be bound to specific network nodes (e.g. Pharmacy `11111111-1111-1111-1111-111111111111`).
   - Row-Level Security automatically restricts inventory and telemetry queries to authorized downstream nodes.
3. **Token-Bucket Rate Limiting:**
   - Each API key operates with an independent token bucket (default 100 requests/min).
   - If exhausted, HTTP `429 Too Many Requests` is returned with `Retry-After` and `X-RateLimit-*` headers.
4. **Outbound HMAC-SHA256 Webhooks:**
   - Subscriptions deliver events (`order.created`, `shipment.dispatched`, `batch.quarantined`, `hitl.created`, `hitl.decided`, `module.activated`).
   - Every delivery includes an `X-MediFlux-Signature: sha256={hmac}` header calculated using the pre-shared secret.

---

## 2. Quickstart: Running the Sample Client

### Prerequisites
- Python 3.11+
- MediFlux backend running locally on `http://localhost:8000` (or configured remote URL)

### Run Workflow
Execute the end-to-end 6-step integration script:

```bash
# From repository root
python clients/sample_client/client.py
```

Or via module path:
```bash
python -m clients.sample_client.client
```

---

## 3. The 6-Step Third-Party Flow

The sample client performs these operations in sequence:

1. **Local Webhook Receiver**: Spawns a background HTTP listener on an ephemeral localhost port to receive and cryptographically verify inbound webhooks.
2. **API Key Provisioning**: Requests a new API key with `write:events`, `read:inventory`, and `read:stream` scopes.
3. **Webhook Registration**: Registers the local receiver URL with MediFlux for supply chain events.
4. **Read Inventory**: Queries stock levels scoped to the authorized pharmacy node.
5. **Post a Sale**: Ingests an atomic POS dispense event (`SaleEvent`) decrementing shelf stock in real time.
6. **Verify Signed Webhook**: Receives an event delivery, validates the `X-MediFlux-Signature` HMAC-SHA256 header using constant-time comparison, and logs verification proof.

---

## 4. Python SDK Usage

```python
import asyncio
from clients.sample_client.typed_client import MediFluxClient

async def main():
    # Initialize client
    async with MediFluxClient(base_url="http://localhost:8000", api_key="mfx_live_...") as client:
        # Read Inventory
        inventory = await client.get_inventory()
        print(f"Current inventory items: {len(inventory)}")

        # Post Point-of-Sale Dispense
        sale = {
            "pharmacy_id": "11111111-1111-1111-1111-111111111111",
            "product_id": "p-001-azithromycin",
            "batch_id": "b-azi-2026-01",
            "quantity": 1,
            "source": "pos-counter-1",
        }
        res = await client.post_sale(sale)
        print(f"Sale ingestion status: {res.get('status')}")

asyncio.run(main())
```

---

## 5. Webhook Signature Verification Snippet

```python
from clients.sample_client.typed_client import MediFluxClient

is_valid = MediFluxClient.verify_webhook_signature(
    raw_body=request_body_bytes,
    secret="your_shared_secret",
    signature_header=request.headers.get("X-MediFlux-Signature"),
)

if not is_valid:
    raise PermissionError("Invalid webhook signature")
```
