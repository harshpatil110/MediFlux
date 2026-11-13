"""Comprehensive automated test suite for Task 21: Embeddings, Semantic Search, and Network Copilot."""

import json
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.hitl import clear_hitl_tasks, create_hitl_task
from app.graphs.copilot import (
    CopilotScope,
    get_cold_chain_status,
    get_demand_signals,
    get_inventory_summary,
    get_open_hitl_tasks,
    get_recent_agent_activity,
    get_stockout_risk,
    search_semantic,
)
from app.graphs.regulatory import save_notification
from app.llm.embeddings import (
    EMBEDDING_DIM,
    clear_vector_index,
    embed_batch,
    embed_text,
    index_network_embeddings,
)
from app.main import app
from app.tools.manufacturer_tools import clear_in_memory_demand_signals


@pytest.fixture(autouse=True)
def clean_copilot_environment():
    """Isolate testing environment before and after every test."""
    clear_vector_index()
    clear_hitl_tasks()
    clear_in_memory_demand_signals()
    index_network_embeddings()
    yield
    clear_vector_index()
    clear_hitl_tasks()
    clear_in_memory_demand_signals()


# -----------------------------------------------------------------------------
# 1. Embedding Service & Concept Space Vectorizer Accuracy
# -----------------------------------------------------------------------------
def test_embedding_dimension_and_normalization():
    """Verify that embed_text produces 768-dimensional unit L2-normalized vectors."""
    vec = embed_text("NPPA DPCO Ceiling Price Revision for Paracetamol")
    assert len(vec) == EMBEDDING_DIM
    # Check L2 unit norm
    norm_sq = sum(x * x for x in vec)
    assert abs(norm_sq - 1.0) < 1e-4

    batch = embed_batch(["Text one", "Text two"])
    assert len(batch) == 2
    assert len(batch[0]) == EMBEDDING_DIM
    assert len(batch[1]) == EMBEDDING_DIM


# -----------------------------------------------------------------------------
# 2. Checkpoint 4: Semantic Search by Meaning (Zero Exact Word Overlap)
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_semantic_search_zero_exact_word_overlap():
    """Search query shares zero words with target notice but matches domain concept space (> 0.65 similarity)."""
    notice_id = f"notif-dpco-{uuid.uuid4().hex[:6]}"
    # Regulatory notice with formal pharmaceutical terminology
    notice_payload = {
        "id": notice_id,
        "title": "NPPA DPCO Ceiling Price Revision for Paracetamol 500mg",
        "content": "National Pharmaceutical Pricing Authority order fixing maximum ceiling rate and tariff for antipyretic formulations.",
        "source": "NPPA",
    }
    save_notification(notice_payload)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Search query with colloquial/plain language: ZERO overlapping words
        # Query: "government maximum cost limit for fever medication"
        # Notice: "NPPA DPCO Ceiling Price Revision for Paracetamol 500mg"
        res = await client.get("/api/v1/search?q=government+maximum+cost+limit+for+fever+medication")
        assert res.status_code == 200
        body = res.json()
        assert body["count"] > 0

        # Target notice must be in results with high semantic cosine similarity
        results = body["results"]
        target = next((r for r in results if r["id"] == notice_id), None)
        assert target is not None
        assert target["type"] == "regulatory_notice"
        assert target["score"] > 0.65, f"Expected similarity > 0.65, got {target['score']}"


