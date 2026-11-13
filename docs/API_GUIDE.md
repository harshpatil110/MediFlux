# MediFlux Developer Platform & API Guide

Welcome to the **MediFlux Developer Platform**. This guide provides comprehensive documentation for third-party developers, hospital information systems (HIS), pharmacy counter POS software, logistics telematics providers, and enterprise ERP integrations.

---

## 1. Authentication & Security Architecture

MediFlux supports two primary authentication modes:

| Authentication Mode | Header Format | Use Case | Lifecycle |
|---|---|---|---|
| **User JWT** | `Authorization: Bearer <token>` | Human operators (pharmacists, stockists, auditors, regulators) accessing web interfaces | Decoded using Supabase JWT secret |
| **Developer API Key** | `X-API-Key: mfx_live_<24-char-token>` | Automated background systems, third-party ERPs, IoT sensor hubs, and counter POS terminals | Provisioned once, hashed with SHA-256 at rest |

### 1.1 SHA-256 Key Hashing Standard
When an API key is provisioned via `POST /api/v1/developer/keys`:
1. The server generates a cryptographically random plaintext string (`f"mfx_live_{secrets.token_urlsafe(24)}"`).
2. The server computes the 64-character hexadecimal SHA-256 hash:
   $$\text{KeyHash} = \text{SHA-256}(\text{RawKey})$$
3. The server persists **ONLY** `key_hash` and `key_prefix` (the first 12 characters, e.g. `mfx_live_a1b2`) in `public.api_keys`.
4. **The plaintext key is returned ONCE AND ONLY ONCE** in the creation response (`key` / `api_key`). It is never logged, stored, or queryable again.

---

## 2. Developer Scopes & Row-Level Security (RLS) Binding

### 2.1 Canonical Developer Scopes

| Scope | Description | Associated Endpoints |
|---|---|---|
| `read:inventory` | Read inventory balances, batch quantities, and shelf safety stocks | `GET /api/v1/inventory`, `GET /api/v1/nodes/{id}/inventory` |
| `write:events` | Ingest retail POS sales, sensor readings, and canonical domain events | `POST /api/v1/events`, `POST /api/v1/events/sale`, `POST /api/v1/events/sensor` |
| `read:stream` | Subscribe to live domain event topics over Server-Sent Events (SSE) | `GET /api/v1/stream`, `GET /api/v1/events/stream` |
| `read:audit` | Query cryptographically verified audit ledger entries and compliance logs | `GET /api/v1/audit`, `GET /api/v1/audit/ledger`, `GET /api/v1/compliance/logs` |
| `use:copilot` | Natural-language supply chain questions & semantic vector search | `POST /api/v1/copilot/query`, `GET /api/v1/search` |
| `manage:adapters` | Synthesize, inspect, and execute Adapter Forge translators | `POST /api/v1/adapters/generate`, `GET /api/v1/adapters`, `POST /api/v1/ingest/{id}` |
| `*` or `all` | Full administrative access to all developer platform capabilities | All endpoints |

### 2.2 Node RLS Scope Binding
API keys can be bound to a specific `node_id` (e.g. Pharmacy Node `11111111-1111-1111-1111-111111111111`).
When authenticated via a node-bound key:
- Inventory queries (`GET /api/v1/inventory`) automatically filter rows where `node_id == key.node_id`.
- Network Copilot queries (`POST /api/v1/copilot/query`) enforce sovereign RLS isolation: data from peer pharmacies is strictly excluded.

---

## 3. Rate Limiting & Architecture Note

MediFlux employs a per-key **Token-Bucket Rate Limiter**:
- **Bucket Capacity ($C$):** Configurable per key (default 100 requests).
- **Refill Rate ($R$):**
  $$R = \frac{C}{60.0} \quad \text{(tokens per second)}$$

### Rate Limit Response (`429 Too Many Requests`)
When bucket tokens are exhausted ($< 1.0$), requests are rejected immediately with HTTP 429:

```http
HTTP/1.1 429 Too Many Requests
Content-Type: application/json
Retry-After: 12
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 0

{
  "detail": "Rate limit exceeded for API key"
}
```

> [!NOTE]
> **Architectural Note (Redis Deferred):**
> In strict accordance with the MediFlux MVP rules (`AGENTS.md`), Redis is deferred.
> Rate limiting is maintained in-process per application instance using thread/async-safe memory structures.
> In multi-worker production clusters, this module can be swapped to a distributed Redis Lua token bucket with zero database schema or API contract changes.

---

## 4. Event Ingestion & Server-Sent Events (SSE)

