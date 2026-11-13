"""Prescription ingestion, sovereign verification, and compliance API endpoints (Task 19 & Task 27)."""

import base64
import logging
from pathlib import Path
from typing import Any

from fastapi import (
    APIRouter,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
    status,
)

from app.events.bus import in_process_event_bus
from app.events.models import EventEnvelope
from app.graphs.prescription import get_prescription, list_prescriptions, run_prescription_graph

logger = logging.getLogger("mediflux.api.prescriptions")

router = APIRouter(prefix="/prescriptions", tags=["Prescriptions"])

FIXTURE_METADATA: dict[str, dict[str, Any]] = {
    "valid_prescription.png": {
        "id": "valid_prescription",
        "filename": "valid_prescription.png",
        "label": "Valid Standard Rx",
        "doctor_name": "Dr. A. K. Sharma",
        "reg_no": "MCI-2019-88412",
        "description": "Standard prescription with Paracetamol & Cetirizine (OTC). Physician verified in registry.",
        "category": "standard_otc",
        "expected_verdict": "APPROVE DISPENSE",
        "expected_status": "approved",
    },
    "schedule_h_prescription.png": {
        "id": "schedule_h_prescription",
        "filename": "schedule_h_prescription.png",
        "label": "Schedule H Antibiotic Rx",
        "doctor_name": "Dr. Priya Nair",
        "reg_no": "DMC-55102",
        "description": "Prescription with Amoxicillin 500mg (Schedule H). Validated doctor; statutory Rx registry entry logged.",
        "category": "schedule_h",
        "expected_verdict": "APPROVE DISPENSE",
        "expected_status": "approved",
    },
    "unknown_doctor.png": {
        "id": "unknown_doctor",
        "filename": "unknown_doctor.png",
        "label": "Unknown Physician Rx",
        "doctor_name": "Dr. Dev Anand",
        "reg_no": "UNKNOWN-REG",
        "description": "Physician credentials not found in CDSCO / State Registry. Autonomous HITL review task triggered.",
        "category": "unverified_doctor",
        "expected_verdict": "FLAGGED FOR HITL REVIEW",
        "expected_status": "flagged",
    },
    "missing_reg_no.png": {
        "id": "missing_reg_no",
        "filename": "missing_reg_no.png",
        "label": "Missing Reg Number Rx",
        "doctor_name": "Dr. R. Verma",
        "reg_no": "MISSING",
        "description": "Prescription scan missing state medical council registration number. Routed to pharmacist inbox.",
        "category": "missing_credential",
        "expected_verdict": "FLAGGED FOR HITL REVIEW",
        "expected_status": "flagged",
    },
    "unlisted_drug.png": {
        "id": "unlisted_drug",
        "filename": "unlisted_drug.png",
        "label": "Unlisted Formulation Rx",
        "doctor_name": "Dr. Sneha Patel",
        "reg_no": "KMC-48291",
        "description": "Unlisted active pharmaceutical entity absent from CDSCO schedule database. Dual verification gate opened.",
        "category": "unlisted_chemical",
        "expected_verdict": "FLAGGED FOR HITL REVIEW",
        "expected_status": "flagged",
    },
}


def _resolve_fixture_path(filename: str) -> Path:
    """Safely resolve fixture path across standard project directories."""
    clean_name = Path(filename).name
    candidates = [
        Path("fixtures/prescriptions") / clean_name,
        Path("backend/fixtures/prescriptions") / clean_name,
        Path("../fixtures/prescriptions") / clean_name,
    ]
    for c in candidates:
        if c.exists():
            return c
    raise FileNotFoundError(f"Prescription fixture '{clean_name}' not found.")


