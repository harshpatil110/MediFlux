"""Model Context Protocol (MCP) Server for MediFlux / NexusChain.

Exposes pharmaceutical supply chain inspection, monitoring, and transactional tools
to external AI agents (Claude Desktop, Cursor, Antigravity IDE, custom agents)
governed by scoped SHA-256 API keys, in-memory token-bucket rate limiting,
node-level RLS boundary enforcement, and cryptographic audit ledger logging.
"""

import json
import logging
import os
import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from mcp.server.mcpserver import MCPServer
from mcp.types import CallToolResult, TextContent

from app.core.audit_ledger import write_audit_entry
from app.core.config import settings
from app.core.security import get_service_db_client
from app.services.api_keys import (
    get_api_key_by_hash,
    hash_api_key,
    rate_limiter,
    record_key_usage,
)

logger = logging.getLogger("mediflux.mcp.server")

# Backwards compatibility alias for MCP 1.x FastMCP users
FastMCP = MCPServer

# Initialize the official MCP Server instance
mcp_server = MCPServer(
    name="mediflux-mcp",
    version="1.0.0",
    instructions=(
        "MediFlux AI-Native Pharmaceutical Supply Chain MCP Server. "
        "Allows authorized AI agents to inspect stock, observe demand cascades, "
        "query the network copilot, ingest retail sales, and review HITL approval tasks."
    ),
)


# ---------------------------------------------------------------------------
# Domain Exceptions
# ---------------------------------------------------------------------------

