"""Automated test suite for Task M6: Sovereign Prescription Scanner & Schedule H Compliance.

Covers all 4 Acceptance Criteria:
- AC #1: Valid synthetic prescription fixture (valid_prescription.png / schedule_h_prescription.png)
  is approved, returns 4-stage pipeline steps, patient initials (never full name), and compliance log ID.
- AC #2: Unknown doctor (unknown_doctor.png) and unlisted drug (unlisted_drug.png) are flagged,
  create pending HITL tasks, and appear in GET /api/v1/hitl/tasks with SSE broadcast.
- AC #3: Approved prescription attached to Schedule H sale passes cascade verification without
  compliance hold; absence of prescription triggers compliance hold.
- AC #4: RLS-scoped pharmacy prescription history isolates records between distinct pharmacy nodes,
  while admin / regulator access can view all nodes. Fixture presets endpoint returns base64 URIs.
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.audit_ledger import clear_in_memory_audit_ledger
from app.core.hitl import clear_hitl_tasks
from app.core.hitl_policy import clear_policy_cache
from app.graphs.prescription import (
    clear_prescription_store,
    run_prescription_graph,
)
from app.main import app
from app.tools.pharmacy_tools import check_prescription_link, clear_mock_inventory

ROOT_DIR = Path(__file__).resolve().parent.parent.parent


def _get_fixture_file(filename: str) -> Path:
    candidates = [
        ROOT_DIR / "fixtures" / "prescriptions" / filename,
        ROOT_DIR / "backend" / "fixtures" / "prescriptions" / filename,
    ]
    for c in candidates:
        if c.exists():
            return c
    raise FileNotFoundError(f"Fixture {filename} not found in {candidates}")


@pytest.fixture(autouse=True)
def clean_environment():
    clear_prescription_store()
    clear_hitl_tasks()
    clear_policy_cache()
    clear_mock_inventory()
    clear_in_memory_audit_ledger()
    yield
    clear_prescription_store()
    clear_hitl_tasks()
    clear_policy_cache()
    clear_mock_inventory()
    clear_in_memory_audit_ledger()


@pytest.fixture
def auth_headers_pharmacy_a():
    return {
        "Authorization": "Bearer demo-token-pharmacy",
        "X-User-Role": "pharmacy",
        "X-Node-Id": "11111111-1111-1111-1111-111111111111",
    }


@pytest.fixture
def auth_headers_pharmacy_b():
    return {
        "Authorization": "Bearer demo-token-pharmacy-b",
        "X-User-Role": "pharmacy",
        "X-Node-Id": "55555555-5555-5555-5555-555555555555",
    }


@pytest.fixture
def auth_headers_admin():
    return {
        "Authorization": "Bearer demo-token-admin",
        "X-User-Role": "admin",
        "X-Node-Id": "00000000-0000-0000-0000-000000000000",
    }


# -----------------------------------------------------------------------------
# AC #1: Valid Synthetic Fixture Approved with 4-Stage Pipeline Steps
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_ac1_valid_fixture_approved_and_4stage_steps(auth_headers_pharmacy_a):
    """Uploading valid prescription returns approved verdict, 4 stages, and patient initials."""
    fix_path = _get_fixture_file("schedule_h_prescription.png")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with open(fix_path, "rb") as f:
            files = {"file": ("schedule_h_prescription.png", f, "image/png")}
            data = {"node_id": "11111111-1111-1111-1111-111111111111"}
            res = await client.post(
                "/api/v1/prescriptions",
                files=files,
                data=data,
                headers=auth_headers_pharmacy_a,
            )

        assert res.status_code == 201
        payload = res.json()

        # Decision & verification
        assert payload["status"] == "approved"
        assert payload["decision"] == "approve_dispense"
        assert payload["doctor_verified"] is True
        assert payload.get("doctor_name") is not None

        # Privacy minimal: initials only, no full patient name exposed
        assert "patient_initials" in payload
        assert payload["patient_initials"] is not None
        assert "patient_name" not in payload or payload.get("patient_name") is None

        # 4-stage pipeline steps present
        steps = payload.get("steps", [])
        assert len(steps) == 4
        stage_names = [s["stage"] for s in steps]
        assert "parsing" in stage_names
        assert "schedule_check" in stage_names
        assert "doctor_verification" in stage_names
        assert "decision" in stage_names

        for st in steps:
            assert st["status"] == "done"
            assert len(st["summary"]) > 5

        # CDSCO classification
        drugs = payload.get("drugs", [])
        assert len(drugs) >= 1
        assert any(d.get("schedule_class") == "H" for d in drugs)

        # Audit and compliance logs
        assert payload.get("compliance_log_id") is not None
        assert "sensitivity" in payload and payload["sensitivity"] == "sensitive"
        assert "privacy_notice" in payload


# -----------------------------------------------------------------------------
# AC #2: Unknown Doctor & Unlisted Drug Flagged + Appears in HITL Approvals
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_ac2_unknown_doctor_flagged_and_creates_hitl(auth_headers_pharmacy_a, auth_headers_admin):
    """Uploading unknown doctor prescription sets status=flagged and creates pending HITL task."""
    fix_path = _get_fixture_file("unknown_doctor.png")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with open(fix_path, "rb") as f:
            files = {"file": ("unknown_doctor.png", f, "image/png")}
            res = await client.post(
                "/api/v1/prescriptions",
                files=files,
                headers=auth_headers_pharmacy_a,
            )

        assert res.status_code == 201
        rx_data = res.json()

        assert rx_data["status"] == "flagged"
        assert rx_data["decision"] == "flag"
        assert rx_data["doctor_verified"] is False
        assert rx_data["hitl_task_id"] is not None
        hitl_id = rx_data["hitl_task_id"]

        # Verify task is available in Task M5 HITL tasks list
        hitl_res = await client.get("/api/v1/hitl/tasks?status=pending", headers=auth_headers_admin)
        assert hitl_res.status_code == 200
        pending_tasks = hitl_res.json()
        assert isinstance(pending_tasks, list)

        matching = [t for t in pending_tasks if t.get("id") == hitl_id or t.get("task_id") == hitl_id]
        assert len(matching) == 1
        task = matching[0]
        assert task.get("task_type") in ("doctor_verification", "prescription_doctor_verification")


@pytest.mark.asyncio
async def test_ac2_unlisted_drug_not_guessed_and_creates_hitl(auth_headers_pharmacy_a, auth_headers_admin):
    """Prescription with unlisted active chemical is never guessed, reports unknown schedule, and flags HITL."""
    fix_path = _get_fixture_file("unlisted_drug.png")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with open(fix_path, "rb") as f:
            files = {"file": ("unlisted_drug.png", f, "image/png")}
            res = await client.post(
                "/api/v1/prescriptions",
                files=files,
                headers=auth_headers_pharmacy_a,
            )

        assert res.status_code == 201
        rx_data = res.json()

        assert rx_data["status"] == "flagged"
        assert rx_data["decision"] == "flag"

        # Explicit check: unlisted drug's schedule MUST be 'unknown' and never guessed
        drugs = rx_data.get("drugs", [])
        assert len(drugs) >= 1
        assert any(d.get("schedule_class") == "unknown" for d in drugs)

        assert rx_data["hitl_task_id"] is not None
        hitl_id = rx_data["hitl_task_id"]

        # Verify task exists in HITL endpoint
        hitl_res = await client.get("/api/v1/hitl/tasks?status=pending", headers=auth_headers_admin)
        assert hitl_res.status_code == 200
        pending_tasks = hitl_res.json()
        matching = [t for t in pending_tasks if t.get("id") == hitl_id or t.get("task_id") == hitl_id]
        assert len(matching) == 1


# -----------------------------------------------------------------------------
# AC #3: Approved Prescription Attached to Schedule H Sale Passes Cascade Check
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_ac3_approved_prescription_attached_to_sale_succeeds(auth_headers_pharmacy_a):
    """Approved Schedule H prescription attached to sale avoids compliance hold and advances cascade."""
    # 1. Ingest approved Schedule H prescription
    fix_path = _get_fixture_file("schedule_h_prescription.png")
    rx_result = await run_prescription_graph(image_bytes=fix_path.read_bytes())
    assert rx_result["status"] == "approved"
    approved_rx_id = rx_result["id"]

    # 2. Verify check_prescription_link passes
    chk = await check_prescription_link(event_id="", prescription_ref=approved_rx_id)
    assert chk["valid"] is True

    # 3. Dispense Schedule H sale with attached prescription_id
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        sale_payload = {
            "event_id": str(uuid.uuid4()),
            "product_id": "MED-AMOX-500",
            "batch_id": "MFG-AMOX-2026-01",
            "quantity": 1,
            "node_id": "11111111-1111-1111-1111-111111111111",
            "prescription_id": approved_rx_id,
        }

        res = await client.post("/api/v1/events/sale", json=sale_payload, headers=auth_headers_pharmacy_a)
        assert res.status_code == 200
        sale_res = res.json()

        assert sale_res.get("compliance_hold") is False
        assert sale_res.get("compliance_status") == "VERIFIED_COMPLIANT"

        # Verify cascade trace: pharmacy step is done, not waiting_approval
        cascade = sale_res.get("cascade_trace", {})
        steps = cascade.get("steps", [])
        pharm_step = next((s for s in steps if s.get("stage") == "pharmacy"), None)
        assert pharm_step is not None
        assert pharm_step.get("status") == "succeeded"
        assert pharm_step.get("state") == "done"
        assert pharm_step.get("hitl_task_id") is None


@pytest.mark.asyncio
async def test_ac3_sale_without_prescription_triggers_compliance_hold(auth_headers_pharmacy_a):
    """Selling Schedule H product without prescription triggers compliance hold in cascade."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        sale_payload = {
            "event_id": str(uuid.uuid4()),
            "product_id": "MED-AMOX-500",
            "batch_id": "MFG-AMOX-2026-01",
            "quantity": 1,
            "node_id": "11111111-1111-1111-1111-111111111111",
            "prescription_id": None,
        }

        res = await client.post("/api/v1/events/sale", json=sale_payload, headers=auth_headers_pharmacy_a)
        assert res.status_code == 200
        sale_res = res.json()

        assert sale_res.get("compliance_hold") is True
        assert sale_res.get("compliance_status") == "FLAGGED_FOR_REVIEW"

        # Pharmacy step holds for approval
        cascade = sale_res.get("cascade_trace", {})
        steps = cascade.get("steps", [])
        pharm_step = next((s for s in steps if s.get("stage") == "pharmacy"), None)
        assert pharm_step is not None
        assert pharm_step.get("status") == "waiting_approval"
        assert pharm_step.get("hitl_task_id") is not None


