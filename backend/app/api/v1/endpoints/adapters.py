"""Adapter Marketplace API and real-time generation SSE streaming (Task 17)."""

import json
import logging
import uuid
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
