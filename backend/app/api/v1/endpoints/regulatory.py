"""Regulatory Pipeline API endpoints and hot-swap control (Task 18)."""

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.graphs.regulatory import (
    activate_regulatory_run,
    crawl_regulatory_notice,
    ensure_baseline_regulatory_modules,
    get_regulatory_run,
    list_notifications,
    list_regulatory_runs,
    rollback_regulatory_run,
    run_regulatory_pipeline,
)
from app.modules_runtime.registry import module_registry

logger = logging.getLogger("mediflux.api.v1.regulatory")

router = APIRouter(prefix="/regulatory", tags=["Regulatory Pipeline"])


# -----------------------------------------------------------------------------
# Schemas
# -----------------------------------------------------------------------------
class IngestNoticeRequest(BaseModel):
    """Payload to submit a regulatory notice for ingestion and pipeline execution."""

    text: str | None = Field(default=None, description="Raw regulatory text or Gazette order")
    url: str | None = Field(default=None, description="URL of official regulatory portal")
    source: str | None = Field(default="CDSCO/NPPA", description="Publishing authority")
    title: str | None = Field(default=None, description="Subject or Gazette reference title")
    auto_deploy: bool | None = Field(default=None, description="Override auto-deploy gating")


class PriceCheckRequest(BaseModel):
    """Payload to test live pricing calculation against active pricing module."""

    sku: str = Field(default="PARA-500", description="Product SKU")
    unit_price: float = Field(default=25.0, description="Base unit price before regulatory cap")
    quantity: int = Field(default=1, ge=1, description="Quantity")
    drug_name: str | None = Field(default=None, description="Optional drug name")
    module_kind: str | None = Field(default="pricing", description="Module kind")
    payload: dict[str, Any] | None = Field(default=None, description="Arbitrary extra fields")


# -----------------------------------------------------------------------------
# Endpoints
# -----------------------------------------------------------------------------
@router.get(
    "/fixtures",
    summary="Get Pre-packaged Synthetic Regulatory Directives",
    description="Returns pre-loaded DPCO price ceiling and track-and-trace notices for 1-click lab execution.",
)
async def get_regulatory_fixtures() -> list[dict[str, Any]]:
    """Retrieve pre-packaged regulatory notices from fixtures/regulatory."""
    fixtures_dir = Path(__file__).resolve().parents[4] / "fixtures" / "regulatory"
    if not fixtures_dir.exists():
        fixtures_dir = Path("fixtures/regulatory")

    # 1. NPPA DPCO Price Ceiling
    nppa_sample = """THE GAZETTE OF INDIA : EXTRAORDINARY [PART II-SEC. 3(ii)]
MINISTRY OF CHEMICALS AND FERTILIZERS
(National Pharmaceutical Pricing Authority)
ORDER
New Delhi, the 14th November, 2026

S.O. 4882(E).- In exercise of the powers conferred by paragraphs 4, 6, 10, 11, 14, 16, 17 and 18 of the Drugs (Prices Control) Order, 2013, read with S.O. 1394(E) dated the 30th May, 2013, issued by the Government of India in the Ministry of Chemicals and Fertilizers, the National Pharmaceutical Pricing Authority (NPPA) hereby fixes the ceiling price specified in column (5) of the Table below as ceiling price exclusive of goods and services tax applicable in respect of the scheduled formulation specified in the corresponding entry in column (2) of the said Table:

TABLE
Sl. No. | Scheduled Formulation | Dosage Form and Strength | Unit | Ceiling Price (INR)
(1)     | (2)                   | (3)                      | (4)  | (5)
1.      | Paracetamol           | Tablet 500 mg (PARA-500) | Strip of 10 | 12.50

Notes:
(a) The ceiling price is inclusive of mandatory maximum allowable post-manufacturing expenses (MAPE).
(b) All manufacturers, stockists, distributors, and retail pharmacies marketing the scheduled formulation with SKU 'PARA-500' are mandated to revise and cap retail selling prices not exceeding INR 12.50 per strip plus local taxes.
(c) Overcharging beyond the notified ceiling price shall attract recovery of overcharged amount with penal interest under the Essential Commodities Act, 1955.
(d) Effective Date: Immediate (14-Nov-2026)."""
    nppa_file = fixtures_dir / "nppa_price_ceiling_notice.txt"
    if nppa_file.exists():
        try:
            nppa_sample = nppa_file.read_text(encoding="utf-8")
        except Exception as e:
            logger.debug("Failed reading nppa sample: %s", e)

    # 2. CDSCO Track and Trace
    cdsco_sample = """GOVERNMENT OF INDIA
CENTRAL DRUGS STANDARD CONTROL ORGANIZATION (CDSCO)
Directorate General of Health Services
FDA Bhawan, Kotla Road, New Delhi - 110002

NOTIFICATION
Dated: 14th November, 2026

Sub: Mandatory QR Code and Dynamic Traceability Encoding on APIs and Top 300 Brands of Drug Formulations under Rule 96 of Drugs and Cosmetics Rules, 1945 - reg.

G.S.R. 782(E).- In exercise of the powers conferred by Section 12 and Section 33 of the Drugs and Cosmetics Act, 1940 (23 of 1940), the Central Government hereby amends the Drugs Rules, 1945 to mandate serialization and automated barcode verification for all pharmaceutical movement across India:

1. Every manufacturer, distributor, and pharmacy edge node shall implement machine-readable DataMatrix barcoding containing:
   (a) Unique Product Identification Code (GTIN)
   (b) Batch Number
   (c) Date of Manufacturing and Expiry
   (d) Serialized Identification Number

2. Verification Guard: The supply chain compliance engine shall enforce non-null serialization tokens on all scheduled antibiotic transactions (Schedule H / H1).
3. Compliance Penalty: Dispatches lacking authenticated barcode metadata shall be rejected at stockist transit checkpoints.
4. Effective Date: 14-Nov-2026."""
    cdsco_file = fixtures_dir / "cdsco_track_and_trace_notice.txt"
    if cdsco_file.exists():
        try:
            cdsco_sample = cdsco_file.read_text(encoding="utf-8")
        except Exception as e:
            logger.debug("Failed reading cdsco sample: %s", e)

    return [
        {
            "id": "nppa_price_ceiling",
            "title": "NPPA DPCO Price Ceiling Notice (Paracetamol / Essential Drug Cap)",
            "source": "NPPA / Gazette of India",
            "category": "Pricing Directive",
            "raw_text": nppa_sample,
            "test_payload": {
                "sku": "PARA-500",
                "drug_name": "Paracetamol 500mg",
                "unit_price": 25.00,
                "quantity": 10,
            },
            "ceiling_price": 12.50,
        },
        {
            "id": "cdsco_track_and_trace",
            "title": "CDSCO Schedule H1 Track-and-Trace Barcode Directive",
            "source": "CDSCO / MoHFW",
            "category": "Compliance & Traceability",
            "raw_text": cdsco_sample,
            "test_payload": {
                "sku": "AZI-500",
                "drug_name": "Azithromycin 500mg",
                "unit_price": 45.00,
                "quantity": 5,
            },
            "ceiling_price": None,
        },
    ]


