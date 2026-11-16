"""Tests for Task M4: Pharmacy POS Lite, Barcode Lookup, FEFO Sale & 5-Stage Cascade."""

import json
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def auth_headers():
    return {
        "Authorization": "Bearer demo-token-pharmacy",
        "X-User-Role": "pharmacy",
        "X-Node-Id": "11111111-1111-1111-1111-111111111111",
    }


@pytest.mark.anyio
async def test_barcode_lookup_success(auth_headers):
    """Verify barcode lookup endpoint returns product and FEFO-sorted batches."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Paracetamol barcode
        res = await client.get("/api/v1/products/by-barcode/8901000000018", headers=auth_headers)
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["barcode"] == "8901000000018"
        assert "Paracetamol" in data["name"] or "PCM" in data["sku"]
        assert "batches" in data
        assert len(data["batches"]) >= 1

        # Check FEFO sort order: expiry dates must be ascending
        batches = data["batches"]
        expiry_dates = [b["expiry_date"] for b in batches]
        assert expiry_dates == sorted(expiry_dates), f"Batches are not FEFO sorted: {expiry_dates}"


@pytest.mark.anyio
async def test_barcode_lookup_not_found(auth_headers):
    """Verify non-existent barcode lookup returns 404."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/api/v1/products/by-barcode/UNKNOWN_999999", headers=auth_headers)
        assert res.status_code == 404
        data = res.json()
        code = data.get("error", {}).get("code") or data.get("code")
        assert code == "PRODUCT_NOT_FOUND" or "PRODUCT_NOT_FOUND" in res.text


@pytest.mark.anyio
async def test_fefo_batches_near_expiry_and_quarantine_flags(auth_headers):
    """Verify mock or real batches expose days_to_expiry, is_near_expiry, and quarantine flags."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Insulin (Cold chain)
        res = await client.get("/api/v1/products/by-barcode/8901000000056", headers=auth_headers)
        assert res.status_code == 200
        data = res.json()
        assert data["is_cold_chain"] is True
        assert len(data["batches"]) >= 2

        # Check that days_to_expiry is populated on all batches
        for b in data["batches"]:
            assert "days_to_expiry" in b
            assert "is_near_expiry" in b
            assert "available_quantity" in b


@pytest.mark.anyio
async def test_quarantined_batch_sale_rejection(auth_headers):
    """Attempting to dispense a quarantined batch must be rejected with 409 BATCH_QUARANTINED."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Look up product to find the quarantined batch
        lookup_res = await client.get("/api/v1/products/by-barcode/8901000000018", headers=auth_headers)
        batches = lookup_res.json()["batches"]
        quarantined_batch = next((b for b in batches if b.get("is_quarantined")), None)
        assert quarantined_batch is not None, "Expected at least one quarantined test batch"

        batch_code = quarantined_batch.get("batch_number") or quarantined_batch.get("batch_no")
        sale_payload = {
            "event_id": "test-quarantine-block-uuid-001",
            "product_id": lookup_res.json()["id"],
            "batch_number": batch_code,
            "quantity": 1,
            "node_id": "11111111-1111-1111-1111-111111111111",
            "channel": "mobile_pos",
        }

        res = await client.post("/api/v1/events/sale", json=sale_payload, headers=auth_headers)
        assert res.status_code == 409
        body = res.json()
        code = body.get("error", {}).get("code") or body.get("code")
        assert code == "BATCH_QUARANTINED"
        assert "quarantine" in res.text.lower()


@pytest.mark.anyio
async def test_single_unit_sale_inventory_decrement_and_cascade(auth_headers):
    """Selling 1 strip decrements shelf inventory and triggers full cascade trace."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        lookup_res = await client.get("/api/v1/products/by-barcode/8901000000018", headers=auth_headers)
        batches = lookup_res.json()["batches"]
        valid_batch = next(b for b in batches if not b.get("is_quarantined") and b["available_quantity"] > 0)
        batch_code = valid_batch.get("batch_number") or valid_batch.get("batch_no")

        client_event_id = "test-sale-uuid-strip-001"
        sale_payload = {
            "event_id": client_event_id,
            "product_id": lookup_res.json()["id"],
            "batch_number": batch_code,
            "quantity": 1,
            "node_id": "11111111-1111-1111-1111-111111111111",
            "channel": "mobile_pos",
        }

        res = await client.post("/api/v1/events/sale", json=sale_payload, headers=auth_headers)
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["quantity_sold"] == 1
        assert data["applied"] is True
        assert data["idempotent_replay"] is False
        first_remaining = data["remaining_stock"]
        assert first_remaining is not None
        assert "correlation_id" in data
        assert "cascade_trace" in data

        # Perform a second distinct sale and verify remaining stock decrements by exactly 1
        sale_payload_2 = dict(sale_payload)
        sale_payload_2["event_id"] = "test-sale-uuid-strip-002"
        res2 = await client.post("/api/v1/events/sale", json=sale_payload_2, headers=auth_headers)
        assert res2.status_code == 200
        data2 = res2.json()
        assert data2["remaining_stock"] == first_remaining - 1

        trace = data["cascade_trace"]
        assert trace["status"] == "completed"
        assert len(trace["steps"]) == 5


@pytest.mark.anyio
async def test_event_id_idempotency_double_post(auth_headers):
    """Submitting the exact same event_id twice returns idempotent_replay: true without double decrement."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        lookup_res = await client.get("/api/v1/products/by-barcode/8901000000025", headers=auth_headers)
        batches = lookup_res.json()["batches"]
        valid_batch = next(b for b in batches if not b.get("is_quarantined") and b["available_quantity"] > 0)
        batch_code = valid_batch.get("batch_number") or valid_batch.get("batch_no")

        idempotent_event_id = "idem-test-uuid-9999"
        payload = {
            "event_id": idempotent_event_id,
            "product_id": lookup_res.json()["id"],
            "batch_number": batch_code,
            "quantity": 1,
            "node_id": "11111111-1111-1111-1111-111111111111",
            "prescription_id": "rx-test-001",
            "channel": "mobile_pos",
        }

        # First post
        res1 = await client.post("/api/v1/events/sale", json=payload, headers=auth_headers)
        assert res1.status_code == 200
        data1 = res1.json()
        assert data1["idempotent_replay"] is False
        stock_after_first = data1["remaining_stock"]

        # Second post (Exact same event_id)
        res2 = await client.post("/api/v1/events/sale", json=payload, headers=auth_headers)
        assert res2.status_code == 200
        data2 = res2.json()
        assert data2["idempotent_replay"] is True
        assert data2["correlation_id"] == data1["correlation_id"]
        # Stock must NOT have decremented a second time!
        assert data2["remaining_stock"] == stock_after_first