### 4.1 Ingesting a POS Sale Event
```bash
curl -X POST "http://localhost:8000/api/v1/events/sale" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: mfx_live_your_api_key_here" \
  -d '{
    "pharmacy_id": "11111111-1111-1111-1111-111111111111",
    "product_id": "p-001-azithromycin",
    "batch_id": "b-azi-2026-01",
    "quantity": 1,
    "source": "counter-pos-terminal-1"
  }'
```

### 4.2 Subscribing to Real-Time SSE Streams
```bash
curl -N "http://localhost:8000/api/v1/stream?topics=pos.sales,agent.activity" \
  -H "X-API-Key: mfx_live_your_api_key_here" \
  -H "Accept: text/event-stream"
```

---

## 5. Outbound Webhooks & HMAC-SHA256 Verification

MediFlux can deliver signed real-time HTTP callbacks to third-party endpoints.

### 5.1 Supported Event Types
- `order.created` (Retail sale or replenishment order generated)
- `shipment.dispatched` (Transit agent dispatched multi-unit transfer)
- `batch.quarantined` (Cold-chain temperature/shock excursion detected)
- `hitl.created` (Human-in-the-loop task requires operator review)
- `hitl.decided` (Operator approved/rejected a pending task)
- `module.activated` (Zero-downtime hot-swap module activated)
- `*` (All events)

### 5.2 Delivery Payload Envelope
```json
{
  "delivery_id": "8c59c5d0-4e3f-42e8-963d-4c387f34f0aa",
  "event_id": "e-pos-001",
  "event_type": "batch.quarantined",
  "timestamp": "2026-11-13T12:00:00.000000Z",
  "node_id": "22222222-2222-2222-2222-222222222222",
  "data": {
    "batch_id": "BIO-INS-01",
    "temperature_c": 14.5,
    "threshold_max_c": 8.0,
    "reason": "Cold-chain breach exceeding safe MKT threshold"
  }
}
```

### 5.3 HMAC-SHA256 Signature Verification

Every delivery includes:
- `X-MediFlux-Signature: sha256={hex_digest}`
- `X-MediFlux-Event: {event_type}`
- `X-MediFlux-Delivery: {delivery_id}`

#### Python Verification Example:
```python
import hashlib
import hmac

def verify_mediflux_webhook(raw_body: bytes, secret: str, signature_header: str) -> bool:
    expected_digest = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    provided = signature_header.strip()
    if provided.startswith("sha256="):
        provided = provided[7:]
    return hmac.compare_digest(expected_digest, provided)
```

#### Node.js Verification Example:
```javascript
const crypto = require("crypto");

function verifyMediFluxWebhook(rawBodyBuffer, secret, signatureHeader) {
  const hmac = crypto.createHmac("sha256", secret);
  hmac.update(rawBodyBuffer);
  const expectedDigest = hmac.digest("hex");
  const provided = signatureHeader.replace(/^sha256=/, "").trim();
  return crypto.timingSafeEqual(Buffer.from(expectedDigest), Buffer.from(provided));
}
```

### 5.4 Exponential Backoff & Auto-Disable
1. **Retries:** Failed deliveries (HTTP status $\ge 400$ or network timeout) retry up to **3 attempts** using exponential backoff:
   $$\text{Delay} = \text{BaseDelay} \times 2^{\text{attempt} - 1}$$
2. **Delivery Log:** Every attempt is logged in `public.webhook_deliveries`.
3. **Auto-Disable:** If a subscription fails 3 consecutive delivery attempts across events, it is automatically marked `is_active = False` to protect downstream endpoints from degradation.

---

## 6. Standard Error Reference

| Status Code | Error Code / Detail | Cause & Remedy |
|---|---|---|
| `400 Bad Request` | `Malformed JSON or invalid parameters` | Request body syntax or query parameter is invalid. |
| `401 Unauthorized` | `Invalid or inactive API key` | Missing, incorrect, or revoked `X-API-Key`. |
| `403 Forbidden` | `Insufficient API key scope. Required: 'write:events'` | API key does not include the permission required for this endpoint. |
| `404 Not Found` | `Entity not found` | Targeted resource ID does not exist. |
| `409 Conflict` | `Duplicate record or idempotency conflict` | The request has already been processed. |
| `422 Unprocessable` | `Validation error` | Pydantic schema validation failure (e.g. quantity must be $> 0$). |
| `429 Too Many Requests` | `Rate limit exceeded for API key` | Request burst exceeded token-bucket capacity. Wait for `Retry-After` seconds. |
| `500 Server Error` | `Internal server error` | Unexpected server condition. Correlation ID is logged in response headers. |
