"""Comprehensive automated test suite for Task 20 Cold-Chain Telemetry Graph."""

import uuid
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.agents.base import _in_memory_agent_runs
from app.core.audit_ledger import clear_in_memory_audit_ledger, get_in_memory_audit_ledger
from app.core.hitl import clear_hitl_tasks, get_in_memory_hitl_tasks
from app.graphs.coldchain import (
    estimate_shelf_life,
    reset_coldchain_state,
    run_coldchain_pipeline,
)
from app.main import app
from app.simulator.sensor_simulator import SensorSimulator


@pytest.fixture(autouse=True)
def clean_coldchain_environment():
    """Isolate testing environment before and after every test."""
    reset_coldchain_state()
    clear_in_memory_audit_ledger()
    clear_hitl_tasks()
    _in_memory_agent_runs.clear()
    yield
    reset_coldchain_state()
    clear_in_memory_audit_ledger()
    clear_hitl_tasks()
    _in_memory_agent_runs.clear()


# -----------------------------------------------------------------------------
# 1. Degradation Model Formula Accuracy Unit Test
# -----------------------------------------------------------------------------
def test_arrhenius_and_shock_degradation_formula():
    """Verify mathematical accuracy of the Simplified Arrhenius Degree-Hour and Shock Degradation Model."""
    # Test 1: Normal storage within safe envelope (5.0 C, 2.0-8.0 C range)
    normal_res = estimate_shelf_life(
        batch_id="BIO-TEST-01",
        readings=[
            {"temperature_c": 5.0, "duration_minutes": 60.0, "shock_g": 0.2},
            {"temperature_c": 4.5, "duration_minutes": 60.0, "shock_g": 0.3},
        ],
        storage_min_c=2.0,
        storage_max_c=8.0,
        base_nominal_days=100.0,
    )
    assert normal_res["cumulative_thermal_penalty_days"] == 0.0
    assert normal_res["cumulative_shock_penalty_days"] == 0.0
    assert normal_res["estimated_remaining_days"] == 100.0
    assert normal_res["shelf_life_pct"] == 100.0

    # Test 2: Heat excursion (18.0 C for 60 minutes, storage_max_c = 8.0 C)
    # ΔT = 18 - 8 = 10.0
    # penalty = (60 / 60) * 10.0 * 0.75 * 2^(10.0 / 10.0) = 1.0 * 10.0 * 0.75 * 2.0 = 15.0 days
    heat_res = estimate_shelf_life(
        batch_id="BIO-TEST-HEAT",
        readings=[{"temperature_c": 18.0, "duration_minutes": 60.0, "shock_g": 0.1}],
        storage_min_c=2.0,
        storage_max_c=8.0,
        base_nominal_days=100.0,
    )
    assert heat_res["cumulative_thermal_penalty_days"] == 15.0
    assert heat_res["estimated_remaining_days"] == 85.0
    assert heat_res["shelf_life_pct"] == 85.0
    assert heat_res["degradation_days"] == 15.0

    # Test 3: Freezing excursion (-2.0 C for 30 minutes, storage_min_c = 2.0 C)
    # ΔT_freeze = 2.0 - (-2.0) = 4.0
    # penalty = (30 / 60) * 4.0 * 4.0 = 0.5 * 16.0 = 8.0 days
    freeze_res = estimate_shelf_life(
        batch_id="BIO-TEST-FREEZE",
        readings=[{"temperature_c": -2.0, "duration_minutes": 30.0, "shock_g": 0.1}],
        storage_min_c=2.0,
        storage_max_c=8.0,
        base_nominal_days=50.0,
    )
    assert freeze_res["cumulative_thermal_penalty_days"] == 8.0
    assert freeze_res["estimated_remaining_days"] == 42.0

    # Test 4: Moderate mechanical shock (6.0g, warn threshold 4.0g)
    # penalty = (6.0 - 4.0) * 5.0 = 10.0 days
    shock_res = estimate_shelf_life(
        batch_id="BIO-TEST-SHOCK",
        readings=[{"temperature_c": 5.0, "duration_minutes": 15.0, "shock_g": 6.0}],
        storage_min_c=2.0,
        storage_max_c=8.0,
        base_nominal_days=60.0,
    )
    assert shock_res["cumulative_shock_penalty_days"] == 10.0
    assert shock_res["estimated_remaining_days"] == 50.0

    # Test 5: Critical mechanical shock breach (>= 8.0g)
    crit_shock_res = estimate_shelf_life(
        batch_id="BIO-TEST-CRIT-SHOCK",
        readings=[{"temperature_c": 5.0, "duration_minutes": 15.0, "shock_g": 8.5}],
        storage_min_c=2.0,
        storage_max_c=8.0,
        base_nominal_days=120.0,
    )
    assert crit_shock_res["critical_shock"] is True
    assert crit_shock_res["estimated_remaining_days"] == 0.0
    assert crit_shock_res["shelf_life_pct"] == 0.0


