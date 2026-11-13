# MediFlux Model Context Protocol (MCP) Server Guide

The **MediFlux MCP Server** exposes pharmaceutical supply chain intelligence, stock visibility, autonomous demand cascade tracing, and HITL approval management to external AI agents and IDE clients through the official **Model Context Protocol (MCP)** specification.

Supported clients include **Claude Desktop**, **Cursor IDE**, **Antigravity IDE**, and custom Python/TypeScript agents.

---

## 1. Security Architecture & Threat Model

Every tool execution across both stdio and HTTP/SSE transports is strictly governed by the MediFlux Zero-Trust Developer Security Model:

```
[ External AI Agent / IDE ]
           │
           │ (stdio JSON-RPC OR HTTP POST /api/v1/mcp/call / SSE)
           ▼
┌────────────────────────────────────────────────────────┐
│ MediFlux Unified MCP Security & Audit Wrapper          │
│                                                        │
│ 1. API Key Resolution (argument / header / env var)   │
│ 2. SHA-256 Key Hash Lookup (at rest in public.api_keys)│
│ 3. In-Memory TokenBucketRateLimiter (burst + refill)   │
│ 4. Granular Scope Verification (read:*, write:*, etc.) │
│ 5. Node-Level RLS Boundary Enforcement (node_id pin)   │
│ 6. Cryptographic Monotonic Audit Ledger (SHA-256 chain)│
└────────────────────────────────────────────────────────┘
           │
           ▼
[ Domain Services: Inventory, Copilot, HITL, Cascade, POS ]
```

### Key Security Guarantees:
1. **API Keys Stored as Hashes**: Plaintext API keys (`mfx_live_...`) are generated once and stored exclusively as SHA-256 digests (`key_hash`). Plaintext keys are never stored, logged, or returned on retrieval.
2. **Node-Level RLS Scoping**: If an API key is bound to a specific pharmacy node ID (`node_id`), `get_inventory` strictly restricts results to that node, and `submit_sale_event` rejects attempts to submit sales for any other node with `403 Forbidden`.
3. **In-Memory Token-Bucket Rate Limiter**: Evaluates burst allowances and continuously refills at $\frac{\text{capacity}}{60.0}$ tokens/sec. Exhausted buckets receive HTTP `429 Too Many Requests` with a compliant `Retry-After` header.
4. **Tamper-Evident Cryptographic Auditing**: Every call (whether executed or rejected due to missing auth, rate limits, scope insufficiency, or node boundary violations) is permanently appended to `public.audit_ledger` with deterministic hash chaining:
   - `mcp.tool.unauthorized` (status: `rejected`, reason: `invalid_or_missing_api_key`)
   - `mcp.tool.rate_limited` (status: `rejected`, reason: `rate_limit_exceeded`)
   - `mcp.tool.forbidden` (status: `rejected`, reason: `insufficient_scope` or `node_mismatch`)
   - `mcp.tool.executed` (status: `succeeded`)

---

## 2. Tools Reference & Required Scopes

| Tool Name | Category | Primary Scope | Accepted Scopes | Description |
| :--- | :--- | :--- | :--- | :--- |
| `get_inventory` | Read | `read:inventory` | `read:inventory`, `*` | Real-time stock balances, safety thresholds, and reservations scoped to node RLS. |
| `get_stockout_risk` | Read | `read:inventory` | `read:inventory`, `use:copilot`, `*` | Predictive stockout risk assessment comparing current balances against safety margins. |
| `list_open_approvals` | Read | `read:audit` | `read:audit`, `read:hitl`, `manage:hitl`, `*` | Open Human-in-the-Loop approval tasks requiring operator intervention. |
| `get_cascade_trace` | Read | `read:audit` | `read:audit`, `read:stream`, `*` | Chronological multi-tier demand cascade execution steps for a correlation ID. |
| `ask_copilot` | Read | `use:copilot` | `use:copilot`, `*` | Query the conversational Network Copilot LangGraph graph with grounded citations. |
| `submit_sale_event` | Action | `write:events` | `write:events`, `*` | Atomic point-of-sale dispense ingestion, inventory deduction, and cascade propagation. |
| `decide_approval` | Action | `decide:approvals` | `decide:approvals`, `manage:hitl`, `*` | Submit human operator decision (approve/reject) for a pending HITL task. |

