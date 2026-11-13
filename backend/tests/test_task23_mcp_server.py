# ruff: noqa: E402
"""Test suite for Task 23: Model Context Protocol (MCP) Server.

Verifies:
1. File & SDK Audit: Tool listing via REST, JSON-RPC, and MCP SDK.
2. Valid get_inventory execution with scoped RLS and cryptographic audit logging.
3. Insufficient scope rejection (403 / error) and audit ledger logging (mcp.tool.forbidden).
4. All remaining MCP tools (get_stockout_risk, list_open_approvals, get_cascade_trace,
   ask_copilot, submit_sale_event, decide_approval) with multi-scope key.
5. Invalid API key (401) and Token-Bucket rate limiting (429) with audit logs.
6. Node RLS boundary enforcement on write actions (reject cross-node sale events).
7. Direct MCP Server SDK call_tool integration.
8. MCP SSE transport endpoint.
"""

import sys
import uuid
from pathlib import Path

# Add repo root to sys.path
repo_root = Path(__file__).resolve().parent.parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

import httpx
import pytest
from httpx import ASGITransport

from app.core.audit_ledger import clear_in_memory_audit_ledger, get_in_memory_audit_ledger
from app.core.hitl import clear_hitl_tasks, create_hitl_task, get_in_memory_hitl_tasks
from app.graphs.cascade import _in_memory_cascade_traces, clear_cascade_traces
from app.main import app
from app.mcp.server import mcp_server
from app.services.api_keys import (
    clear_in_memory_api_keys,
    create_api_key,
    get_api_key_by_hash,
    hash_api_key,
    rate_limiter,
)

PHARMACY_NODE_ID = "11111111-1111-1111-1111-111111111111"
STOCKIST_NODE_ID = "22222222-2222-2222-2222-222222222222"


@pytest.fixture(autouse=True)
def reset_mcp_test_state():
    """Reset API keys, rate limiter, audit ledger, and HITL tasks before each test."""
    clear_in_memory_api_keys()
    clear_in_memory_audit_ledger()
    clear_hitl_tasks()
    clear_cascade_traces()
    rate_limiter.reset()
    yield
    clear_in_memory_api_keys()
    clear_in_memory_audit_ledger()
    clear_hitl_tasks()
    clear_cascade_traces()
    rate_limiter.reset()


@pytest.mark.asyncio
async def test_mcp_tools_listing() -> None:
    """Checkpoint 1 & 2: Verify tool listing across REST, JSON-RPC, and MCP SDK."""
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. REST GET /api/v1/mcp/tools
        res = await client.get("/api/v1/mcp/tools")
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["count"] == 7
        tool_names = [t["name"] for t in data["tools"]]
        expected_tools = [
            "get_inventory",
            "get_stockout_risk",
            "list_open_approvals",
            "get_cascade_trace",
            "ask_copilot",
            "submit_sale_event",
            "decide_approval",
        ]
        for t in expected_tools:
            assert t in tool_names

        # 2. JSON-RPC tools/list
        rpc_res = await client.post(
            "/api/v1/mcp/rpc",
            json={"jsonrpc": "2.0", "id": 101, "method": "tools/list", "params": {}},
        )
        assert rpc_res.status_code == 200, rpc_res.text
        rpc_data = rpc_res.json()
        assert rpc_data["id"] == 101
        rpc_tools = [t["name"] for t in rpc_data["result"]["tools"]]
        for t in expected_tools:
            assert t in rpc_tools

    # 3. Direct MCP SDK Server listing
    sdk_tools = await mcp_server.list_tools()
    assert len(sdk_tools) == 7
    sdk_names = [t.name for t in sdk_tools]
    for t in expected_tools:
        assert t in sdk_names