@router.get(
    "/runs",
    summary="List Regulatory Pipeline Runs",
    description="Retrieves list of all historic and active regulatory runs.",
)
async def list_regulatory_runs_endpoint() -> list[dict[str, Any]]:
    """Retrieve catalog of all regulatory pipeline runs."""
    return list_regulatory_runs()


@router.post(
    "/notifications",
    summary="Ingest Regulatory Notice and Execute Analysis Pipeline",
    description="Ingests notice text or URL, runs crawler, analyzes directive, mutates code in staging, and creates HITL gate.",
    status_code=status.HTTP_202_ACCEPTED,
)
async def ingest_notification_endpoint(payload: IngestNoticeRequest) -> dict[str, Any]:
    """Ingest regulatory notice and trigger pipeline."""
    ensure_baseline_regulatory_modules()
    notice = crawl_regulatory_notice(
        text=payload.text,
        url=payload.url,
        source=payload.source,
        title=payload.title,
    )

    run_result = await run_regulatory_pipeline(
        notification_id=notice["id"],
        notification_text=notice["full_text"],
        source=notice.get("source", "CDSCO/NPPA"),
        title=notice.get("title", "Regulatory Notice"),
        correlation_id=notice.get("correlation_id"),
    )

    return {
        "notification_id": notice["id"],
        "run_id": run_result["id"],
        "status": run_result["status"],
        "reg_change": run_result.get("reg_change", {}),
        "staged_version": run_result.get("staged_version"),
        "active_version": run_result.get("active_version"),
        "hitl_task_id": run_result.get("hitl_task_id"),
        "diff": run_result.get("diff"),
        "test_results": run_result.get("test_results"),
    }


@router.get(
    "/notifications",
    summary="List Ingested Regulatory Notifications",
    description="Lists all regulatory notifications from authorities with content hash and timestamp.",
)
async def list_notifications_endpoint() -> list[dict[str, Any]]:
    """Retrieve catalog of ingested regulatory notices."""
    return list_notifications()