class MCPError(Exception):
    """Base exception for MCP operations."""

    def __init__(
        self,
        message: str,
        status_code: int = 500,
        code: str = "mcp_error",
        detail: Any = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code
        self.detail = detail or message


class MCPAuthError(MCPError):
    """Unauthorized: invalid or missing API key."""

    def __init__(self, message: str = "Missing or invalid API key", detail: Any = None) -> None:
        super().__init__(message, status_code=401, code="unauthorized", detail=detail)


class MCPRateLimitError(MCPError):
    """Too Many Requests: Token bucket exhausted."""

    def __init__(self, message: str = "Rate limit exceeded", retry_after: int = 60, detail: Any = None) -> None:
        super().__init__(message, status_code=429, code="rate_limit_exceeded", detail=detail)
        self.retry_after = retry_after


class MCPScopeError(MCPError):
    """Forbidden: caller key lacks required scope."""

    def __init__(self, message: str = "Insufficient API key scope for tool call", detail: Any = None) -> None:
        super().__init__(message, status_code=403, code="insufficient_scope", detail=detail)


class MCPPermissionError(MCPError):
    """Forbidden: node RLS boundary or role permission violation."""

    def __init__(self, message: str = "Permission denied", detail: Any = None) -> None:
        super().__init__(message, status_code=403, code="permission_denied", detail=detail)


class MCPExecutionError(MCPError):
    """Execution error within the underlying tool domain logic."""

    def __init__(self, message: str, status_code: int = 400, code: str = "execution_error", detail: Any = None) -> None:
        super().__init__(message, status_code=status_code, code=code, detail=detail)


# ---------------------------------------------------------------------------
# MCP Tools Metadata Specification
# ---------------------------------------------------------------------------

MCP_TOOLS_METADATA: dict[str, dict[str, Any]] = {
    "get_inventory": {
        "name": "get_inventory",
        "description": (
            "Retrieve current inventory balances, safety stocks, and reservations scoped to node RLS. "
            "A pharmacy-bound key can ONLY read its own node inventory."
        ),
        "primary_scope": "read:inventory",
        "required_scopes": ["read:inventory"],
        "category": "read",
        "input_schema": {
            "type": "object",
            "properties": {
                "api_key": {"type": "string", "description": "Optional explicit MediFlux API key."},
                "node_id": {"type": "string", "description": "Optional node ID filter (ignored if key is node-bound)."},
                "product": {"type": "string", "description": "Optional product name or ID filter."},
                "region": {"type": "string", "description": "Optional geographical region filter."},
                "limit": {"type": "integer", "default": 50, "description": "Maximum number of records to return."},
            },
        },
    },
    "get_stockout_risk": {
        "name": "get_stockout_risk",
        "description": (
            "Analyze network or regional inventory to identify pharmacy nodes at immediate risk of stockout "
            "by comparing available stock against safety thresholds."
        ),
        "primary_scope": "read:inventory",
        "required_scopes": ["read:inventory", "use:copilot"],
        "category": "read",
        "input_schema": {
            "type": "object",
            "properties": {
                "api_key": {"type": "string", "description": "Optional explicit MediFlux API key."},
                "product": {"type": "string", "description": "Optional product name or ID to assess."},
                "region": {"type": "string", "description": "Optional regional filter."},
            },
        },
    },
    "list_open_approvals": {
        "name": "list_open_approvals",
        "description": (
            "List open Human-in-the-Loop (HITL) approval tasks requiring human operator intervention, "
            "scoped to the caller's node RLS boundary."
        ),
        "primary_scope": "read:audit",
        "required_scopes": ["read:audit", "read:hitl", "manage:hitl"],
        "category": "read",
        "input_schema": {
            "type": "object",
            "properties": {
                "api_key": {"type": "string", "description": "Optional explicit MediFlux API key."},
                "status": {"type": "string", "default": "pending", "description": "Task status (pending, approved, rejected, all)."},
                "task_type": {"type": "string", "description": "Optional filter by task type."},
                "limit": {"type": "integer", "default": 25, "description": "Maximum tasks to return."},
            },
        },
    },
    "get_cascade_trace": {
        "name": "get_cascade_trace",
        "description": (
            "Retrieve the end-to-end multi-tier demand cascade execution trace for a correlation ID "
            "across agent runs, events, and audit ledgers."
        ),
        "primary_scope": "read:audit",
        "required_scopes": ["read:audit", "read:stream"],
        "category": "read",
        "input_schema": {
            "type": "object",
            "required": ["correlation_id"],
            "properties": {
                "api_key": {"type": "string", "description": "Optional explicit MediFlux API key."},
                "correlation_id": {"type": "string", "description": "Demand cascade correlation ID to trace."},
            },
        },
    },
    "ask_copilot": {
        "name": "ask_copilot",
        "description": (
            "Query the MediFlux Network Copilot AI agent with grounded supply chain citations, "
            "scoped to the caller's node RLS context."
        ),
        "primary_scope": "use:copilot",
        "required_scopes": ["use:copilot"],
        "category": "read",
        "input_schema": {
            "type": "object",
            "required": ["question"],
            "properties": {
                "api_key": {"type": "string", "description": "Optional explicit MediFlux API key."},
                "question": {"type": "string", "description": "Natural language question for the supply chain copilot."},
                "region": {"type": "string", "description": "Optional geographical focus region."},
            },
        },
    },
    "submit_sale_event": {
        "name": "submit_sale_event",
        "description": (
            "Ingest a retail point-of-sale dispense event, deduct inventory atomically, "
            "and trigger the multi-tier demand cascade. Strictly pinned to the caller's node_id."
        ),
        "primary_scope": "write:events",
        "required_scopes": ["write:events"],
        "category": "action",
        "input_schema": {
            "type": "object",
            "properties": {
                "api_key": {"type": "string", "description": "Optional explicit MediFlux API key."},
                "product_id": {"type": "string", "description": "Master SKU product ID (e.g. p-001-azithromycin)."},
                "sku": {"type": "string", "description": "Product SKU alternative."},
                "quantity": {"type": "integer", "default": 1, "description": "Number of units dispensed."},
                "node_id": {"type": "string", "description": "Pharmacy node ID (must match key node_id if bound)."},
                "prescription_id": {"type": "string", "description": "Prescription ID for Schedule H compliance."},
                "unit_price": {"type": "number", "description": "Retail price per unit in INR."},
                "correlation_id": {"type": "string", "description": "Optional tracking correlation ID."},
            },
        },
    },
    "decide_approval": {
        "name": "decide_approval",
        "description": (
            "Submit an operator decision (approved or rejected) for a pending HITL task with cryptographic audit logging. "
            "Requires high-privilege decide:approvals or manage:hitl scope."
        ),
        "primary_scope": "decide:approvals",
        "required_scopes": ["decide:approvals", "manage:hitl"],
        "category": "action",
        "input_schema": {
            "type": "object",
            "required": ["task_id", "decision"],
            "properties": {
                "api_key": {"type": "string", "description": "Optional explicit MediFlux API key."},
                "task_id": {"type": "string", "description": "HITL task ID to decide."},
                "decision": {
                    "type": "string",
                    "enum": ["approved", "rejected", "approve", "reject"],
                    "description": "Decision outcome.",
                },
                "decision_note": {"type": "string", "description": "Operator rationale or decision explanation."},
            },
        },
    },
}


def get_mcp_tools_metadata() -> list[dict[str, Any]]:
    """Return all registered MCP tools with schema and scope metadata."""
    return list(MCP_TOOLS_METADATA.values())


# ---------------------------------------------------------------------------
# Unified Security, Scope & Cryptographic Audit Verification
# ---------------------------------------------------------------------------

async def authenticate_and_authorize(
    tool_name: str,
    arguments: dict[str, Any],
    context_api_key: str | None = None,
) -> tuple[dict[str, Any], str]:
    """Authenticate API key, check rate limit, verify scopes, enforce RLS, and log rejections."""
    # 1. Resolve raw API key
    raw_key = (
        arguments.get("api_key")
        or context_api_key
        or os.environ.get("MEDIFLUX_API_KEY")
    )

    if not raw_key or not isinstance(raw_key, str) or not raw_key.strip():
        await write_audit_entry(
            actor="anonymous",
            action="mcp.tool.unauthorized",
            entity_type="mcp_tool",
            entity_id=tool_name,
            payload={
                "tool": tool_name,
                "status": "rejected",
                "reason": "invalid_or_missing_api_key",
            },
            explanation="MCP tool call rejected: missing API key",
        )
        raise MCPAuthError(
            "API key required. Pass api_key argument, X-API-Key header, or MEDIFLUX_API_KEY env var."
        )

    raw_key = raw_key.strip()
    if raw_key.startswith("Bearer "):
        raw_key = raw_key[7:].strip()

    # 2. SHA-256 Key Lookup
    key_hash = hash_api_key(raw_key)
    key_rec = get_api_key_by_hash(key_hash)
    if not key_rec or not key_rec.get("is_active", True):
        await write_audit_entry(
            actor="anonymous",
            action="mcp.tool.unauthorized",
            entity_type="mcp_tool",
            entity_id=tool_name,
            payload={
                "tool": tool_name,
                "status": "rejected",
                "reason": "invalid_or_missing_api_key",
            },
            explanation="MCP tool call rejected: invalid or revoked API key",
        )
        raise MCPAuthError("Invalid or inactive API key.")

    key_id = str(key_rec.get("id"))
    node_id = key_rec.get("node_id")

    # 3. Token-Bucket Rate Limiter
    rate_limit_val = int(key_rec.get("rate_limit", 100))
    allowed, retry_after, remaining, capacity = rate_limiter.check_and_consume(
        key_id, rate_limit_val
    )
    if not allowed:
        await write_audit_entry(
            actor=key_id,
            action="mcp.tool.rate_limited",
            entity_type="mcp_tool",
            entity_id=tool_name,
            payload={
                "tool": tool_name,
                "status": "rejected",
                "reason": "rate_limit_exceeded",
                "retry_after": retry_after,
                "node_id": node_id,
            },
            explanation=f"MCP tool call rejected: rate limit exceeded ({retry_after}s retry-after)",
        )
        raise MCPRateLimitError(
            f"Rate limit exceeded. Retry after {retry_after} seconds.",
            retry_after=retry_after,
        )

    # 4. Scope Verification
    tool_meta = MCP_TOOLS_METADATA.get(tool_name, {})
    accepted_scopes = tool_meta.get("required_scopes", [])
    primary_scope = tool_meta.get("primary_scope", accepted_scopes[0] if accepted_scopes else "*")
    key_scopes = key_rec.get("scopes", [])

    has_scope = (
        "*" in key_scopes
        or "all" in key_scopes
        or any(s in key_scopes for s in accepted_scopes)
    )

    if not has_scope:
        await write_audit_entry(
            actor=key_id,
            action="mcp.tool.forbidden",
            entity_type="mcp_tool",
            entity_id=tool_name,
            payload={
                "tool": tool_name,
                "required_scope": primary_scope,
                "accepted_scopes": accepted_scopes,
                "key_scopes": key_scopes,
                "status": "rejected",
                "reason": "insufficient_scope",
                "node_id": node_id,
            },
            explanation=f"MCP tool call forbidden: key lacks required scope '{primary_scope}'",
        )
        raise MCPScopeError(
            f"Insufficient API key scope for tool '{tool_name}'. Required: '{primary_scope}', key has: {key_scopes}"
        )

    # 5. Node RLS Enforcement for Action Tools
    if tool_name == "submit_sale_event" and node_id:
        req_node = arguments.get("node_id")
        if req_node and req_node != node_id:
            await write_audit_entry(
                actor=key_id,
                action="mcp.tool.forbidden",
                entity_type="mcp_tool",
                entity_id=tool_name,
                payload={
                    "tool": tool_name,
                    "status": "rejected",
                    "reason": "node_mismatch",
                    "node_id": node_id,
                    "attempted_node_id": req_node,
                },
                explanation="MCP tool call forbidden: cross-node sale boundary violation",
            )
            raise MCPPermissionError(
                f"API key is bound to node '{node_id}'. Cannot submit sale for node '{req_node}'."
            )

    return key_rec, raw_key


# ---------------------------------------------------------------------------
# Individual Domain Tool Handlers
# ---------------------------------------------------------------------------

async def _handle_get_inventory(
    key_rec: dict[str, Any], arguments: dict[str, Any]
) -> dict[str, Any]:
    """Retrieve inventory records scoped to node RLS."""
    bound_node = key_rec.get("node_id")
    effective_node = bound_node or arguments.get("node_id")
    limit = max(1, min(int(arguments.get("limit", 50)), 200))
    prod_filter = arguments.get("product")

    items: list[dict[str, Any]] = []

    # 1. Supabase database lookup if configured
    if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY:
        try:
            client = get_service_db_client()
            if client:
                query = client.table("inventory").select("*, products(name), batches(batch_no)")
                if effective_node:
                    query = query.eq("node_id", effective_node)
                res = query.limit(limit + 1).execute()
                for row in (res.data or []):
                    prod = row.get("products") or {}
                    batch = row.get("batches") or {}
                    items.append({
                        "id": row["id"],
                        "node_id": row["node_id"],
                        "product_id": row["product_id"],
                        "product_name": prod.get("name") or row.get("product_name", row["product_id"]),
                        "batch_id": row.get("batch_id"),
                        "batch_no": batch.get("batch_no") or row.get("batch_no"),
                        "quantity": int(row["quantity"]),
                        "reserved": int(row.get("reserved", 0)),
                        "safety_stock": int(row.get("safety_stock", 10)),
                    })
        except Exception as exc:
            logger.warning("Supabase inventory query failed in MCP tool: %s", exc)

    # 2. Local fallback if database is empty/offline
    if not items:
        from app.api.v1.endpoints.inventory import BASE_MOCK_INVENTORY, DEFAULT_INVENTORY

        pool = list(DEFAULT_INVENTORY)
        if not any(i.get("node_id") == "11111111-1111-1111-1111-111111111111" for i in pool):
            pool.extend(BASE_MOCK_INVENTORY)

        for inv in pool:
            if effective_node and inv.get("node_id") != effective_node:
                continue
            items.append({
                "id": inv["id"],
                "node_id": inv["node_id"],
                "product_id": inv["product_id"],
                "product_name": inv.get("product_name", inv["product_id"]),
                "batch_id": inv.get("batch_id"),
                "batch_no": inv.get("batch_no"),
                "quantity": int(inv["quantity"]),
                "reserved": int(inv.get("reserved", 0)),
                "safety_stock": int(inv.get("safety_stock", 10)),
            })

    # Apply product filtering
    if prod_filter:
        pf_lower = prod_filter.lower()
        items = [
            i for i in items
            if pf_lower in str(i.get("product_id", "")).lower()
            or pf_lower in str(i.get("product_name", "")).lower()
        ]

    items = items[:limit]
    total_qty = sum(i["quantity"] for i in items)
    total_res = sum(i["reserved"] for i in items)

    return {
        "node_id": effective_node,
        "count": len(items),
        "items": items,
        "summary": {
            "total_quantity": total_qty,
            "total_reserved": total_res,
            "available_stock": total_qty - total_res,
        },
    }


async def _handle_get_stockout_risk(
    key_rec: dict[str, Any], arguments: dict[str, Any]
) -> dict[str, Any]:
    """Identify nodes at risk of running out of stock."""
    from app.graphs.copilot import CopilotScope, get_stockout_risk

    scope = CopilotScope(
        node_id=key_rec.get("node_id"),
        role="pharmacy" if key_rec.get("node_id") else "admin",
        region=arguments.get("region"),
    )
    return await get_stockout_risk(
        product=arguments.get("product"),
        region=arguments.get("region"),
        scope=scope,
    )


async def _handle_list_open_approvals(
    key_rec: dict[str, Any], arguments: dict[str, Any]
) -> dict[str, Any]:
    """Retrieve open/pending HITL tasks requiring operator intervention."""
    from app.core.hitl import get_in_memory_hitl_tasks

    status_filter = arguments.get("status", "pending")
    task_type = arguments.get("task_type")
    limit = max(1, min(int(arguments.get("limit", 25)), 100))
    bound_node = key_rec.get("node_id")

    all_tasks = list(get_in_memory_hitl_tasks())

    if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY:
        try:
            client = get_service_db_client()
            if client:
                query = client.table("hitl_tasks").select("*")
                if status_filter and status_filter != "all":
                    query = query.eq("status", status_filter)
                if task_type:
                    query = query.eq("task_type", task_type)
                res = query.order("created_at", desc=True).limit(limit).execute()
                seen_ids = {t["id"] for t in all_tasks}
                for row in (res.data or []):
                    if row["id"] not in seen_ids:
                        all_tasks.append(row)
        except Exception as exc:
            logger.warning("Supabase hitl_tasks query failed in MCP tool: %s", exc)

    filtered: list[dict[str, Any]] = []
    for t in all_tasks:
        if status_filter and status_filter != "all" and t.get("status") != status_filter:
            continue
        if task_type and t.get("task_type") != task_type:
            continue
        if bound_node:
            t_node = t.get("node_id") or t.get("payload", {}).get("node_id")
            if t_node and t_node != bound_node:
                continue
        filtered.append(t)

    filtered = filtered[:limit]
    return {
        "tasks": filtered,
        "count": len(filtered),
        "status": status_filter,
    }


async def _handle_get_cascade_trace(
    key_rec: dict[str, Any], arguments: dict[str, Any]
) -> dict[str, Any]:
    """Retrieve multi-tier demand cascade execution trace for correlation ID."""
    from app.agents.base import get_in_memory_agent_runs
    from app.graphs.cascade import get_in_memory_cascade_trace

    cid = arguments.get("correlation_id")
    if not cid:
        raise MCPExecutionError("Parameter 'correlation_id' is required.")

    # 1. In-memory cascade trace
    trace_rec = get_in_memory_cascade_trace(cid)
    if trace_rec:
        return trace_rec

    # 2. In-memory agent runs
    agent_runs = [r for r in get_in_memory_agent_runs() if r.get("correlation_id") == cid]
    if agent_runs:
        steps = [
            {
                "tier": r.get("agent_name", "").replace("_agent", ""),
                "agent_name": r.get("agent_name", ""),
                "status": r.get("status", "success"),
                "summary": f"{r.get('agent_name', '')} processed demand",
                "latency_ms": float(r.get("duration_ms", 0.0)),
                "created_at": r.get("created_at", ""),
            }
            for r in agent_runs
        ]
        return {
            "correlation_id": cid,
            "status": "completed",
            "steps": steps,
        }

    # 3. Database agent runs
    if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY:
        try:
            client = get_service_db_client()
            if client:
                res = (
                    client.table("agent_runs")
                    .select("*")
                    .eq("correlation_id", cid)
                    .order("created_at")
                    .execute()
                )
                if res.data:
                    steps = [
                        {
                            "tier": r.get("agent_name", "").replace("_agent", ""),
                            "agent_name": r.get("agent_name", ""),
                            "status": r.get("status", "success"),
                            "summary": f"{r.get('agent_name', '')} completed",
                            "latency_ms": float(r.get("duration_ms", 0.0)),
                            "created_at": r.get("created_at", ""),
                        }
                        for r in res.data
                    ]
                    return {
                        "correlation_id": cid,
                        "status": "completed",
                        "steps": steps,
                    }
        except Exception as exc:
            logger.warning("Supabase agent_runs query failed in MCP tool: %s", exc)

    return {
        "correlation_id": cid,
        "status": "not_found",
        "steps": [],
        "message": f"No cascade trace recorded for correlation ID: {cid}",
    }


async def _handle_ask_copilot(
    key_rec: dict[str, Any], arguments: dict[str, Any]
) -> dict[str, Any]:
    """Invoke the Network Copilot LangGraph graph."""
    from app.graphs.copilot import CopilotScope, run_copilot

    question = arguments.get("question")
    if not question:
        raise MCPExecutionError("Parameter 'question' is required.")

    scope = CopilotScope(
        node_id=key_rec.get("node_id"),
        role="pharmacy" if key_rec.get("node_id") else "admin",
        region=arguments.get("region"),
    )

    result = await run_copilot(question=question, scope=scope)
    return {
        "answer": result.get("answer", ""),
        "references": result.get("references", []),
        "tools_used": result.get("tools_used", []),
        "trace_id": result.get("trace_id", ""),
    }


async def _handle_submit_sale_event(
    key_rec: dict[str, Any], arguments: dict[str, Any]
) -> dict[str, Any]:
    """Ingest a retail POS sale event and trigger the cascade."""
    from app.events.bus import in_process_event_bus
    from app.events.models import EventEnvelope, SaleEvent
    from app.events.service import apply_sale

    bound_node = key_rec.get("node_id")
    effective_node = bound_node or arguments.get("node_id") or "11111111-1111-1111-1111-111111111111"

    product_id = arguments.get("product_id") or arguments.get("sku") or "p-001-azithromycin"
    batch_id = "b-azi-2026-01" if "azi" in product_id.lower() else "b-ins-2026-01"
    quantity = max(1, int(arguments.get("quantity", 1)))
    cid = arguments.get("correlation_id") or str(uuid.uuid4())
    event_id = str(uuid.uuid4())
    now_iso = datetime.now(UTC).isoformat()

    event = SaleEvent(
        event_id=event_id,
        pharmacy_id=str(effective_node),
        product_id=str(product_id),
        batch_id=str(batch_id),
        quantity=quantity,
        timestamp=now_iso,
        source="mcp",
    )

    # 1. Apply atomic sale deduction
    apply_res = await apply_sale(event=event, correlation_id=cid)

    # 2. Publish to event bus
    envelope = EventEnvelope(
        event_id=str(event_id),
        type="pos.sales",
        node_id=str(effective_node),
        correlation_id=cid,
        timestamp=now_iso,
        payload={
            "pharmacy_id": str(effective_node),
            "product_id": str(product_id),
            "batch_id": str(batch_id),
            "quantity": quantity,
            "prescription_id": arguments.get("prescription_id"),
            "unit_price": arguments.get("unit_price"),
        },
    )
    await in_process_event_bus.publish(envelope)

    return {
        "event_id": str(event_id),
        "correlation_id": cid,
        "pharmacy_id": str(effective_node),
        "product_id": product_id,
        "batch_id": batch_id,
        "quantity": quantity,
        "applied": apply_res.get("applied", True),
        "updated_inventory": apply_res.get("new_quantity"),
    }


async def _handle_decide_approval(
    key_rec: dict[str, Any], arguments: dict[str, Any]
) -> dict[str, Any]:
    """Execute high-privilege HITL task approval or rejection."""
    from app.core.hitl import (
        get_hitl_task,
        record_hitl_decision,
        resolve_hitl_task,
        resume_graph_thread,
    )

    if not getattr(settings, "MCP_ALLOW_DECIDE_APPROVAL", True):
        raise MCPPermissionError("MCP decide_approval is disabled by system configuration.")

    task_id = arguments.get("task_id")
    if not task_id:
        raise MCPExecutionError("Parameter 'task_id' is required.")

    decision_raw = str(arguments.get("decision", "approved")).strip().lower()
    if decision_raw in ("approve", "approved"):
        decision_norm = "approve"
        dec_status = "approved"
    elif decision_raw in ("reject", "rejected"):
        decision_norm = "reject"
        dec_status = "rejected"
    else:
        raise MCPExecutionError(
            f"Invalid decision '{decision_raw}'. Expected 'approved' or 'rejected'."
        )

    note = arguments.get("decision_note") or f"Decided via MCP tool call by {key_rec.get('name', 'API Key')}"
    now_iso = datetime.now(UTC).isoformat()

    # Verify task existence if possible
    get_hitl_task(task_id)

    # Update in-memory HITL state
    resolve_hitl_task(task_id=task_id, status=dec_status, decision_reason=note)
    record_hitl_decision(
        task_id=task_id,
        decision_payload={
            "task_id": task_id,
            "status": dec_status,
            "decision": decision_norm,
            "decided_by": key_rec["id"],
            "decision_note": note,
            "decided_at": now_iso,
        },
    )

    # Update Supabase if available
    if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY:
        try:
            client = get_service_db_client()
            if client:
                client.table("hitl_tasks").update({
                    "status": dec_status,
                    "decided_by": key_rec["id"],
                    "decided_at": now_iso,
                    "decision_note": note,
                }).eq("id", task_id).execute()
        except Exception as exc:
            logger.warning("Supabase HITL decision update failed in MCP tool: %s", exc)

    # Resume graph thread if registered
    await resume_graph_thread(
        thread_or_corr_id=task_id,
        resume_payload={"decision": decision_norm, "actor": key_rec["id"], "note": note},
    )

    return {
        "task_id": task_id,
        "decision": dec_status,
        "status": dec_status,
        "decided_by": key_rec["id"],
        "note": note,
        "decided_at": now_iso,
    }


# ---------------------------------------------------------------------------
# Master Tool Dispatcher & Cryptographic Audit Ledger Integration
# ---------------------------------------------------------------------------

async def execute_mcp_tool(
    tool_name: str,
    arguments: dict[str, Any] | None = None,
    context_api_key: str | None = None,
) -> dict[str, Any]:
    """Execute an MCP tool with authentication, rate limiting, scopes, and audit logging."""
    args = dict(arguments or {})

    if tool_name not in MCP_TOOLS_METADATA:
        raise MCPExecutionError(
            f"Unknown MCP tool '{tool_name}'. Available tools: {list(MCP_TOOLS_METADATA.keys())}",
            status_code=404,
            code="tool_not_found",
        )

    # 1. Authenticate & Authorize
    key_rec, raw_key = await authenticate_and_authorize(
        tool_name=tool_name,
        arguments=args,
        context_api_key=context_api_key,
    )

    # 2. Record API key usage telemetry
    record_key_usage(key_id=str(key_rec["id"]), key_hash=key_rec["key_hash"])

    # 3. Dispatch to domain handler
    handler_map = {
        "get_inventory": _handle_get_inventory,
        "get_stockout_risk": _handle_get_stockout_risk,
        "list_open_approvals": _handle_list_open_approvals,
        "get_cascade_trace": _handle_get_cascade_trace,
        "ask_copilot": _handle_ask_copilot,
        "submit_sale_event": _handle_submit_sale_event,
        "decide_approval": _handle_decide_approval,
    }

    handler = handler_map[tool_name]
    result = await handler(key_rec=key_rec, arguments=args)

    # 4. Write success entry to cryptographic audit ledger
    sanitized_args = {k: ("[REDACTED]" if k == "api_key" else v) for k, v in args.items()}
    await write_audit_entry(
        actor=str(key_rec["id"]),
        action="mcp.tool.executed",
        entity_type="mcp_tool",
        entity_id=tool_name,
        payload={
            "tool": tool_name,
            "arguments_sanitized": sanitized_args,
            "status": "succeeded",
            "node_id": key_rec.get("node_id"),
        },
        explanation=f"MCP tool '{tool_name}' executed successfully",
    )

    return result


# ---------------------------------------------------------------------------
# FastMCP / MCPServer Tool Registrations (stdio / SSE protocol runners)
# ---------------------------------------------------------------------------

def _build_mcp_result(result: dict[str, Any]) -> CallToolResult:
    """Helper to construct structured CallToolResult."""
    return CallToolResult(
        content=[TextContent(type="text", text=json.dumps(result, indent=2))],
        structured_content=result,
        is_error=False,
    )


def _build_mcp_error(err: Exception) -> CallToolResult:
    """Helper to construct error CallToolResult."""
    error_payload = {
        "error": str(err),
        "type": type(err).__name__,
        "is_error": True,
    }
    return CallToolResult(
        content=[TextContent(type="text", text=json.dumps(error_payload))],
        structured_content=error_payload,
        is_error=True,
    )


@mcp_server.tool()
async def get_inventory(
    api_key: str | None = None,
    node_id: str | None = None,
    product: str | None = None,
    region: str | None = None,
    limit: int = 50,
) -> CallToolResult:
    """Retrieve real-time inventory balances and safety stocks."""
    try:
        args = {"api_key": api_key, "node_id": node_id, "product": product, "region": region, "limit": limit}
        res = await execute_mcp_tool("get_inventory", args)
        return _build_mcp_result(res)
    except Exception as exc:
        return _build_mcp_error(exc)


@mcp_server.tool()
async def get_stockout_risk(
    api_key: str | None = None,
    product: str | None = None,
    region: str | None = None,
) -> CallToolResult:
    """Analyze network or regional inventory to identify pharmacy nodes at risk of stockout."""
    try:
        args = {"api_key": api_key, "product": product, "region": region}
        res = await execute_mcp_tool("get_stockout_risk", args)
        return _build_mcp_result(res)
    except Exception as exc:
        return _build_mcp_error(exc)


@mcp_server.tool()
async def list_open_approvals(
    api_key: str | None = None,
    status: str = "pending",
    task_type: str | None = None,
    limit: int = 25,
) -> CallToolResult:
    """List open Human-in-the-Loop (HITL) approval tasks."""
    try:
        args = {"api_key": api_key, "status": status, "task_type": task_type, "limit": limit}
        res = await execute_mcp_tool("list_open_approvals", args)
        return _build_mcp_result(res)
    except Exception as exc:
        return _build_mcp_error(exc)


@mcp_server.tool()
async def get_cascade_trace(
    correlation_id: str,
    api_key: str | None = None,
) -> CallToolResult:
    """Retrieve multi-tier demand cascade execution trace for a correlation ID."""
    try:
        args = {"api_key": api_key, "correlation_id": correlation_id}
        res = await execute_mcp_tool("get_cascade_trace", args)
        return _build_mcp_result(res)
    except Exception as exc:
        return _build_mcp_error(exc)


@mcp_server.tool()
async def ask_copilot(
    question: str,
    api_key: str | None = None,
    region: str | None = None,
) -> CallToolResult:
    """Query the MediFlux Network Copilot AI agent."""
    try:
        args = {"api_key": api_key, "question": question, "region": region}
        res = await execute_mcp_tool("ask_copilot", args)
        return _build_mcp_result(res)
    except Exception as exc:
        return _build_mcp_error(exc)


@mcp_server.tool()
async def submit_sale_event(
    api_key: str | None = None,
    product_id: str | None = None,
    sku: str | None = None,
    quantity: int = 1,
    node_id: str | None = None,
    prescription_id: str | None = None,
    unit_price: float | None = None,
    correlation_id: str | None = None,
) -> CallToolResult:
    """Ingest a retail point-of-sale dispense event, deduct inventory, and trigger cascade."""
    try:
        args = {
            "api_key": api_key,
            "product_id": product_id,
            "sku": sku,
            "quantity": quantity,
            "node_id": node_id,
            "prescription_id": prescription_id,
            "unit_price": unit_price,
            "correlation_id": correlation_id,
        }
        res = await execute_mcp_tool("submit_sale_event", args)
        return _build_mcp_result(res)
    except Exception as exc:
        return _build_mcp_error(exc)


@mcp_server.tool()
async def decide_approval(
    task_id: str,
    decision: Literal["approved", "rejected", "approve", "reject"] = "approved",
    decision_note: str | None = None,
    api_key: str | None = None,
) -> CallToolResult:
    """Submit an operator decision for a pending HITL task."""
    try:
        args = {
            "api_key": api_key,
            "task_id": task_id,
            "decision": decision,
            "decision_note": decision_note,
        }
        res = await execute_mcp_tool("decide_approval", args)
        return _build_mcp_result(res)
    except Exception as exc:
        return _build_mcp_error(exc)


# ---------------------------------------------------------------------------
# CLI Runner Entrypoint
# ---------------------------------------------------------------------------

def run_stdio() -> None:
    """Run the MCP server over stdio for CLI clients (Claude Desktop, Cursor, Antigravity)."""
    mcp_server.run(transport="stdio")


if __name__ == "__main__":
    run_stdio()