@pytest.mark.asyncio
async def test_valid_get_inventory_and_audit_ledger() -> None:
    """Checkpoint 2: Call get_inventory with scoped key, assert RLS filtering and audit entry."""
    # Provision API key with only read:inventory bound to PHARMACY_NODE_ID
    key_rec, raw_key = create_api_key(
        name="Pharmacy Edge Key",
        scopes=["read:inventory"],
        node_id=PHARMACY_NODE_ID,
        rate_limit=50,
    )

    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Execute tool call via POST /api/v1/mcp/call with X-API-Key header
        call_res = await client.post(
            "/api/v1/mcp/call",
            headers={"X-API-Key": raw_key},
            json={
                "name": "get_inventory",
                "arguments": {"product": "azithromycin", "limit": 10},
            },
        )
        assert call_res.status_code == 200, call_res.text
        body = call_res.json()
        assert body["is_error"] is False
        struct = body["structured_content"]
        assert struct["node_id"] == PHARMACY_NODE_ID
        assert struct["count"] >= 1
        for item in struct["items"]:
            assert item["node_id"] == PHARMACY_NODE_ID
            assert "azithral" in item["product_name"].lower() or "azi" in item["product_id"].lower()

    # Verify API key usage telemetry increment
    key_after = get_api_key_by_hash(hash_api_key(raw_key))
    assert key_after is not None
    assert key_after["usage_count"] == 1
    assert key_after["last_used_at"] is not None

    # Verify audit ledger entry
    entries = get_in_memory_audit_ledger()
    exec_entries = [e for e in entries if e["action"] == "mcp.tool.executed"]
    assert len(exec_entries) >= 1
    latest_audit = exec_entries[-1]
    assert latest_audit["actor"] == key_rec["id"]
    assert latest_audit["entity_type"] == "mcp_tool"
    assert latest_audit["entity_id"] == "get_inventory"
    assert latest_audit["payload"]["status"] == "succeeded"
    assert latest_audit["payload"]["node_id"] == PHARMACY_NODE_ID


@pytest.mark.asyncio
async def test_insufficient_scope_rejection_and_audit_ledger() -> None:
    """Checkpoint 3: Key with ONLY read:inventory receives 403 and writes mcp.tool.forbidden audit log."""
    key_rec, raw_key = create_api_key(
        name="Read Only Key",
        scopes=["read:inventory"],
        node_id=PHARMACY_NODE_ID,
    )

    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Attempt submit_sale_event (requires write:events)
        res_sale = await client.post(
            "/api/v1/mcp/call",
            headers={"X-API-Key": raw_key},
            json={
                "name": "submit_sale_event",
                "arguments": {"product_id": "p-001-azithromycin", "quantity": 1},
            },
        )
        assert res_sale.status_code == 403
        assert "Insufficient API key scope" in res_sale.json()["detail"]

        # 2. Attempt ask_copilot (requires use:copilot)
        res_copilot = await client.post(
            "/api/v1/mcp/call",
            headers={"X-API-Key": raw_key},
            json={
                "name": "ask_copilot",
                "arguments": {"question": "What is the network stock?"},
            },
        )
        assert res_copilot.status_code == 403
        assert "Insufficient API key scope" in res_copilot.json()["detail"]

        # 3. Attempt decide_approval (requires decide:approvals)
        res_decide = await client.post(
            "/api/v1/mcp/call",
            headers={"X-API-Key": raw_key},
            json={
                "name": "decide_approval",
                "arguments": {"task_id": "task-test-01", "decision": "approved"},
            },
        )
        assert res_decide.status_code == 403
        assert "Insufficient API key scope" in res_decide.json()["detail"]

        # 4. JSON-RPC test: tools/call rejection returns code -32003
        rpc_call = await client.post(
            "/api/v1/mcp/rpc",
            headers={"X-API-Key": raw_key},
            json={
                "jsonrpc": "2.0",
                "id": 999,
                "method": "tools/call",
                "params": {
                    "name": "submit_sale_event",
                    "arguments": {"quantity": 1},
                },
            },
        )
        assert rpc_call.status_code == 200
        rpc_body = rpc_call.json()
        assert "error" in rpc_body
        assert rpc_body["error"]["code"] == -32003
        assert rpc_body["error"]["data"]["status"] == 403

    # Assert cryptographic audit ledger entries for all rejections
    entries = get_in_memory_audit_ledger()
    forbidden_entries = [e for e in entries if e["action"] == "mcp.tool.forbidden"]
    assert len(forbidden_entries) >= 4  # 3 REST + 1 JSON-RPC

    tools_rejected = [e["payload"]["tool"] for e in forbidden_entries]
    assert "submit_sale_event" in tools_rejected
    assert "ask_copilot" in tools_rejected
    assert "decide_approval" in tools_rejected

    for entry in forbidden_entries:
        assert entry["actor"] == key_rec["id"]
        assert entry["payload"]["status"] == "rejected"
        assert entry["payload"]["reason"] == "insufficient_scope"


