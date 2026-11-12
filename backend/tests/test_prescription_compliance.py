"""Automated test suite for Task 19 Sovereign Prescription & Schedule H Compliance Graph."""

from pathlib import Path
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.agents.pharmacy_agent import PharmacyAgent
from app.core.audit_ledger import get_in_memory_audit_ledger
from app.core.hitl import clear_hitl_tasks, get_in_memory_hitl_tasks
from app.core.hitl_policy import clear_policy_cache
from app.graphs.prescription import (
    clear_prescription_store,
    run_prescription_graph,
)
from app.llm import llm_router
from app.llm.schemas import SensitiveDataRoutingError
from app.main import app
from app.tools.compliance_tools import lookup_schedule
from app.tools.pharmacy_tools import (
    check_prescription_link,
    clear_mock_inventory,
    set_mock_inventory,
)


def _get_rx_fixture_path(filename: str) -> Path:
    """Resolve prescription PNG fixture path across candidate roots."""
    candidates = [
        Path("fixtures/prescriptions") / filename,
        Path("backend/fixtures/prescriptions") / filename,
        Path("../fixtures/prescriptions") / filename,
    ]
    for c in candidates:
        if c.exists():
            return c
    raise FileNotFoundError(f"Prescription fixture '{filename}' not found.")


@pytest.fixture(autouse=True)
def clean_prescription_environment():
    """Isolate testing environment before and after every test."""
    clear_prescription_store()
    clear_hitl_tasks()
    clear_policy_cache()
    clear_mock_inventory()
    yield
    clear_prescription_store()
    clear_hitl_tasks()
    clear_policy_cache()
    clear_mock_inventory()


# -----------------------------------------------------------------------------
# 1. Acceptance Test: Valid Prescription -> Approved
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_valid_prescription_acceptance():
    """Upload valid_prescription.png and verify decision == approve_dispense, status == approved."""
    fix_path = _get_rx_fixture_path("valid_prescription.png")
    img_bytes = fix_path.read_bytes()

    result = await run_prescription_graph(image_bytes=img_bytes)

    assert result["status"] == "approved"
    assert result["decision"] == "approve_dispense"
    assert result["doctor_verified"] is True
    assert result["doctor_name"] == "Dr. A. K. Sharma"
    assert result["doctor_registration_no"] == "MCI-2019-88412"
    assert result["patient_initials"] == "R.K."
    assert result["hitl_task_id"] is None
    assert result["sensitivity"] == "sensitive"

    # Verify drug schedule classified as OTC (Paracetamol)
    drugs = result["drugs"]
    assert len(drugs) >= 1
    assert any("Paracetamol" in d["name"] and d["schedule_class"] == "OTC" for d in drugs)

    # Verify audit ledger write
    audit_entries = get_in_memory_audit_ledger()
    assert any(
        e.get("action") == "PRESCRIPTION_COMPLIANCE_EVALUATED" and e.get("entity_id") == result["id"]
        for e in audit_entries
    )


# -----------------------------------------------------------------------------
# 2. Acceptance Test: Schedule H Prescription -> Approved
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_schedule_h_prescription_acceptance():
    """Upload schedule_h_prescription.png and verify decision == approve_dispense, has_schedule_h == True."""
    fix_path = _get_rx_fixture_path("schedule_h_prescription.png")
    img_bytes = fix_path.read_bytes()

    result = await run_prescription_graph(image_bytes=img_bytes)

    assert result["status"] == "approved"
    assert result["decision"] == "approve_dispense"
    assert result["doctor_verified"] is True
    assert result["schedule_summary"]["has_schedule_h"] is True
    assert result["hitl_task_id"] is None

    # Verify Schedule H classification on Amoxicillin
    drugs = result["drugs"]
    amx = next(d for d in drugs if "Amoxicillin" in d["name"])
    assert amx["schedule_class"] == "H"
    assert amx["requires_prescription"] is True


# -----------------------------------------------------------------------------
# 3. Acceptance Test: Unknown Doctor -> Flagged & HITL Gate
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_unknown_doctor_flagged_and_hitl():
    """Upload unknown_doctor.png and verify decision == flag, status == flagged, and HITL task created."""
    fix_path = _get_rx_fixture_path("unknown_doctor.png")
    img_bytes = fix_path.read_bytes()

    result = await run_prescription_graph(image_bytes=img_bytes)

    assert result["status"] == "flagged"
    assert result["decision"] == "flag"
    assert result["doctor_verified"] is False
    assert result["hitl_task_id"] is not None

    # Verify HITL task registered in memory/db
    hitl_tasks = get_in_memory_hitl_tasks()
    task = next((t for t in hitl_tasks if t.get("id") == result["hitl_task_id"]), None)
    assert task is not None
    assert task.get("action_type") == "prescription_doctor_verification"


