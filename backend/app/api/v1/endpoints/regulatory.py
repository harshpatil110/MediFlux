"""Regulatory Pipeline API endpoints and hot-swap control (Task 18)."""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.graphs.regulatory import (
    activate_regulatory_run,
    crawl_regulatory_notice,
    ensure_baseline_regulatory_modules,
    get_regulatory_run,
    list_notifications,
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


# -----------------------------------------------------------------------------
# Endpoints
# -----------------------------------------------------------------------------
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
    try:
        result = module_registry.run_module("pricing_engine", payload.model_dump())
        active_mod = module_registry.get_active("pricing_engine")
        return {
            "active_version": active_mod.version if active_mod else 1,
            "result": result,
        }
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