@pytest.mark.asyncio
async def test_all_remaining_mcp_tools_execution() -> None:
    """Checkpoint 4: High-privilege API key executes all remaining MCP tools cleanly."""
    key_rec, raw_key = create_api_key(
        name="Full Network Admin Key",
        scopes=[
            "read:inventory",
            "read:audit",
            "use:copilot",
            "write:events",
            "decide:approvals",
        ],
        node_id=PHARMACY_NODE_ID,
    )

    # 1. Setup HITL task to approve
    hitl_task = create_hitl_task(
        task_type="regulatory_hot_swap",
        payload={"patch_id": "patch-101", "node_id": PHARMACY_NODE_ID},
        node_id=PHARMACY_NODE_ID,
        workflow_name="regulatory_approval",
    )
    task_id = hitl_task["id"]

    # 2. Setup cascade trace in memory
    cid = f"test-trace-{uuid.uuid4()}"
    _in_memory_cascade_traces[cid] = {
        "correlation_id": cid,
        "status": "completed",
        "event": {"type": "pos.sales"},
        "steps": [
            {
                "tier": "pharmacy",
                "agent_name": "pharmacy_agent",
                "status": "success",
                "summary": "Deducted retail strip",
                "latency_ms": 12.5,
            }
        ],
    }

    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Tool: get_stockout_risk
        r_stockout = await client.post(
            "/api/v1/mcp/call",
            headers={"X-API-Key": raw_key},
            json={"name": "get_stockout_risk", "arguments": {"product": "insulin"}},
        )
        assert r_stockout.status_code == 200, r_stockout.text
        assert r_stockout.json()["is_error"] is False

        # Tool: list_open_approvals
        r_approvals = await client.post(
            "/api/v1/mcp/call",
            headers={"X-API-Key": raw_key},
            json={"name": "list_open_approvals", "arguments": {"status": "pending"}},
        )
        assert r_approvals.status_code == 200, r_approvals.text
        approvals_data = r_approvals.json()["structured_content"]
        assert approvals_data["count"] >= 1
        assert any(t["id"] == task_id for t in approvals_data["tasks"])

        # Tool: get_cascade_trace
        r_trace = await client.post(
            "/api/v1/mcp/call",
            headers={"X-API-Key": raw_key},
            json={"name": "get_cascade_trace", "arguments": {"correlation_id": cid}},
        )
        assert r_trace.status_code == 200, r_trace.text
        trace_data = r_trace.json()["structured_content"]
        assert trace_data["correlation_id"] == cid
        assert len(trace_data["steps"]) >= 1

        # Tool: ask_copilot
        r_copilot = await client.post(
            "/api/v1/mcp/call",
            headers={"X-API-Key": raw_key},
            json={"name": "ask_copilot", "arguments": {"question": "What is our stock of Azithral?"}},
        )
        assert r_copilot.status_code == 200, r_copilot.text
        copilot_data = r_copilot.json()["structured_content"]
        assert "answer" in copilot_data
        assert "references" in copilot_data

        # Tool: submit_sale_event
        sale_cid = f"mcp-sale-{uuid.uuid4()}"
        r_sale = await client.post(
            "/api/v1/mcp/call",
            headers={"X-API-Key": raw_key},
            json={
                "name": "submit_sale_event",
                "arguments": {
                    "product_id": "p-001-azithromycin",
                    "quantity": 2,
                    "correlation_id": sale_cid,
                },
            },
        )
        assert r_sale.status_code == 200, r_sale.text
        sale_data = r_sale.json()["structured_content"]
        assert sale_data["correlation_id"] == sale_cid
        assert sale_data["applied"] is True

        # Tool: decide_approval
        r_decide = await client.post(
            "/api/v1/mcp/call",
            headers={"X-API-Key": raw_key},
            json={
                "name": "decide_approval",
                "arguments": {
                    "task_id": task_id,
                    "decision": "approved",
                    "decision_note": "Approved by external agent via MCP",
                },
            },
        )
        assert r_decide.status_code == 200, r_decide.text
        decide_data = r_decide.json()["structured_content"]
        assert decide_data["decision"] == "approved"
        assert decide_data["status"] == "approved"

    # Verify task resolution
    all_hitl = get_in_memory_hitl_tasks()
    matching_tasks = [t for t in all_hitl if t.get("id") == task_id]
    assert len(matching_tasks) == 1
    assert matching_tasks[0]["status"] == "approved"

    # Verify audit entries exist for all 6 executions
    entries = get_in_memory_audit_ledger()
    executed_tools = {e["payload"]["tool"] for e in entries if e["action"] == "mcp.tool.executed"}
    for t in [
        "get_stockout_risk",
        "list_open_approvals",
        "get_cascade_trace",
        "ask_copilot",
        "submit_sale_event",
        "decide_approval",
    ]:
        assert t in executed_tools


