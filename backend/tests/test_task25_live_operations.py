"""Automated test suite for Task 25: Live Operations Screens (Overview, Cascade Replay, Agent Console).

Tests cover:
1. POS Simulator Single-Strip Demand Propagation (POST /api/v1/simulator/pos & POST /api/v1/cascade/trigger)
2. Execution of complete 4-tier cascade trace (Tier 4 -> Tier 3 -> Tier 2 -> Tier 1)
3. Deterministic Historical Replay consistency (GET /api/v1/cascade/{correlation_id})
4. Cascade summary list retrieval (GET /api/v1/cascade)
5. Live Operational KPIs (GET /api/v1/overview/kpis) with stockout_risks >= 4
6. Agent runs observability (GET /api/v1/agents/runs) with query filtering
7. Mathematical token invariance guarantee (metrics.total_tokens == sum(run.total_tokens))
"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

AUTH_HEADER = {"Authorization": "Bearer mock-admin-token"}


@pytest.mark.asyncio
async def test_simulator_pos_single_trigger_and_4_tier_cascade():
    """Verify 'Sell 1 Strip' triggers an automated, realistic 4-tier supply chain cascade."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        payload = {
            "mode": "single",
            "quantity": 1,
        }
        resp = await client.post("/api/v1/simulator/pos", json=payload, headers=AUTH_HEADER)
        assert resp.status_code == 200
        data = resp.json()

        assert "correlation_id" in data
        assert data["correlation_id"].startswith("casc-")
        assert data["mode"] == "single"
        assert data["events_created"] >= 1

        cascade = data.get("cascade")
        assert cascade is not None
        assert cascade["correlation_id"] == data["correlation_id"]
        assert cascade["status"] in ("completed", "succeeded")

        steps = cascade.get("steps", [])
        assert len(steps) == 4

        # Verify all 4 tiers executed in strict sequence:
        # Tier 4 (Pharmacy) -> Tier 3 (Stockist) -> Tier 2 (Distributor) -> Tier 1 (Manufacturer)
        tier_numbers = [s["tier"] for s in steps]
        assert tier_numbers == [4, 3, 2, 1]

        # Check Pharmacy step details
        pharmacy_step = steps[0]
        assert pharmacy_step["tier"] == 4
        assert "Pharmacy" in pharmacy_step["tier_label"]
        assert pharmacy_step["status"] == "succeeded"
        assert len(pharmacy_step["reasoning"]) > 10
        assert pharmacy_step["total_tokens"] > 0
        assert pharmacy_step["duration_ms"] > 0

        # Check Stockist step details
        stockist_step = steps[1]
        assert stockist_step["tier"] == 3
        assert "Stockist" in stockist_step["tier_label"]
        assert stockist_step["status"] == "succeeded"
        assert len(stockist_step["reasoning"]) > 10

        # Check Distributor step details
        distributor_step = steps[2]
        assert distributor_step["tier"] == 2
        assert "Distributor" in distributor_step["tier_label"]
        assert distributor_step["status"] == "succeeded"

        # Check Manufacturer step details
        mfg_step = steps[3]
        assert mfg_step["tier"] == 1
        assert "Formulation" in mfg_step["tier_label"] or "Manufacturer" in mfg_step["tier_label"]
        assert mfg_step["status"] == "succeeded"


@pytest.mark.asyncio
async def test_simulator_pos_modes_and_alias():
    """Verify steady, burst, and stockout modes and the /api/v1/cascade/trigger alias."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Stockout Mode
        stockout_resp = await client.post(
            "/api/v1/simulator/pos",
            json={"mode": "stockout", "quantity": 30},
            headers=AUTH_HEADER,
        )
        assert stockout_resp.status_code == 200
        stockout_data = stockout_resp.json()
        assert stockout_data["mode"] == "stockout"
        assert len(stockout_data["cascade"]["steps"]) == 4

        # 2. Steady Traffic Mode
        steady_resp = await client.post(
            "/api/v1/simulator/pos",
            json={"mode": "steady"},
            headers=AUTH_HEADER,
        )
        assert steady_resp.status_code == 200
        assert steady_resp.json()["events_created"] >= 3

        # 3. Burst Mode
        burst_resp = await client.post(
            "/api/v1/simulator/pos",
            json={"mode": "burst"},
            headers=AUTH_HEADER,
        )
        assert burst_resp.status_code == 200
        assert burst_resp.json()["events_created"] >= 8

        # 4. Cascade Trigger Alias
        alias_resp = await client.post(
            "/api/v1/cascade/trigger",
            json={"mode": "single", "quantity": 1},
            headers=AUTH_HEADER,
        )
        assert alias_resp.status_code == 200
        assert alias_resp.json()["correlation_id"].startswith("casc-")


@pytest.mark.asyncio
async def test_deterministic_historical_cascade_replay():
    """Verify querying GET /api/v1/cascade/{correlation_id} twice returns the identical stored trace."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Trigger a cascade to generate a correlation ID
        trigger_resp = await client.post(
            "/api/v1/simulator/pos",
            json={"mode": "single", "quantity": 1},
            headers=AUTH_HEADER,
        )
        assert trigger_resp.status_code == 200
        corr_id = trigger_resp.json()["correlation_id"]

        # 2. First retrieval
        resp_1 = await client.get(f"/api/v1/cascade/{corr_id}", headers=AUTH_HEADER)
        assert resp_1.status_code == 200
        trace_1 = resp_1.json()

        # 3. Second retrieval (historical replay)
        resp_2 = await client.get(f"/api/v1/cascade/{corr_id}", headers=AUTH_HEADER)
        assert resp_2.status_code == 200
        trace_2 = resp_2.json()

        # Deterministic equality checks
        assert trace_1["correlation_id"] == trace_2["correlation_id"] == corr_id
        assert trace_1["started_at"] == trace_2["started_at"]
        assert trace_1["completed_at"] == trace_2["completed_at"]
        assert trace_1["total_duration_ms"] == trace_2["total_duration_ms"]
        assert trace_1["total_tokens"] == trace_2["total_tokens"]
        assert len(trace_1["steps"]) == len(trace_2["steps"]) == 4

        for step_a, step_b in zip(trace_1["steps"], trace_2["steps"], strict=True):
            assert step_a["tier"] == step_b["tier"]
            assert step_a["agent_name"] == step_b["agent_name"]
            assert step_a["node_id"] == step_b["node_id"]
            assert step_a["reasoning"] == step_b["reasoning"]
            assert step_a["input"] == step_b["input"]
            assert step_a["output"] == step_b["output"]
            assert step_a["total_tokens"] == step_b["total_tokens"]
            assert step_a["duration_ms"] == step_b["duration_ms"]

        # 4. Non-existent correlation ID returns 404
        resp_404 = await client.get("/api/v1/cascade/non-existent-uuid-999", headers=AUTH_HEADER)
        assert resp_404.status_code == 404