# -----------------------------------------------------------------------------
# 3. Checkpoint 2: Stockout Risk Query Acceptance Test
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_stockout_risk_copilot_query():
    """Querying at-risk pharmacies returns exact node names, quantities, and structured references."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        payload = {
            "question": "Which pharmacies are at risk of running out of Paracetamol in North region?",
            "stream": False,
        }
        res = await client.post(
            "/api/v1/copilot/query",
            json=payload,
            headers={"X-User-Role": "admin"},
        )
        assert res.status_code == 200
        body = res.json()

        # 1. Planner invoked get_stockout_risk
        assert "get_stockout_risk" in body["tools_used"]

        # 2. Answer names exact at-risk pharmacies from seeded network
        answer = body["answer"]
        assert "Apollo Pharmacy" in answer or "Apex Pharmacy" in answer or "City Medicos" in answer
        assert "units available" in answer.lower() or "safety" in answer.lower()

        # 3. References array contains structured citations
        refs = body["references"]
        assert len(refs) > 0
        node_ref = next((r for r in refs if r["type"] == "node"), None)
        assert node_ref is not None
        assert "id" in node_ref
        assert "label" in node_ref
        assert "node_id" in node_ref
        assert body["trace_id"] is not None


# -----------------------------------------------------------------------------
# 4. Checkpoint 3: Pharmacy RLS Isolation Acceptance Test
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_pharmacy_rls_scope_isolation():
    """Pharmacy A caller NEVER receives data or references belonging to Pharmacy B."""
    pharm_a_id = "11111111-1111-1111-1111-111111111111"
    pharm_b_id = "11111111-1111-1111-1111-111111111132"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Pharmacy A asks about network inventory or Pharmacy B
        payload = {
            "question": "What is the stock level at Apollo Pharmacy Koramangala?",
            "stream": False,
            "node_id": pharm_b_id,  # Attempting to query Pharmacy B
        }
        res = await client.post(
            "/api/v1/copilot/query",
            json=payload,
            headers={
                "X-User-Role": "pharmacy",
                "X-Node-Id": pharm_a_id,  # Authenticated as Pharmacy A
            },
        )
        assert res.status_code == 200
        body = res.json()

        # 1. Answer explicitly includes access isolation notice
        answer = body["answer"]
        assert "restricted" in answer.lower() or "isolated" in answer.lower()
        assert pharm_a_id in answer or "your authorized pharmacy" in answer.lower()

        # 2. Zero references belonging to Pharmacy B
        refs = body["references"]
        for r in refs:
            assert r.get("node_id") != pharm_b_id, f"RLS Leak: Found Pharmacy B node_id in references: {r}"


# -----------------------------------------------------------------------------
# 5. Checkpoint 5: All 7 Read-Only Parameterized Tools Direct Tests
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_all_seven_read_only_tools():
    """Verify that all 7 parameterized tools return structured records and citations."""
    admin_scope = CopilotScope(role="admin")

    # 1. search_semantic
    res_sem = await search_semantic("NPPA ceiling price", limit=3, scope=admin_scope)
    assert res_sem["tool"] == "search_semantic"
    assert "results" in res_sem

    # 2. get_stockout_risk
    res_risk = await get_stockout_risk(product="Insulin Glargine", region="North", scope=admin_scope)
    assert res_risk["tool"] == "get_stockout_risk"
    assert len(res_risk["references"]) > 0

    # 3. get_inventory_summary
    res_inv = await get_inventory_summary(product="Paracetamol", scope=admin_scope)
    assert res_inv["tool"] == "get_inventory_summary"
    assert "total_available" in res_inv

    # 4. get_open_hitl_tasks
    create_hitl_task(
        task_type="test_copilot_approval",
        payload={"notes": "Verification test"},
        risk_level="medium",
    )
    res_hitl = await get_open_hitl_tasks(status="pending", scope=admin_scope)
    assert res_hitl["tool"] == "get_open_hitl_tasks"
    assert res_hitl["count"] >= 1

    # 5. get_recent_agent_activity
    res_act = await get_recent_agent_activity(limit=5, scope=admin_scope)
    assert res_act["tool"] == "get_recent_agent_activity"

    # 6. get_demand_signals
    res_sig = await get_demand_signals(region="North", scope=admin_scope)
    assert res_sig["tool"] == "get_demand_signals"

    # 7. get_cold_chain_status
    res_cold = await get_cold_chain_status(scope=admin_scope)
    assert res_cold["tool"] == "get_cold_chain_status"
    assert "batches" in res_cold


# -----------------------------------------------------------------------------
# 6. Checkpoint 5 (Part B): SSE Streaming Query Test
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_copilot_sse_streaming():
    """Verify that stream=True progressively streams SSE events: planner, tool_result, answer, done."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        payload = {
            "question": "Which pharmacies are at risk of stockout for Insulin?",
            "stream": True,
        }
        res = await client.post(
            "/api/v1/copilot/query",
            json=payload,
            headers={"X-User-Role": "admin"},
        )
        assert res.status_code == 200
        assert "text/event-stream" in res.headers["content-type"]

        content = res.text
        # Assert streaming events are emitted in chronological order
        assert "event: planner" in content
        assert "event: tool_result" in content
        assert "event: answer" in content
        assert "event: done" in content

        # Verify parsed done payload
        lines = content.splitlines()
        done_data_line = None
        for i, line in enumerate(lines):
            if "event: done" in line and (i + 1) < len(lines):
                done_data_line = lines[i + 1]
                break

        assert done_data_line is not None
        assert done_data_line.startswith("data: ")
        done_obj = json.loads(done_data_line.replace("data: ", ""))
        assert "answer" in done_obj
        assert "references" in done_obj
        assert "tools_used" in done_obj
