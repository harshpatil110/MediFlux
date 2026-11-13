"""Adapter Marketplace API and real-time generation SSE streaming (Task 17)."""

import json
import logging
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from app.core.security import get_actor
from app.graphs.forge import (
    get_adapter,
    get_forge_job,
    list_adapter_versions,
    list_adapters,
    rollback_adapter,
    run_forge,
)

logger = logging.getLogger("mediflux.api.v1.adapters")

router = APIRouter(prefix="/adapters", tags=["Adapter Forge & Marketplace"])


# -----------------------------------------------------------------------------
# Request & Response Schemas
# -----------------------------------------------------------------------------
class GenerateAdapterRequest(BaseModel):
    """Payload to trigger autonomous adapter synthesis and testing."""

    name: str = Field(..., description="Unique alphanumeric identifier for the adapter module")
    sample_payload: Any = Field(..., description="Raw legacy sample payload (CSV text, XML string, or JSON dict/list)")
    expected_output: dict[str, Any] | None = Field(default=None, description="Optional target canonical dictionary")
    description: str | None = Field(default=None, description="Human-readable description of source system")
    target_schema: str = Field(default="SaleEvent", description="Target canonical schema ('SaleEvent' or 'BatchUpdate')")
    max_attempts: int = Field(default=4, ge=1, le=10, description="Maximum self-healing retry iterations")
    injected_bad_code: str | None = Field(default=None, description="Test hook for guard violation verification")


class RollbackAdapterRequest(BaseModel):
    """Payload to revert an adapter to a prior version."""

    target_version: int | None = Field(default=None, description="Specific target version to restore")


# -----------------------------------------------------------------------------
# Endpoints
# -----------------------------------------------------------------------------
@router.post(
    "/generate",
    summary="Trigger Autonomous Adapter Generation Workflow",
    description="Launches the multi-agent Forge Graph to inspect legacy payloads, write guard-compliant adapter code, test, and register.",
    status_code=status.HTTP_202_ACCEPTED,
)
async def generate_adapter(
    payload: GenerateAdapterRequest,
    x_api_key: str | None = Header(None, alias="X-API-Key"),
) -> dict[str, Any]:
    """Execute Adapter Forge synthesis and testing graph."""
    if x_api_key:
        actor = await get_actor(x_api_key=x_api_key)
        scopes = actor.scopes
        if "*" not in scopes and "all" not in scopes and "manage:adapters" not in scopes:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient API key scope. Required: 'manage:adapters'",
            )

    job_id = str(uuid.uuid4())
    logger.info("Initiating adapter generation job: %s for '%s'", job_id, payload.name)

    state = await run_forge(
        name=payload.name,
        raw_sample=payload.sample_payload,
        expected_output=payload.expected_output,
        description=payload.description,
        target_schema=payload.target_schema,
        max_attempts=payload.max_attempts,
        job_id=job_id,
        injected_bad_code=payload.injected_bad_code,
    )

    return {
        "job_id": job_id,
        "name": payload.name,
        "status": state.get("status", "unknown"),
        "adapter_id": state.get("adapter_id"),
        "version": state.get("version"),
        "error_logs": state.get("error_logs", []),
    }