# -----------------------------------------------------------------------------
# 4. Acceptance Test: Missing Registration Number -> Rejected / Flagged
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_missing_reg_no_rejected():
    """Upload missing_reg_no.png and verify decision in ('reject', 'flag'), status in ('rejected', 'flagged')."""
    fix_path = _get_rx_fixture_path("missing_reg_no.png")
    img_bytes = fix_path.read_bytes()

    result = await run_prescription_graph(image_bytes=img_bytes)

    assert result["status"] in ("rejected", "flagged")
    assert result["decision"] in ("reject", "flag")
    assert result["doctor_verified"] is False
    assert result["doctor_registration_no"] is None


# -----------------------------------------------------------------------------
# 5. Acceptance Test: Unlisted Drug -> schedule_class == 'unknown' & HITL Gate
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_unlisted_drug_flagged_and_hitl():
    """Upload unlisted_drug.png and verify lookup_schedule reports unknown without guessing, and HITL created."""
    fix_path = _get_rx_fixture_path("unlisted_drug.png")
    img_bytes = fix_path.read_bytes()

    # Direct tool check: lookup_schedule MUST return "unknown"
    sch_tool_res = lookup_schedule("Xenorab-ZX 999mg")
    assert sch_tool_res["schedule_class"] == "unknown"
    assert sch_tool_res["matched"] is False

    result = await run_prescription_graph(image_bytes=img_bytes)

    assert result["status"] == "flagged"
    assert result["decision"] == "flag"
    assert result["schedule_summary"]["has_unknown"] is True
    assert result["hitl_task_id"] is not None

    # Verify HITL task type is prescription_unknown_drug
    hitl_tasks = get_in_memory_hitl_tasks()
    task = next((t for t in hitl_tasks if t.get("id") == result["hitl_task_id"]), None)
    assert task is not None
    assert task.get("action_type") == "prescription_unknown_drug"


# -----------------------------------------------------------------------------
# 6. Sovereign Local-Only Routing Guardrail Assertion
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_sovereign_local_only_routing():
    """Assert sensitivity='sensitive' is enforced and hosted cloud providers are NEVER invoked."""
    hosted_providers_called = []

    # Mock router complete to inspect passed sensitivity
    orig_complete = llm_router.complete

    async def mock_router_complete(*args, **kwargs):
        sensitivity = kwargs.get("sensitivity")
        assert sensitivity == "sensitive", "Prescription pipeline MUST pass sensitivity='sensitive'"
        # Ensure never calling hosted cloud
        for provider_name in ["openai", "anthropic", "gemini", "groq"]:
            if kwargs.get("provider") == provider_name:
                hosted_providers_called.append(provider_name)
        return await orig_complete(*args, **kwargs)

    with patch.object(llm_router, "complete", side_effect=mock_router_complete):
        fix_path = _get_rx_fixture_path("valid_prescription.png")
        res = await run_prescription_graph(image_path=str(fix_path))
        assert res["status"] == "approved"
        assert len(hosted_providers_called) == 0

    # Direct assertion: routing sensitive data to hosted providers raises SensitiveDataRoutingError
    with pytest.raises(SensitiveDataRoutingError):
        # Remove or break Ollama provider to verify it refuses fallback
        with patch.dict(llm_router.providers, {"ollama": None}):
            await llm_router.complete(
                agent="test_sensitive",
                messages=[{"role": "user", "content": "Patient details"}],
                response_model=dict,
                sensitivity="sensitive",
            )


