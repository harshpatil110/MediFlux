"""Prescription ingestion, sovereign verification, and compliance API endpoints (Task 19 & Task 27)."""

import base64
import logging
import uuid
from pathlib import Path
from typing import Annotated, Any

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
    status,
)

from app.core.security import CurrentUser, get_current_user_optional
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
    request: Request,
    current_user: Annotated[CurrentUser | None, Depends(get_current_user_optional)] = None,
    node_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    """Retrieve scanned prescriptions list with privacy-preserving patient redaction and RLS scoping."""
    user_role = current_user.role if current_user else None
    user_node = current_user.node_id if current_user else None
    header_node = request.headers.get("X-Node-Id")

    effective_node = node_id or user_node or header_node
    items = list_prescriptions(limit=limit, node_id=effective_node, role=user_role)
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
    fixture_name: str | None = Form(None),  # noqa: B008
    fixture_hint: str | None = Form(None),  # noqa: B008
    current_user: Annotated[CurrentUser | None, Depends(get_current_user_optional)] = None,
) -> dict[str, Any]:
    """Ingest prescription scan via multipart form or JSON, verify compliance, and return structured result."""
    content_type = request.headers.get("content-type", "")

    img_bytes: bytes | None = None
    img_path: str | None = None
    img_b64: str | None = None
    resolved_fixture = fixture_name or fixture_hint
    target_node = (
        node_id
        or (current_user.node_id if current_user else None)
        or request.headers.get("X-Node-Id")
        or "11111111-1111-1111-1111-111111111111"
    )
    corr_id = correlation_id or str(uuid.uuid4())

    # 1. Handle JSON request body
    if "application/json" in content_type:
        try:
            body = await request.json()
            if isinstance(body, dict):
                img_path = body.get("image_path")
                img_b64 = body.get("image_base64")
                resolved_fixture = (
                    resolved_fixture
                    or body.get("fixture_name")
                    or body.get("fixture_id")
                    or body.get("fixture_hint")
                )
                target_node = (
                    body.get("node_id")
                    or (current_user.node_id if current_user else None)
                    or target_node
                )
                corr_id = body.get("correlation_id") or corr_id
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Invalid JSON body: {exc}") from exc

    # 2. Handle multipart file upload or fixture parameter
    elif file is not None:
        try:
            img_bytes = await file.read()
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Failed to read uploaded file: {exc}") from exc

    # 3. Resolve fixture if specified
    if resolved_fixture and not img_bytes:
        fname = resolved_fixture if resolved_fixture.endswith(".png") else f"{resolved_fixture}.png"
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

    # 4. Emit progress event for parsing
    try:
        await in_process_event_bus.publish(
            "prescription.progress",
            EventEnvelope(
                source="service:prescription_scanner",
                type="prescription.progress",
                data={
                    "stage": "parsing",
                    "status": "in_progress",
                    "correlation_id": corr_id,
                },
                node_id=target_node,
                correlation_id=corr_id,
            ),
        )
    except Exception as exc:
        logger.debug("Failed to emit prescription.progress event: %s", exc)

    # 5. Execute Sovereign Prescription Graph
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

    # 6. Emit prescription.scanned and prescription.completed events on event bus
    try:
        rx_id = str(result.get("prescription_id") or result.get("id"))
        ev = EventEnvelope(
            source="service:prescription_scanner",
            type="prescription.completed",
            data={
                "prescription_id": rx_id,
                "decision": result.get("decision"),
                "status": result.get("status"),
                "doctor_verified": result.get("doctor_verified"),
                "doctor_name": result.get("doctor_name"),
                "patient_initials": result.get("patient_initials"),
                "drugs": result.get("drugs", []),
                "steps": result.get("steps", []),
                "hitl_task_id": result.get("hitl_task_id"),
                "compliance_log_id": result.get("compliance_log_id"),
                "sensitivity": "sensitive",
            },
            node_id=target_node,
            correlation_id=corr_id,
        )
        await in_process_event_bus.publish("prescription.completed", ev)
        await in_process_event_bus.publish("prescription.scanned", ev)
    except Exception as exc:
        logger.debug("Failed to emit prescription.completed event: %s", exc)

    response.status_code = status.HTTP_201_CREATED
    return result


@router.get("/{prescription_id}", status_code=status.HTTP_200_OK)
async def get_prescription_by_id(
    prescription_id: str,
    request: Request,
    current_user: Annotated[CurrentUser | None, Depends(get_current_user_optional)] = None,
) -> dict[str, Any]:
    """Retrieve full prescription record and compliance evaluation by ID."""
    rx = get_prescription(prescription_id)
    if not rx:
        raise HTTPException(status_code=404, detail=f"Prescription '{prescription_id}' not found.")

    # RLS enforcement for pharmacy role
    if current_user and current_user.role and any(r in current_user.role.lower() for r in ("pharmacy", "pharmacist", "pic", "staff")):
        caller_node = current_user.node_id or request.headers.get("X-Node-Id")
        rx_node = rx.get("node_id")
        if caller_node and rx_node and str(caller_node) != str(rx_node):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access forbidden: Prescription belongs to a different pharmacy node.",
            )

    return rx