@router.get("", status_code=status.HTTP_200_OK)
async def list_prescriptions_endpoint(
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    """Retrieve scanned prescriptions list with privacy-preserving patient redaction."""
    items = list_prescriptions(limit=limit)
    return {
        "prescriptions": items,
        "total": len(items),
    }


@router.get("/fixtures", status_code=status.HTTP_200_OK)
async def get_prescription_fixtures() -> list[dict[str, Any]]:
    """Retrieve synthetic prescription fixtures with base64 data URIs for 1-click preview and testing."""
    fixtures_list: list[dict[str, Any]] = []

    for filename, meta in FIXTURE_METADATA.items():
        data_uri: str | None = None
        try:
            fpath = _resolve_fixture_path(filename)
            b64_content = base64.b64encode(fpath.read_bytes()).decode("utf-8")
            data_uri = f"data:image/png;base64,{b64_content}"
        except Exception as exc:
            logger.debug("Could not read fixture %s: %s", filename, exc)

        fixtures_list.append({
            **meta,
            "data_uri": data_uri,
        })

    return fixtures_list


@router.post("", status_code=status.HTTP_201_CREATED)
async def upload_prescription(
    request: Request,
    response: Response,
    file: UploadFile | None = File(None),  # noqa: B008
    node_id: str | None = Form(None),  # noqa: B008
    correlation_id: str | None = Form(None),  # noqa: B008
) -> dict[str, Any]:
    """Ingest prescription scan via multipart form or JSON, verify compliance, and return structured result."""
    content_type = request.headers.get("content-type", "")

    img_bytes: bytes | None = None
    img_path: str | None = None
    img_b64: str | None = None
    fixture_name: str | None = None
    target_node = node_id
    corr_id = correlation_id

    # 1. Handle JSON request body
    if "application/json" in content_type:
        try:
            body = await request.json()
            if isinstance(body, dict):
                img_path = body.get("image_path")
                img_b64 = body.get("image_base64")
                fixture_name = body.get("fixture_name") or body.get("fixture_id")
                target_node = target_node or body.get("node_id")
                corr_id = corr_id or body.get("correlation_id")
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Invalid JSON body: {exc}") from exc

    # 2. Handle multipart file upload or fixture parameter
    elif file is not None:
        try:
            img_bytes = await file.read()
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Failed to read uploaded file: {exc}") from exc

    # 3. Resolve fixture if specified
    if fixture_name and not img_bytes:
        fname = fixture_name if fixture_name.endswith(".png") else f"{fixture_name}.png"
        try:
            fpath = _resolve_fixture_path(fname)
            img_bytes = fpath.read_bytes()
            img_path = str(fpath)
        except Exception as exc:
            raise HTTPException(status_code=404, detail=f"Fixture not found: {exc}") from exc

    if not img_bytes and not img_path and not img_b64:
        raise HTTPException(
            status_code=400,
            detail="Must provide an image file upload, fixture_name, image_path, or image_base64 payload.",
        )

    # 4. Execute Sovereign Prescription Graph
    try:
        result = await run_prescription_graph(
            image_bytes=img_bytes,
            image_path=img_path,
            image_base64=img_b64,
            node_id=target_node,
            correlation_id=corr_id,
        )
    except Exception as exc:
        logger.error("Prescription graph execution failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Prescription verification failed: {exc}") from exc

    # 5. Emit prescription.scanned event on event bus
    try:
        rx_id = str(result.get("prescription_id") or result.get("id"))
        ev = EventEnvelope(
            source="service:prescription_scanner",
            type="prescription.scanned",
            data={
                "prescription_id": rx_id,
                "decision": result.get("decision"),
                "status": result.get("status"),
                "doctor_verified": result.get("doctor_verified"),
                "doctor_name": result.get("doctor_name"),
                "patient_initials": result.get("patient_initials"),
                "drugs": result.get("drugs", []),
                "sensitivity": "sensitive",
            },
            correlation_id=corr_id,
        )
        await in_process_event_bus.publish("prescription.scanned", ev)
    except Exception as exc:
        logger.debug("Failed to emit prescription.scanned event: %s", exc)

    response.status_code = status.HTTP_201_CREATED
    return result


@router.get("/{prescription_id}", status_code=status.HTTP_200_OK)
async def get_prescription_by_id(prescription_id: str) -> dict[str, Any]:
    """Retrieve full prescription record and compliance evaluation by ID."""
    rx = get_prescription(prescription_id)
    if not rx:
        raise HTTPException(status_code=404, detail=f"Prescription '{prescription_id}' not found.")
    return rx
