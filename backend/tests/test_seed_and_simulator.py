"""Unit and integration test suite for Task 9: Synthetic Data Agent, Seed Pipeline, and POS Simulator."""

from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.agents.seed_agent import seed_agent
from app.api.v1.endpoints.inventory import DEFAULT_INVENTORY
from app.api.v1.endpoints.nodes import DEFAULT_NODES
from app.api.v1.endpoints.products import DEFAULT_PRODUCTS
from app.core.config import settings
from app.events.bus import in_process_event_bus
from app.events.models import EventEnvelope
from app.events.service import get_in_memory_stock, set_in_memory_stock
from app.main import app
from app.simulator.pos_simulator import POSSimulator
from app.simulator.sensor_simulator import SensorSimulator


@pytest.fixture(autouse=True)
def mock_supabase_offline_mode():
    """Ensure tests run locally without making remote Supabase HTTP round-trips."""
    with patch.object(settings, "SUPABASE_URL", ""):
        yield


def test_seed_pipeline_idempotency():
    """Seed Script Idempotency Test: Execute seed routine twice and verify counts remain identical."""
    # First execution
    run1 = seed_agent.seed_database()
    assert run1["nodes"] == 25  # 2 mfg + 3 dist + 5 stk + 15 pharm
    assert run1["products"] == 20
    assert run1["batches"] == 40
    assert run1["inventory"] == 425
    assert len(DEFAULT_NODES) == 25
    assert len(DEFAULT_PRODUCTS) == 20
    assert len(DEFAULT_INVENTORY) == 425

    # Second execution (must not create duplicate records)
    run2 = seed_agent.seed_database()
    assert run2["nodes"] == run1["nodes"]
    assert run2["products"] == run1["products"]
    assert run2["batches"] == run1["batches"]
    assert run2["inventory"] == run1["inventory"]
    assert len(DEFAULT_NODES) == 25
    assert len(DEFAULT_PRODUCTS) == 20
    assert len(DEFAULT_INVENTORY) == 425


def test_synthetic_data_label_check():
    """Synthetic Data Label Check: Verify 100% of generated records contain is_synthetic: true in metadata."""
    data = seed_agent.generate_all()

    for table_name, records in data.items():
        assert len(records) > 0, f"Table {table_name} generated 0 records"
        for idx, item in enumerate(records):
            metadata = item.get("metadata")
            assert metadata is not None, f"Record #{idx} in {table_name} is missing metadata"
            assert metadata.get("is_synthetic") is True, f"Record #{idx} in {table_name} lacks is_synthetic: true"


def test_medical_schedule_integrity_check():
    """Medical Schedule Integrity Check: Verify seeded products accurately mirror fixtures/drug_schedules.json."""
    raw_fixtures = seed_agent.load_drug_schedules()
    assert len(raw_fixtures) == 20

    products = seed_agent.generate_products()
    assert len(products) == 20

    prod_by_sku = {p.sku: p for p in products}

    for item in raw_fixtures:
        sku = item["sku"]
        assert sku in prod_by_sku, f"Missing product with SKU {sku}"
        prod = prod_by_sku[sku]

        assert prod.name == item["product_name"]
        assert prod.is_cold_chain == item["is_cold_chain"]
        assert prod.storage_min_c == item["min_temp_celsius"]
        assert prod.storage_max_c == item["max_temp_celsius"]
        assert prod.metadata["schedule_type"] == item["schedule_type"]
        assert prod.metadata["neml_ceiling_price"] == item["neml_ceiling_price"]
        # Enforce DPCO ceiling compliance
        assert prod.price_per_unit <= item["neml_ceiling_price"]


def test_doctor_registry_fixture_integrity():
    """Verify curated mock doctor registry matches expected schema and contents."""
    docs = seed_agent.load_doctor_registry()
    assert len(docs) >= 5
    for doc in docs:
        assert "doctor_id" in doc
        assert "license_number" in doc
        assert "name" in doc
        assert "specialization" in doc
        assert "valid_until" in doc