---

## 3. Connecting MCP Clients

### A. Claude Desktop Configuration (`claude_desktop_config.json`)

On Windows, open `%APPDATA%\Claude\claude_desktop_config.json` (or `~/.config/Claude/claude_desktop_config.json` on macOS/Linux):

```json
{
  "mcpServers": {
    "mediflux": {
      "command": "python",
      "args": [
        "-m",
        "app.mcp.server"
      ],
      "cwd": "C:\\Users\\harsh\\Desktop\\Coding\\MediFlux\\backend",
      "env": {
        "MEDIFLUX_API_KEY": "mfx_live_your_actual_api_key_here"
      }
    }
  }
}
```

Or using the root convenience entrypoint:

```json
{
  "mcpServers": {
    "mediflux": {
      "command": "python",
      "args": [
        "mcp_server.py"
      ],
      "cwd": "C:\\Users\\harsh\\Desktop\\Coding\\MediFlux",
      "env": {
        "MEDIFLUX_API_KEY": "mfx_live_your_actual_api_key_here"
      }
    }
  }
}
```

### B. Cursor IDE Configuration (`.cursor/mcp.json`)

Add the following to your project or user `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "mediflux": {
      "command": "python",
      "args": ["-m", "app.mcp.server"],
      "cwd": "${workspaceFolder}/backend",
      "env": {
        "MEDIFLUX_API_KEY": "mfx_live_your_actual_api_key_here"
      }
    }
  }
}
```

### C. Antigravity IDE Configuration (`antigravity.mcp.json`)

```json
{
  "mcpServers": {
    "mediflux": {
      "command": "python",
      "args": ["-m", "app.mcp.server"],
      "cwd": "${workspaceFolder}/backend",
      "env": {
        "MEDIFLUX_API_KEY": "mfx_live_your_actual_api_key_here"
      }
    }
  }
}
```

### D. Connecting over HTTP / SSE Transport

When MediFlux backend is running (`uvicorn app.main:app --port 8000`):

1. **SSE Session Initialization**:
   ```
   GET /api/v1/mcp/sse
   ```
2. **Tool Execution over HTTP REST**:
   ```bash
   curl -X POST http://localhost:8000/api/v1/mcp/call \
     -H "Content-Type: application/json" \
     -H "X-API-Key: mfx_live_your_actual_api_key_here" \
     -d '{
       "name": "get_inventory",
       "arguments": {
         "product": "azithromycin",
         "limit": 10
       }
     }'
   ```
3. **Tool Execution over JSON-RPC 2.0**:
   ```bash
   curl -X POST http://localhost:8000/api/v1/mcp/rpc \
     -H "Content-Type: application/json" \
     -H "X-API-Key: mfx_live_your_actual_api_key_here" \
     -d '{
       "jsonrpc": "2.0",
       "id": 1,
       "method": "tools/call",
       "params": {
         "name": "get_inventory",
         "arguments": {"limit": 5}
       }
     }'
   ```

---

## 4. Python Client Integration Example

```python
import asyncio
import httpx
from mcp.server.mcpserver import MCPServer

async def main():
    api_key = "mfx_live_your_key_here"
    base_url = "http://localhost:8000/api/v1/mcp"

    async with httpx.AsyncClient(headers={"X-API-Key": api_key}) as client:
        # 1. Discover registered tools
        tools_resp = await client.get(f"{base_url}/tools")
        print("Available MCP Tools:", [t["name"] for t in tools_resp.json()["tools"]])

        # 2. Query scoped inventory
        inv_resp = await client.post(
            f"{base_url}/call",
            json={
                "name": "get_inventory",
                "arguments": {"product": "azithromycin", "limit": 5}
            }
        )
        print("Inventory Result:", inv_resp.json()["structured_content"])

if __name__ == "__main__":
    asyncio.run(main())
```