@router.get(
    "/runs/{run_id}",
    summary="Get Regulatory Pipeline Run Details",
    description="Returns step-by-step agent trace, diff, test results, and deployment status.",
)
async def get_regulatory_run_endpoint(run_id: str) -> dict[str, Any]:
    """Retrieve details for a specific regulatory pipeline run."""
    run = get_regulatory_run(run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Regulatory run '{run_id}' not found.")
    return run


@router.post(
    "/check-now",
    summary="Trigger Manual Regulatory Crawl Across Configured Sources",
    description="Scans MoHFW, CDSCO, and NPPA/eGazette sources and triggers the pipeline for unread directives.",
)
async def check_regulatory_sources_now(
    use_fixtures: bool = Query(default=True, description="Use local synthetic fixtures for testing"),
) -> list[dict[str, Any]]:
    """Scan regulatory sources and process new directives."""
    ensure_baseline_regulatory_modules()
    results = []
    sources = [
        ("nppa", "National Pharmaceutical Pricing Authority", "fixtures/regulatory/nppa_price_ceiling_notice.txt"),
        ("cdsco", "Central Drugs Standard Control Organization", "fixtures/regulatory/cdsco_track_and_trace_notice.txt"),
    ]
    for src_name, title, _fixture_rel in sources:
        notice = crawl_regulatory_notice(url=f"https://{src_name}.gov.in", source=src_name, title=title)
        run_res = await run_regulatory_pipeline(
            notification_id=notice["id"],
            notification_text=notice["full_text"],
            source=src_name,
            title=title,
        )
        results.append({
            "source": src_name,
            "notification_id": notice["id"],
            "run_id": run_res["id"],
            "status": run_res["status"],
            "staged_version": run_res.get("staged_version"),
        })
    return results


@router.post(
    "/runs/{run_id}/approve",
    summary="Approve Staged Regulatory Update and Trigger Hot-Swap",
    description="Approves the HITL checkpoint, atomically hot-swaps active module with zero downtime, and logs to audit ledger.",
)
async def approve_regulatory_run_endpoint(
    run_id: str,
    approver: str = Query(default="human:compliance_officer"),
) -> dict[str, Any]:
    """Approve staged regulatory module and hot-swap into production."""
    try:
        updated = await activate_regulatory_run(run_id, approver=approver)
        return {
            "status": "deployed",
            "active_version": updated.get("active_version"),
            "run": updated,
        }
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post(
    "/runs/{run_id}/rollback",
    summary="Rollback Deployed Regulatory Module",
    description="Reverts the active module to previous stable version and writes audit ledger record.",
)
async def rollback_regulatory_run_endpoint(
    run_id: str,
    actor: str = Query(default="human:compliance_officer"),
) -> dict[str, Any]:
    """Roll back deployed regulatory module to previous version."""
    try:
        updated = await rollback_regulatory_run(run_id, actor=actor)
        return {
            "status": "rolled_back",
            "active_version": updated.get("active_version"),
            "run": updated,
        }
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post(
    "/price-check",
    summary="Execute Live Pricing Calculation via Active Module",
    description="Executes the currently active pricing_engine module to test price ceiling enforcement in real time.",
)
async def price_check_endpoint(payload: PriceCheckRequest) -> dict[str, Any]:
    """Execute currently active pricing engine in the dynamic module registry."""
    ensure_baseline_regulatory_modules()
    now_iso = datetime.now(UTC).isoformat()
    try:
        run_input = {
            "sku": payload.sku,
            "unit_price": payload.unit_price,
            "quantity": payload.quantity,
            "drug_name": payload.drug_name or "Paracetamol 500mg",
        }
        if payload.payload:
            run_input.update(payload.payload)

        result = module_registry.run_module("pricing_engine", run_input)
        active_mod = module_registry.get_active("pricing_engine")
        active_version = active_mod.version if active_mod else 1

        effective_price = float(result.get("effective_price") or result.get("final_unit_price") or payload.unit_price)
        price_capped = bool(result.get("price_capped", effective_price < payload.unit_price))
        ceiling_applied = result.get("ceiling_applied") or (effective_price if price_capped else None)
        total_amount = round(effective_price * payload.quantity, 2)

        output_data = {
            "sku": payload.sku,
            "original_price": payload.unit_price,
            "unit_price": payload.unit_price,
            "effective_price": effective_price,
            "final_unit_price": effective_price,
            "quantity": payload.quantity,
            "total_amount": total_amount,
            "price_capped": price_capped,
            "ceiling_applied": ceiling_applied,
            "compliant": True,
        }

        return {
            "active_version": active_version,
            "module_name": "pricing_engine",
            "input": run_input,
            "output": output_data,
            "result": result,
            "evaluated_at": now_iso,
        }
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