@router.get(
    "/jobs/{job_id}",
    summary="Get Forge Job Status or SSE Stream",
    description="Returns JSON status or streams Server-Sent Events based on content negotiation (Accept header).",
)
async def get_job_status(job_id: str, request: Request) -> Any:
    """Retrieve job details or stream progress over Server-Sent Events."""
    job = get_forge_job(job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Forge job '{job_id}' not found.")

    accept_header = request.headers.get("accept", "")
    if "text/event-stream" in accept_header:
        return await stream_job_events(job_id)

    return {
        "job_id": job_id,
        "adapter_name": job.get("adapter_name"),
        "status": job.get("status"),
        "adapter_id": job.get("adapter_id"),
        "version": job.get("version"),
        "events": job.get("events", []),
        "test_results": job.get("test_results"),
        "error_logs": job.get("error_logs", []),
    }


@router.get(
    "/jobs/{job_id}/stream",
    summary="Real-Time Forge SSE Progress Stream",
    description="Streams each agent step (inspecting, coding, testing, fixing, registered, failed) in real time.",
)
async def stream_job_events(job_id: str) -> EventSourceResponse:
    """Stream live agent step events using Server-Sent Events."""
    job = get_forge_job(job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Forge job '{job_id}' not found.")

    async def event_generator():
        current_job = get_forge_job(job_id) or {}
        events = list(current_job.get("events", []))
        for ev in events:
            yield {
                "event": ev.get("step", "progress"),
                "data": json.dumps(ev),
            }
        # Yield terminal event
        yield {
            "event": "done",
            "data": json.dumps({
                "job_id": job_id,
                "status": current_job.get("status"),
                "adapter_id": current_job.get("adapter_id"),
                "version": current_job.get("version"),
            }),
        }

    return EventSourceResponse(event_generator())


@router.get(
    "/fixtures",
    summary="Get Pre-packaged Legacy Format Fixtures for Quick 1-Click Synthesis",
    description="Returns pre-loaded CSV, XML, and nested JSON payloads and target schemas for UI demonstration.",
)
async def get_adapter_fixtures() -> list[dict[str, Any]]:
    """Retrieve pre-packaged sample fixtures from fixtures/legacy directory."""
    fixtures_dir = Path(__file__).resolve().parents[4] / "fixtures" / "legacy"
    if not fixtures_dir.exists():
        fixtures_dir = Path("fixtures/legacy")

    # 1. Pharmacy Billing CSV
    csv_sample = "BILL_NO,STORE_CODE,DRUG_SKU,BATCH_NUM,QTY_SOLD,UNIT_MRP,TXN_DATE\nINV-2026-9081,PHARM-BLR-001,PARA-500,BATCH-2026-X1,2,45.50,14/11/2026 10:30"
    csv_expected = {
        "pharmacy_id": "PHARM-BLR-001",
        "product_id": "PARA-500",
        "batch_id": "BATCH-2026-X1",
        "quantity": 2,
        "source": "pos",
    }
    csv_file = fixtures_dir / "pharmacy_billing_sample.csv"
    if csv_file.exists():
        try:
            csv_sample = csv_file.read_text(encoding="utf-8")
        except Exception as e:
            logger.debug("Failed reading csv sample: %s", e)
    csv_exp_file = fixtures_dir / "pharmacy_billing_expected.json"
    if csv_exp_file.exists():
        try:
            csv_expected = json.loads(csv_exp_file.read_text(encoding="utf-8"))
        except Exception as e:
            logger.debug("Failed reading csv expected: %s", e)

    # 2. Manufacturer ERP XML
    xml_sample = """<?xml version="1.0" encoding="UTF-8"?>
<DispatchNotice>
    <Header>
        <FacilityCode>MFG-PUN-01</FacilityCode>
        <Timestamp>2026-11-14T08:00:00Z</Timestamp>
    </Header>
    <Item>
        <MaterialNumber>AZI-500</MaterialNumber>
        <LotNumber>BATCH-2026-M1</LotNumber>
        <QuantityProduced>5000</QuantityProduced>
    </Item>
</DispatchNotice>"""
    xml_expected = {
        "manufacturer_id": "MFG-PUN-01",
        "product_id": "AZI-500",
        "batch_id": "BATCH-2026-M1",
        "quantity": 5000,
        "source": "erp_mfg",
    }
    xml_file = fixtures_dir / "manufacturer_erp_sample.xml"
    if xml_file.exists():
        try:
            xml_sample = xml_file.read_text(encoding="utf-8")
        except Exception as e:
            logger.debug("Failed reading xml sample: %s", e)
    xml_exp_file = fixtures_dir / "manufacturer_erp_expected.json"
    if xml_exp_file.exists():
        try:
            xml_expected = json.loads(xml_exp_file.read_text(encoding="utf-8"))
        except Exception as e:
            logger.debug("Failed reading xml expected: %s", e)

    # 3. Nested Legacy POS JSON
    json_sample = """{
  "pos_terminal": {
    "store_id": "PHARM-MUM-04",
    "terminal_no": "TERM-02"
  },
  "basket": [
    {
      "item_code": "AMOX-250",
      "lot_code": "LOT-2026-A2",
      "count": 4,
      "price": 120.00
    }
  ]
}"""
    json_expected = {
        "pharmacy_id": "PHARM-MUM-04",
        "product_id": "AMOX-250",
        "batch_id": "LOT-2026-A2",
        "quantity": 4,
        "source": "pos",
    }
    json_file = fixtures_dir / "nested_legacy_pos_sample.json"
    if json_file.exists():
        try:
            json_sample = json_file.read_text(encoding="utf-8")
        except Exception as e:
            logger.debug("Failed reading json sample: %s", e)
    json_exp_file = fixtures_dir / "nested_legacy_pos_expected.json"
    if json_exp_file.exists():
        try:
            json_expected = json.loads(json_exp_file.read_text(encoding="utf-8"))
        except Exception as e:
            logger.debug("Failed reading json expected: %s", e)

    return [
        {
            "id": "pharmacy_billing_csv",
            "name": "1. Legacy Pharmacy Billing CSV",
            "format": "csv",
            "description": "Legacy pharmacy point-of-sale invoice row with custom column headers and DD/MM/YYYY date formatting.",
            "target_schema": "SaleEvent",
            "sample_payload": csv_sample,
            "expected_output": csv_expected,
        },
        {
            "id": "manufacturer_erp_xml",
            "name": "2. Manufacturer ERP XML",
            "format": "xml",
            "description": "SAP/Oracle ERP XML dispatch notice with batch number, SKU, and unit quantity.",
            "target_schema": "BatchUpdate",
            "sample_payload": xml_sample,
            "expected_output": xml_expected,
        },
        {
            "id": "nested_legacy_pos_json",
            "name": "3. Nested Legacy POS JSON",
            "format": "json",
            "description": "Legacy e-pharmacy counter receipt with nested store and transaction metadata.",
            "target_schema": "SaleEvent",
            "sample_payload": json_sample,
            "expected_output": json_expected,
        },
    ]


@router.get(
    "",
    summary="List Registered Adapters",
    description="Lists all registered dynamic adapters with their active version, format, and status.",
)
async def list_all_adapters() -> list[dict[str, Any]]:
    """Retrieve catalog of all active adapters."""
    return list_adapters()


@router.get(
    "/{identifier}",
    summary="Get Adapter Details and Version History",
    description="Returns full adapter details, including source code, test results, and all historical versions.",
)
async def get_adapter_details(identifier: str, version: int | None = Query(None)) -> dict[str, Any]:
    """Retrieve adapter metadata, source code, and full version history."""
    adapter = get_adapter(identifier, version=version)
    if not adapter:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Adapter '{identifier}' not found.")

    name = adapter.get("name", identifier)
    all_versions = list_adapter_versions(name)

    return {
        "adapter": adapter,
        "versions": all_versions,
    }


@router.post(
    "/{identifier}/rollback",
    summary="Rollback Adapter to Prior Stable Version",
    description="Reverts active adapter to a specified prior version (or active_version - 1) and syncs module registry.",
)
async def rollback_adapter_endpoint(
    identifier: str,
    payload: RollbackAdapterRequest | None = None,
) -> dict[str, Any]:
    """Roll back active version of specified adapter."""
    target_ver = payload.target_version if payload else None
    try:
        restored = rollback_adapter(identifier, target_version=target_ver)
        return {
            "status": "rolled_back",
            "adapter": restored,
            "active_version": restored.get("version"),
        }
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