# -----------------------------------------------------------------------------
# 2. Checkpoint 2: Normal Readings Acceptance Test
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_normal_readings_acceptance():
    """Normal readings keep batch active, stock intact, and update shelf life."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Ingest compliant telemetry reading
        payload = {
            "batch_id": "BIO-INS-01",
            "temperature_c": 4.5,
            "humidity": 50.0,
            "shock_g": 0.2,
            "duration_minutes": 15.0,
            "mode": "normal",
            "node_id": "22222222-2222-2222-2222-222222222222",
        }
        res = await client.post("/api/v1/events/sensor", json=payload)
        assert res.status_code == 202
        body = res.json()
        assert body["decision"] == "ok"
        assert body["quarantined"] is False
        assert body["quarantine_action_id"] is None
        assert "optimal" in body["explanation"].lower() or "compliant" in body["explanation"].lower()

        # Query GET /api/v1/coldchain/batches
        b_res = await client.get("/api/v1/coldchain/batches")
        assert b_res.status_code == 200
        batches = b_res.json()["batches"]
        target = next((b for b in batches if b["batch_id"] == "BIO-INS-01"), None)
        assert target is not None
        assert target["status"] == "active"
        assert target["available_quantity"] == 1000
        assert target["last_reading"]["temperature_c"] == 4.5
        assert target["shelf_life_estimate"]["decision"] == "ok"

        # Query GET /api/v1/coldchain/quarantines (no quarantines created)
        q_res = await client.get("/api/v1/coldchain/quarantines")
        assert q_res.status_code == 200
        assert q_res.json()["total"] == 0


# -----------------------------------------------------------------------------
# 3. Checkpoint 3: Excursion Quarantine & Stock Removal Test
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_thermal_excursion_quarantine_and_stock_removal():
    """Thermal excursion triggers quarantine, zeroes available stock, logs explanation, and writes audit record."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        corr_id = str(uuid.uuid4())
        # Post sustained thermal excursion (e.g., 16.5 C > 8.0 C for 45 minutes)
        payload = {
            "batch_id": "BIO-VAC-01",
            "temperature_c": 16.5,
            "humidity": 65.0,
            "shock_g": 0.3,
            "duration_minutes": 45.0,
            "mode": "excursion",
            "node_id": "22222222-2222-2222-2222-222222222222",
            "correlation_id": corr_id,
        }
        res = await client.post("/api/v1/events/sensor", json=payload)
        assert res.status_code == 202
        body = res.json()

        # 1. Telemetry Agent decided quarantine
        assert body["decision"] == "quarantine"
        assert body["quarantined"] is True
        assert body["quarantine_action_id"] is not None

        # 2. Excursion Analyst plain-language explanation
        explanation = body["explanation"]
        assert "BIO-VAC-01" in explanation
        assert "excursion" in explanation.lower() or "quarantined" in explanation.lower()

        # 3. Batch available stock dropped to 0 in GET /api/v1/coldchain/batches
        b_res = await client.get("/api/v1/coldchain/batches")
        assert b_res.status_code == 200
        batches = b_res.json()["batches"]
        target = next((b for b in batches if b["batch_id"] == "BIO-VAC-01"), None)
        assert target is not None
        assert target["status"] == "quarantined"
        assert target["available_quantity"] == 0

        # 4. Quarantine action record in GET /api/v1/coldchain/quarantines
        q_res = await client.get("/api/v1/coldchain/quarantines")
        assert q_res.status_code == 200
        quarantines = q_res.json()["quarantines"]
        assert len(quarantines) == 1
        q_action = quarantines[0]
        assert q_action["batch_id"] == "BIO-VAC-01"
        assert q_action["status"] == "quarantined"
        assert q_action["reason"] == explanation
        assert q_action["correlation_id"] == corr_id

        # 5. Cryptographic Audit Log verification
        audit_entries = get_in_memory_audit_ledger()
        assert len(audit_entries) >= 1
        coldchain_audit = next((a for a in audit_entries if a.get("action") == "COLDCHAIN_QUARANTINE_EXECUTED"), None)
        assert coldchain_audit is not None
        assert coldchain_audit["actor"] == "ColdChainTelemetryGraph"
        assert coldchain_audit["entity_id"] == "BIO-VAC-01"
        assert coldchain_audit["explanation"] == explanation