@pytest.mark.asyncio
async def test_pos_simulator_single_mode():
    """POS Simulator Single Mode Test: Assert 1 SaleEvent is posted to /api/v1/events/sale and stock decrements."""
    seed_agent.seed_database()

    # Find a pharmacy and its inventory
    pharmacy = next(n for n in DEFAULT_NODES if n["tier"] == "pharmacy")
    pharm_id = pharmacy["id"]

    inv_entry = next(i for i in DEFAULT_INVENTORY if i["node_id"] == pharm_id)
    prod_id = inv_entry["product_id"]
    batch_id = inv_entry["batch_id"]

    # Set known stock
    set_in_memory_stock(pharm_id, prod_id, batch_id, 30)

    sim = POSSimulator(
        app=app,
        mode="single",
        target_pharmacy_id=pharm_id,
        target_product_id=prod_id,
    )

    try:
        res = await sim.run_single(quantity=2)
        assert res["status"] == "completed"
        assert res["events_sent"] == 1

        # Check inventory decremented by 2
        remaining = get_in_memory_stock(pharm_id, prod_id, batch_id)
        assert remaining == 28
    finally:
        await sim.close()


@pytest.mark.asyncio
async def test_pos_simulator_stockout_run():
    """Test stockout_run mode: Emits continuous sales until stock reaches safety threshold."""
    seed_agent.seed_database()

    pharmacy = next(n for n in DEFAULT_NODES if n["tier"] == "pharmacy")
    pharm_id = pharmacy["id"]

    inv_entry = next(i for i in DEFAULT_INVENTORY if i["node_id"] == pharm_id)
    prod_id = inv_entry["product_id"]
    batch_id = inv_entry["batch_id"]

    # Start with 16 units, safety stock threshold = 10
    set_in_memory_stock(pharm_id, prod_id, batch_id, 16)

    sim = POSSimulator(
        app=app,
        mode="stockout_run",
        target_pharmacy_id=pharm_id,
        target_product_id=prod_id,
    )

    try:
        res = await sim.run_stockout_run(
            pharmacy_id=pharm_id,
            product_id=prod_id,
            safety_stock_threshold=10,
        )
        assert res["status"] == "completed"
        final_stock = get_in_memory_stock(pharm_id, prod_id, batch_id)
        assert final_stock <= 10
        assert res["events_sent"] >= 3
    finally:
        await sim.close()


@pytest.mark.asyncio
async def test_simulator_admin_api_endpoints():
    """Simulator Admin API Test: POST /run -> GET /status (running) -> POST /stop -> GET /status (stopped)."""
    seed_agent.seed_database()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Start simulation
        run_resp = await client.post(
            "/api/v1/simulator/run",
            json={
                "mode": "steady",
                "rate": 10.0,
                "duration_seconds": 5,
            },
        )
        assert run_resp.status_code == 200
        run_data = run_resp.json()
        assert run_data["status"] == "started"
        assert "simulation_id" in run_data

        # 2. Query status
        status_resp = await client.get("/api/v1/simulator/status")
        assert status_resp.status_code == 200
        status_data = status_resp.json()
        assert status_data["status"] in ("running", "completed", "idle")
        assert status_data["mode"] == "steady"

        # 3. Stop simulation
        stop_resp = await client.post("/api/v1/simulator/stop")
        assert stop_resp.status_code == 200
        stop_data = stop_resp.json()
        assert stop_data["status"] == "stopped"

        # 4. Verify stopped
        status2_resp = await client.get("/api/v1/simulator/status")
        assert status2_resp.status_code == 200
        status2_data = status2_resp.json()
        assert status2_data["status"] in ("stopped", "idle")


@pytest.mark.asyncio
async def test_sensor_simulator_stub():
    """Verify Environmental Sensor Simulator publishes cold-chain telemetry readings."""
    sensor = SensorSimulator(vehicle_id="KA-01-RF-8821")
    received_readings: list[EventEnvelope] = []

    def _listener(envelope: EventEnvelope) -> None:
        received_readings.append(envelope)

    in_process_event_bus.register_listener("coldchain.telemetry", _listener)

    await sensor.emit_telemetry(temp_celsius=5.4)

    assert len(received_readings) == 1
    reading = received_readings[0]
    assert reading.type == "coldchain.telemetry"
    assert reading.node_id == "KA-01-RF-8821"
    assert reading.payload["temperature_celsius"] == 5.4
    assert reading.payload["is_breached"] is False