@pytest.mark.asyncio
async def test_cascade_summary_list():
    """Verify GET /api/v1/cascade returns recent cascade traces with summaries."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/cascade?limit=10", headers=AUTH_HEADER)
        assert resp.status_code == 200
        summaries = resp.json()

        assert isinstance(summaries, list)
        assert len(summaries) >= 1

        first = summaries[0]
        assert "correlation_id" in first
        assert "timestamp" in first
        assert "product_name" in first
        assert "pharmacy_name" in first
        assert "tiers_completed" in first
        assert first["tiers_completed"] == "4/4"
        assert first["total_tokens"] > 0


@pytest.mark.asyncio
async def test_overview_kpis():
    """Verify GET /api/v1/overview/kpis returns live operational metrics with stockout_risks >= 4."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/overview/kpis", headers=AUTH_HEADER)
        assert resp.status_code == 200
        kpis = resp.json()

        assert "events_today" in kpis
        assert "total_events" in kpis
        assert "stockout_risks" in kpis
        assert "open_approvals" in kpis
        assert "quarantined_batches" in kpis
        assert "total_nodes" in kpis
        assert "total_products" in kpis

        assert kpis["total_events"] >= 0
        assert kpis["stockout_risks"] >= 4
        assert kpis["total_nodes"] >= 1
        assert kpis["total_products"] >= 1


@pytest.mark.asyncio
async def test_agent_runs_filtering_and_metrics_invariance():
    """Verify agent runs filtering and prove mathematical token invariance:

    metrics.total_tokens == sum(run.total_tokens for run in agent_runs).
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Fetch all runs
        runs_resp = await client.get("/api/v1/agents/runs?limit=100", headers=AUTH_HEADER)
        assert runs_resp.status_code == 200
        all_runs = runs_resp.json()
        assert len(all_runs) >= 4

        # 2. Fetch metrics
        metrics_resp = await client.get("/api/v1/agents/metrics", headers=AUTH_HEADER)
        assert metrics_resp.status_code == 200
        metrics = metrics_resp.json()

        # Mathematical Invariance Guarantee Check
        sum_tokens = sum(r["total_tokens"] for r in all_runs)
        sum_prompt_tokens = sum(r["prompt_tokens"] for r in all_runs)
        sum_comp_tokens = sum(r["completion_tokens"] for r in all_runs)

        assert metrics["total_tokens"] == sum_tokens
        assert metrics["total_prompt_tokens"] == sum_prompt_tokens
        assert metrics["total_completion_tokens"] == sum_comp_tokens

        # Check by_agent sum
        agent_tokens_sum = sum(a["total_tokens"] for a in metrics["by_agent"])
        assert agent_tokens_sum == metrics["total_tokens"]

        # Check by_provider sum
        provider_tokens_sum = sum(p["total_tokens"] for p in metrics["by_provider"])
        assert provider_tokens_sum == metrics["total_tokens"]

        # 3. Test filtering runs by status
        succeeded_resp = await client.get(
            "/api/v1/agents/runs?status=succeeded", headers=AUTH_HEADER
        )
        assert succeeded_resp.status_code == 200
        for r in succeeded_resp.json():
            assert r["status"] == "succeeded"

        # 4. Test filtering runs by graph
        graph_resp = await client.get(
            "/api/v1/agents/runs?graph=cascade_graph", headers=AUTH_HEADER
        )
        assert graph_resp.status_code == 200
        for r in graph_resp.json():
            assert r["graph"] == "cascade_graph"