# -----------------------------------------------------------------------------
# 4. Checkpoint 4: Mechanical Shock Breach Test
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_mechanical_shock_breach_quarantine():
    """Severe physical handling impact (shock_g >= 8.5g) triggers immediate quarantine."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        payload = {
            "batch_id": "BIO-VAC-ROT-01",
            "temperature_c": 4.8,
            "humidity": 52.0,
            "shock_g": 9.2,
            "duration_minutes": 15.0,
            "mode": "shock",
            "node_id": "22222222-2222-2222-2222-222222222222",
            "shipment_id": "SHP-DL-MUM-901",
        }
        res = await client.post("/api/v1/events/sensor", json=payload)
        assert res.status_code == 202
        body = res.json()

        assert body["decision"] == "quarantine"
        assert body["quarantined"] is True
        assert body["shelf_life_estimate"]["critical_shock"] is True
        assert body["shelf_life_estimate"]["estimated_remaining_days"] == 0.0

        explanation = body["explanation"]
        assert "shock" in explanation.lower()
        assert "9.2" in explanation

        # Stock zeroed in batch list
        b_res = await client.get("/api/v1/coldchain/batches")
        batches = b_res.json()["batches"]
        target = next((b for b in batches if b["batch_id"] == "BIO-VAC-ROT-01"), None)
        assert target["status"] == "quarantined"
        assert target["available_quantity"] == 0


# -----------------------------------------------------------------------------
# 5. Checkpoint 5: Dynamic Balancing Agent (Task 12) Rebalancing Trace Test
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_rebalancing_activity_visible_in_trace():
    """Verify that auto-quarantine triggers Task 12 Dynamic Balancing Agent visible in agent_runs."""
    corr_id = str(uuid.uuid4())
    result = await run_coldchain_pipeline(
        batch_id="BIO-INS-01",
        readings={
            "temperature_c": 17.5,
            "humidity": 60.0,
            "shock_g": 0.2,
            "duration_minutes": 45.0,
            "mode": "excursion",
        },
        node_id="22222222-2222-2222-2222-222222222222",
        correlation_id=corr_id,
    )

    assert result["decision"] == "quarantine"
    assert result["quarantined"] is True
    rebal = result.get("rebalance_result")
    assert rebal is not None
    assert "action" in rebal or "reasoning" in rebal

    # Check agent_runs for both coldchain agents and stockist_agent under this correlation_id
    runs = [r for r in _in_memory_agent_runs if r.get("correlation_id") == corr_id]
    agent_names = [r.get("agent_name") for r in runs]
    assert "telemetry_agent" in agent_names
    assert "excursion_analyst" in agent_names
    assert "stockist_agent" in agent_names


# -----------------------------------------------------------------------------
# 6. Checkpoint 6: High-Value HITL Policy Test
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_high_value_hitl_quarantine_policy():
    """High-value batch creates pending HITL task while still immediately executing quarantine."""
    corr_id = str(uuid.uuid4())
    with patch.dict("os.environ", {"COLDCHAIN_HIGH_VALUE_HITL_THRESHOLD": "10000.0"}):
        result = await run_coldchain_pipeline(
            batch_id="BIO-VAC-01",  # 2500 units * 225.0 = 562,500 INR (exceeds threshold)
            readings={
                "temperature_c": 19.0,
                "humidity": 70.0,
                "shock_g": 0.2,
                "duration_minutes": 35.0,
                "mode": "excursion",
            },
            correlation_id=corr_id,
            require_hitl_for_high_value=True,
        )

        assert result["decision"] == "quarantine"
        assert result["quarantined"] is True
        assert result["hitl_task_id"] is not None

        # HITL task is recorded
        hitl_tasks = get_in_memory_hitl_tasks()
        task = next((t for t in hitl_tasks if t.get("id") == result["hitl_task_id"]), None)
        assert task is not None
        assert task["status"] == "pending"
        assert task["action_type"] == "coldchain_quarantine_disposition"


# -----------------------------------------------------------------------------
# 7. Checkpoint 7: Sensor Simulator Integration
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_sensor_simulator_integration():
    """Run SensorSimulator against test client in normal and excursion modes."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        sim = SensorSimulator(base_url="http://test")

        # 1. Normal mode simulation
        normal_runs = await sim.run_simulation(
            batch_id="BIO-INS-01",
            mode="normal",
            steps=2,
            client=client,
        )
        assert len(normal_runs) == 2
        for r in normal_runs:
            assert r["decision"] == "ok"
            assert r["quarantined"] is False

        # 2. Excursion mode simulation
        excursion_runs = await sim.run_simulation(
            batch_id="BIO-VAC-01",
            mode="excursion",
            steps=2,
            client=client,
        )
        assert len(excursion_runs) == 2
        assert any(r["decision"] == "quarantine" for r in excursion_runs)