# -----------------------------------------------------------------------------
# 7. Integration: Schedule H Sale Event Cascade with Task 11 check_prescription_link
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_schedule_h_sale_event_cascade_approved():
    """Verify that referencing an approved Task 19 prescription ID succeeds in Task 11 PharmacyAgent."""
    # 1. Ingest approved Schedule H prescription
    fix_path = _get_rx_fixture_path("schedule_h_prescription.png")
    rx_res = await run_prescription_graph(image_bytes=fix_path.read_bytes())
    assert rx_res["status"] == "approved"
    rx_id = rx_res["id"]

    # 2. Check check_prescription_link directly
    chk = await check_prescription_link(event_id="", prescription_ref=rx_id)
    assert chk["valid"] is True

    # 3. Simulate SaleEvent in PharmacyAgent referencing this prescription_id
    pharmacy_id = "11111111-1111-1111-1111-111111111111"
    product_id = "p-amoxicillin-500"
    set_mock_inventory(pharmacy_id, [{"product_id": product_id, "quantity": 5, "safety_stock": 10}])

    agent = PharmacyAgent()
    state = {
        "event_id": "evt-sale-rx-approved-01",
        "event_type": "pos.sale",
        "pharmacy_id": pharmacy_id,
        "product_id": product_id,
        "schedule_type": "Schedule H",
        "prescription_id": rx_id,
        "current_stock": 5,
        "event_payload": {
            "prescription_id": rx_id,
            "schedule_type": "Schedule H",
        },
    }

    result = await agent.run(state)
    # The prescription is approved, so compliance_hold MUST be False and replenishment triggered
    assert result.compliance_hold is False
    assert result.needed is True


@pytest.mark.asyncio
async def test_schedule_h_sale_event_cascade_blocked_on_flagged_rx():
    """Verify that referencing a flagged/unverified prescription ID triggers a compliance hold in PharmacyAgent."""
    # 1. Ingest unverified doctor prescription (flagged)
    fix_path = _get_rx_fixture_path("unknown_doctor.png")
    rx_res = await run_prescription_graph(image_bytes=fix_path.read_bytes())
    assert rx_res["status"] == "flagged"
    flagged_rx_id = rx_res["id"]

    # 2. Check check_prescription_link directly
    chk = await check_prescription_link(event_id="", prescription_ref=flagged_rx_id)
    assert chk["valid"] is False

    # 3. Simulate SaleEvent in PharmacyAgent referencing flagged prescription_id
    pharmacy_id = "11111111-1111-1111-1111-111111111111"
    product_id = "p-amoxicillin-500"
    agent = PharmacyAgent()
    state = {
        "event_id": "evt-sale-rx-flagged-01",
        "event_type": "pos.sale",
        "pharmacy_id": pharmacy_id,
        "product_id": product_id,
        "schedule_type": "Schedule H",
        "prescription_id": flagged_rx_id,
        "current_stock": 5,
        "event_payload": {
            "prescription_id": flagged_rx_id,
            "schedule_type": "Schedule H",
        },
    }

    result = await agent.run(state)
    # Blocked: compliance_hold MUST be True
    assert result.compliance_hold is True
    assert result.needed is False
    assert "compliance hold" in result.reason.lower()


# -----------------------------------------------------------------------------
# 8. API Endpoints Test (Multipart Upload, JSON, GET Prescription & Logs)
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_prescription_api_endpoints():
    """Verify POST /api/v1/prescriptions (multipart & JSON), GET /{id}, and GET /api/v1/compliance/logs."""
    fix_path = _get_rx_fixture_path("valid_prescription.png")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # A. Multipart Upload
        with open(fix_path, "rb") as f:
            files = {"file": ("valid_prescription.png", f, "image/png")}
            res = await client.post("/api/v1/prescriptions", files=files)
            assert res.status_code == 201
            data = res.json()
            assert data["status"] == "approved"
            assert data["decision"] == "approve_dispense"
            rx_id = data["id"]

        # B. GET /api/v1/prescriptions/{id}
        get_res = await client.get(f"/api/v1/prescriptions/{rx_id}")
        assert get_res.status_code == 200
        rx_data = get_res.json()
        assert rx_data["id"] == rx_id
        assert rx_data["doctor_name"] == "Dr. A. K. Sharma"

        # C. JSON body upload with image_path
        json_res = await client.post(
            "/api/v1/prescriptions",
            json={"image_path": str(fix_path), "node_id": "11111111-1111-1111-1111-111111111111"},
        )
        assert json_res.status_code == 201
        json_data = json_res.json()
        assert json_data["status"] == "approved"

        # D. GET /api/v1/compliance/logs
        logs_res = await client.get(f"/api/v1/compliance/logs?prescription_id={rx_id}")
        assert logs_res.status_code == 200
        logs = logs_res.json()
        assert len(logs) >= 1
        assert logs[0]["prescription_id"] == rx_id
        assert logs[0]["action"] == "approve_dispense"