@pytest.mark.asyncio
async def test_invalid_api_key_and_rate_limiting() -> None:
    """Checkpoint 5: Invalid API key -> 401; Rate limit burst -> 429; audit logs recorded."""
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Missing API Key
        r_missing = await client.post(
            "/api/v1/mcp/call",
            json={"name": "get_inventory", "arguments": {}},
        )
        assert r_missing.status_code == 401
        assert "API key required" in r_missing.json()["detail"]

        # 2. Invalid API Key
        r_invalid = await client.post(
            "/api/v1/mcp/call",
            headers={"X-API-Key": "mfx_live_invalid_signature_key_999"},
            json={"name": "get_inventory", "arguments": {}},
        )
        assert r_invalid.status_code == 401
        assert "Invalid or inactive API key" in r_invalid.json()["detail"]

        # Verify unauthorized audit logging
        entries = get_in_memory_audit_ledger()
        unauth = [e for e in entries if e["action"] == "mcp.tool.unauthorized"]
        assert len(unauth) >= 2

        # 3. Rate limiting test: create key with rate_limit=2
        _, raw_limited_key = create_api_key(
            name="Strict Rate Limited Key",
            scopes=["read:inventory"],
            rate_limit=2,
        )

        r1 = await client.post(
            "/api/v1/mcp/call",
            headers={"X-API-Key": raw_limited_key},
            json={"name": "get_inventory", "arguments": {}},
        )
        assert r1.status_code == 200

        r2 = await client.post(
            "/api/v1/mcp/call",
            headers={"X-API-Key": raw_limited_key},
            json={"name": "get_inventory", "arguments": {}},
        )
        assert r2.status_code == 200

        r3 = await client.post(
            "/api/v1/mcp/call",
            headers={"X-API-Key": raw_limited_key},
            json={"name": "get_inventory", "arguments": {}},
        )
        assert r3.status_code == 429
        assert "Retry-After" in r3.headers
        assert "Rate limit exceeded" in r3.json()["detail"]

        # Verify rate_limited audit log
        entries = get_in_memory_audit_ledger()
        rate_logs = [e for e in entries if e["action"] == "mcp.tool.rate_limited"]
        assert len(rate_logs) >= 1
        assert rate_logs[-1]["payload"]["status"] == "rejected"
        assert rate_logs[-1]["payload"]["reason"] == "rate_limit_exceeded"


@pytest.mark.asyncio
async def test_node_rls_boundary_isolation() -> None:
    """Verify pharmacy-bound key cannot submit sales for other network nodes."""
    _, raw_key = create_api_key(
        name="Pharmacy Alpha Key",
        scopes=["write:events"],
        node_id=PHARMACY_NODE_ID,
    )

    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Attempt to submit sale for STOCKIST_NODE_ID
        res = await client.post(
            "/api/v1/mcp/call",
            headers={"X-API-Key": raw_key},
            json={
                "name": "submit_sale_event",
                "arguments": {
                    "product_id": "p-001-azithromycin",
                    "quantity": 1,
                    "node_id": STOCKIST_NODE_ID,
                },
            },
        )
        assert res.status_code == 403
        assert "bound to node" in res.json()["detail"]

    # Verify node_mismatch audit entry
    entries = get_in_memory_audit_ledger()
    mismatch_entries = [
        e for e in entries
        if e["action"] == "mcp.tool.forbidden" and e["payload"].get("reason") == "node_mismatch"
    ]
    assert len(mismatch_entries) >= 1
    assert mismatch_entries[-1]["payload"]["attempted_node_id"] == STOCKIST_NODE_ID


@pytest.mark.asyncio
async def test_mcp_server_sdk_direct_calls() -> None:
    """Verify tool execution directly via the official MCP SDK server interface."""
    _, valid_key = create_api_key(
        name="SDK Test Key",
        scopes=["read:inventory"],
        node_id=PHARMACY_NODE_ID,
    )

    # 1. Valid call_tool via SDK
    res = await mcp_server.call_tool(
        "get_inventory",
        {"api_key": valid_key, "product": "azithromycin"},
    )
    assert res.is_error is False
    assert res.structured_content is not None
    assert res.structured_content["count"] >= 1

    # 2. Scope error via SDK (submit_sale_event requires write:events)
    res_err = await mcp_server.call_tool(
        "submit_sale_event",
        {"api_key": valid_key, "quantity": 1},
    )
    assert res_err.is_error is True
    assert "Insufficient API key scope" in res_err.content[0].text


@pytest.mark.asyncio
async def test_mcp_sse_transport_endpoint() -> None:
    """Verify MCP SSE transport endpoint connects and emits stream events."""
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/mcp/sse")
        assert res.status_code == 200
        assert "text/event-stream" in res.headers["content-type"]
        assert "endpoint" in res.text
        assert "/api/v1/mcp/call" in res.text