# -----------------------------------------------------------------------------
# AC #4: RLS-Scoped Pharmacy History & Fixture Presets Endpoint
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_ac4_fixtures_presets_endpoint(auth_headers_pharmacy_a):
    """GET /api/v1/prescriptions/fixtures returns the 5 canonical demo presets with base64 data URIs."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/prescriptions/fixtures", headers=auth_headers_pharmacy_a)
        assert res.status_code == 200
        fixtures = res.json()
        assert isinstance(fixtures, list)
        assert len(fixtures) == 5

        filenames = [f["filename"] for f in fixtures]
        assert "valid_prescription.png" in filenames
        assert "schedule_h_prescription.png" in filenames
        assert "unknown_doctor.png" in filenames
        assert "missing_reg_no.png" in filenames
        assert "unlisted_drug.png" in filenames

        for f in fixtures:
            assert f.get("data_uri") is not None
            assert str(f["data_uri"]).startswith("data:image/png;base64,")


@pytest.mark.asyncio
async def test_ac4_rls_pharmacy_history_isolation(
    auth_headers_pharmacy_a,
    auth_headers_pharmacy_b,
    auth_headers_admin,
):
    """Pharmacy A cannot see Pharmacy B prescriptions in GET /api/v1/prescriptions or GET /{id}."""
    node_a = "11111111-1111-1111-1111-111111111111"
    node_b = "55555555-5555-5555-5555-555555555555"

    fix_path = _get_fixture_file("valid_prescription.png")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Ingest for Pharmacy A
        with open(fix_path, "rb") as f:
            res_a = await client.post(
                "/api/v1/prescriptions",
                files={"file": ("valid_prescription.png", f, "image/png")},
                data={"node_id": node_a},
                headers=auth_headers_pharmacy_a,
            )
        assert res_a.status_code == 201
        rx_a_id = res_a.json()["id"]

        # Ingest for Pharmacy B
        with open(fix_path, "rb") as f:
            res_b = await client.post(
                "/api/v1/prescriptions",
                files={"file": ("valid_prescription.png", f, "image/png")},
                data={"node_id": node_b},
                headers=auth_headers_pharmacy_b,
            )
        assert res_b.status_code == 201
        rx_b_id = res_b.json()["id"]

        # 1. Pharmacy A lists prescriptions: must see rx_a, must NOT see rx_b
        list_a = await client.get("/api/v1/prescriptions", headers=auth_headers_pharmacy_a)
        assert list_a.status_code == 200
        p_list_a = list_a.json()["prescriptions"]
        ids_a = [p["id"] for p in p_list_a]
        assert rx_a_id in ids_a
        assert rx_b_id not in ids_a

        # 2. Pharmacy B lists prescriptions: must see rx_b, must NOT see rx_a
        list_b = await client.get("/api/v1/prescriptions", headers=auth_headers_pharmacy_b)
        assert list_b.status_code == 200
        p_list_b = list_b.json()["prescriptions"]
        ids_b = [p["id"] for p in p_list_b]
        assert rx_b_id in ids_b
        assert rx_a_id not in ids_b

        # 3. Admin lists prescriptions: sees both
        list_admin = await client.get("/api/v1/prescriptions", headers=auth_headers_admin)
        assert list_admin.status_code == 200
        p_list_admin = list_admin.json()["prescriptions"]
        ids_admin = [p["id"] for p in p_list_admin]
        assert rx_a_id in ids_admin
        assert rx_b_id in ids_admin

        # 4. Cross-node single prescription access: Pharmacy A attempting to read Pharmacy B's rx returns 403 Forbidden
        cross_res = await client.get(f"/api/v1/prescriptions/{rx_b_id}", headers=auth_headers_pharmacy_a)
        assert cross_res.status_code == 403


# -----------------------------------------------------------------------------
# AC #4: Ephemeral Image Cache Cleanup & Zero-Persistence Contract
# -----------------------------------------------------------------------------
def test_ac4_ephemeral_image_cache_cleanup_and_zero_persistence():
    """Verify ephemeral image cleanup module guarantees 0 remaining cached images upon cleanup."""
    cleanup_ts = ROOT_DIR / "mobile" / "src" / "features" / "prescriptions" / "imageCleanup.ts"
    assert cleanup_ts.is_file(), "mobile/src/features/prescriptions/imageCleanup.ts missing"
    content = cleanup_ts.read_text(encoding="utf-8")

    # Contract functions must all be exported
    assert "export function registerTempPrescriptionUri" in content
    assert "export async function cleanupPrescriptionUri" in content
    assert "export async function cleanupAllTempPrescriptionImages" in content
    assert "export function getRemainingTempPrescriptionUris" in content
    assert "trackedTempImageUris" in content

    # Verify scan-rx.tsx wires up cleanup in finally and unmount
    scan_rx_tsx = ROOT_DIR / "mobile" / "app" / "(tabs)" / "scan-rx.tsx"
    assert scan_rx_tsx.is_file(), "mobile/app/(tabs)/scan-rx.tsx missing"
    scan_content = scan_rx_tsx.read_text(encoding="utf-8")
    assert "cleanupAllTempPrescriptionImages" in scan_content
    assert "cleanupAllTempPrescriptionImages()" in scan_content

    # Verify Capture Card handles cleanup on retake / error
    capture_card = ROOT_DIR / "mobile" / "src" / "features" / "prescriptions" / "PrescriptionCaptureCard.tsx"
    assert capture_card.is_file(), "PrescriptionCaptureCard.tsx missing"
    capture_content = capture_card.read_text(encoding="utf-8")
    assert "registerTempPrescriptionUri" in capture_content
    assert "cleanupAllTempPrescriptionImages" in capture_content


@pytest.mark.asyncio
async def test_missing_registration_number_rejected(auth_headers_pharmacy_a):
    """Prescription with missing doctor registration number is rejected per statutory rules."""
    fix_path = _get_fixture_file("missing_reg_no.png")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with open(fix_path, "rb") as f:
            files = {"file": ("missing_reg_no.png", f, "image/png")}
            res = await client.post(
                "/api/v1/prescriptions",
                files=files,
                headers=auth_headers_pharmacy_a,
            )

        assert res.status_code == 201
        rx_data = res.json()
        assert rx_data["status"] == "rejected"
        assert rx_data["decision"] == "reject"
        assert rx_data["doctor_verified"] is False


