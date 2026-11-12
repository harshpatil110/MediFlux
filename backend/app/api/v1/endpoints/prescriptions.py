"""Prescription ingestion and verification API endpoints (Task 19)."""

import logging
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, Request, Response, UploadFile, status

from app.graphs.prescription import get_prescription, run_prescription_graph

logger = logging.getLogger("mediflux.api.prescriptions")

router = APIRouter(prefix="/prescriptions", tags=["Prescriptions"])


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
    target_node = node_id
    corr_id = correlation_id

    # 1. Handle JSON request body
    if "application/json" in content_type:
        try:
            body = await request.json()
            if isinstance(body, dict):
                img_path = body.get("image_path")
                img_b64 = body.get("image_base64")
                target_node = target_node or body.get("node_id")
                corr_id = corr_id or body.get("correlation_id")
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Invalid JSON body: {exc}") from exc

    # 2. Handle multipart file upload
    elif file is not None:
        try:
            img_bytes = await file.read()
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Failed to read uploaded file: {exc}") from exc

    if not img_bytes and not img_path and not img_b64:
        raise HTTPException(
            status_code=400,
            detail="Must provide an image file upload, image_path, or image_base64 payload.",
        )

    # 3. Execute Sovereign Prescription Graph
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

    response.status_code = status.HTTP_201_CREATED
    return result


@router.get("/{prescription_id}", status_code=status.HTTP_200_OK)
async def get_prescription_by_id(prescription_id: str) -> dict[str, Any]:
    """Retrieve full prescription record and compliance evaluation by ID."""
    rx = get_prescription(prescription_id)
    if not rx:
        raise HTTPException(status_code=404, detail=f"Prescription '{prescription_id}' not found.")
    return rx