@pytest.mark.anyio
async def test_schedule_h_prescription_handling(auth_headers):
    """Schedule H drug without prescription flags compliance hold; with prescription verifies clean."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Amoxicillin (Schedule H drug)
        lookup_res = await client.get("/api/v1/products/by-barcode/8901000000025", headers=auth_headers)
        assert lookup_res.json()["requires_prescription"] is True
        valid_batch = next(b for b in lookup_res.json()["batches"] if not b.get("is_quarantined"))
        batch_code = valid_batch.get("batch_number") or valid_batch.get("batch_no")

        # 1. Sale without prescription -> Compliance hold flagged
        res_no_rx = await client.post(
            "/api/v1/events/sale",
            json={
                "event_id": "sched-h-no-rx-test-01",
                "product_id": lookup_res.json()["id"],
                "batch_number": batch_code,
                "quantity": 1,
                "node_id": "11111111-1111-1111-1111-111111111111",
                "channel": "mobile_pos",
            },
            headers=auth_headers,
        )
        assert res_no_rx.status_code == 200
        data_no_rx = res_no_rx.json()
        assert data_no_rx["compliance_hold"] is True
        assert "compliance_warning" in data_no_rx or "warning" in data_no_rx

        # 2. Sale with prescription -> Compliance verified clean
        res_with_rx = await client.post(
            "/api/v1/events/sale",
            json={
                "event_id": "sched-h-with-rx-test-02",
                "product_id": lookup_res.json()["id"],
                "batch_number": batch_code,
                "quantity": 1,
                "node_id": "11111111-1111-1111-1111-111111111111",
                "prescription_id": "rx-dr-sharma-2026-001",
                "channel": "mobile_pos",
            },
            headers=auth_headers,
        )
        assert res_with_rx.status_code == 200
        data_with_rx = res_with_rx.json()
        assert data_with_rx["compliance_hold"] is False
        assert data_with_rx.get("compliance_warning") is None


@pytest.mark.anyio
async def test_cascade_5_stage_progression(auth_headers):
    """GET /api/v1/cascade/{correlation_id} returns all 5 stages in order."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Trigger a retail sale
        sale_res = await client.post(
            "/api/v1/events/sale",
            json={
                "event_id": "test-5-stage-cascade-trigger",
                "product_id": "p-001-pcm-650",
                "batch_number": "PCM-2026-B1",
                "quantity": 1,
                "node_id": "11111111-1111-1111-1111-111111111111",
                "channel": "mobile_pos",
            },
            headers=auth_headers,
        )
        corr_id = sale_res.json()["correlation_id"]

        cascade_res = await client.get(f"/api/v1/cascade/{corr_id}", headers=auth_headers)
        assert cascade_res.status_code == 200
        trace = cascade_res.json()
        assert trace["correlation_id"] == corr_id
        assert trace["status"] == "completed"
        assert len(trace["steps"]) == 5

        stages = [s["stage"] for s in trace["steps"]]
        expected_stages = ["supervisor", "pharmacy", "stockist", "distributor", "manufacturer"]
        assert stages == expected_stages


def test_printable_barcode_sheet_and_manifest_exist():
    """Verify barcode manifest, PNG sheet, and PDF sheet were generated."""
    repo_root = Path(__file__).resolve().parents[2]
    manifest_path = Path("fixtures/barcodes/barcodes_manifest.json")
    if not manifest_path.is_file():
        manifest_path = repo_root / "fixtures" / "barcodes" / "barcodes_manifest.json"
        sheet_png = repo_root / "fixtures" / "barcodes" / "printable_barcode_sheet.png"
        sheet_pdf = repo_root / "fixtures" / "barcodes" / "printable_barcode_sheet.pdf"
    else:
        sheet_png = Path("fixtures/barcodes/printable_barcode_sheet.png")
        sheet_pdf = Path("fixtures/barcodes/printable_barcode_sheet.pdf")

    assert manifest_path.is_file(), "barcodes_manifest.json missing"
    assert sheet_png.is_file(), "printable_barcode_sheet.png missing"
    assert sheet_pdf.is_file(), "printable_barcode_sheet.pdf missing"

    assert sheet_png.stat().st_size > 10000, "printable_barcode_sheet.png is too small"
    assert sheet_pdf.stat().st_size > 5000, "printable_barcode_sheet.pdf is too small"

    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)
    assert len(manifest) >= 20
    for item in manifest:
        assert "barcode" in item
        assert "sku" in item
        assert "name" in item
        ind_png = Path(item["image_path"])
        if not ind_png.is_file():
            ind_png = repo_root / item["image_path"]
        assert ind_png.is_file(), f"Individual barcode card missing: {ind_png}"
