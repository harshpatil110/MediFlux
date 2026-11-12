"""Cascade trace REST API endpoints for observing multi-tier demand propagation."""

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.agents.base import get_in_memory_agent_runs
from app.core.exceptions import NotFoundError
from app.core.security import CurrentUser, get_current_user, get_service_db_client
from app.graphs.cascade import get_in_memory_cascade_trace

logger = logging.getLogger("mediflux.api.cascade")

router = APIRouter(prefix="/cascade", tags=["Demand Cascade Observability"])


class CascadeTraceStep(BaseModel):
    tier: str
    agent_name: str
    status: str
    summary: str
    start_time: str
    end_time: str
    latency_ms: float = 0.0


class CascadeTraceResponse(BaseModel):
    correlation_id: str
    status: str
    event: dict[str, Any] = Field(default_factory=dict)
    steps: list[CascadeTraceStep] = Field(default_factory=list)


@router.get(
    "/{correlation_id}",
    response_model=CascadeTraceResponse,
    summary="Get Cascade Execution Trace",
    description="Retrieve ordered multi-tier execution steps for a demand cascade by correlation ID.",
)
async def get_cascade_trace(
    correlation_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> CascadeTraceResponse:
    """Query in-memory and database agent_runs to return full cascade trace."""
    # 1. Check in-memory cascade traces
    trace_record = get_in_memory_cascade_trace(correlation_id)
    if trace_record:
        steps = [
            CascadeTraceStep(
                tier=s.get("tier", "unknown"),
                agent_name=s.get("agent_name", "unknown"),
                status=s.get("status", "unknown"),
                summary=s.get("summary", ""),
                start_time=s.get("start_time", ""),
                end_time=s.get("end_time", ""),
                latency_ms=float(s.get("latency_ms", 0.0)),
            )
            for s in trace_record.get("steps", [])
        ]
        return CascadeTraceResponse(
            correlation_id=correlation_id,
            status=trace_record.get("status", "completed"),
            event=trace_record.get("event", {}),
            steps=steps,
        )

    # 2. Check in-memory agent_runs
    agent_runs = [r for r in get_in_memory_agent_runs() if r.get("correlation_id") == correlation_id]
    if agent_runs:
        steps = []
        for r in agent_runs:
            agent_name = r.get("agent_name", "")
            tier = agent_name.replace("_agent", "")
            steps.append(
                CascadeTraceStep(
                    tier=tier,
                    agent_name=agent_name,
                    status=r.get("status", "success"),
                    summary=f"{tier.title()} processed demand",
                    start_time=r.get("created_at", ""),
                    end_time=r.get("created_at", ""),
                    latency_ms=float(r.get("duration_ms", 0.0)),
                )
            )
        status_val = "partial" if any(r.get("status") == "failed" for r in agent_runs) else "completed"
        return CascadeTraceResponse(
            correlation_id=correlation_id,
            status=status_val,
            event={},
            steps=steps,
        )

    # 3. Check Supabase database if connected
    client = get_service_db_client()
    if client:
        try:
            res = client.table("agent_runs").select("*").eq("correlation_id", correlation_id).order("created_at").execute()
            if res.data:
                steps = []
                for r in res.data:
                    agent_name = r.get("agent_name", "")
                    tier = agent_name.replace("_agent", "")
                    steps.append(
                        CascadeTraceStep(
                            tier=tier,
                            agent_name=agent_name,
                            status=r.get("status", "success"),
                            summary=f"{tier.title()} step completed",
                            start_time=r.get("created_at", ""),
                            end_time=r.get("created_at", ""),
                            latency_ms=float(r.get("duration_ms", 0.0)),
                        )
                    )
                status_val = "partial" if any(r.get("status") == "failed" for r in res.data) else "completed"
                return CascadeTraceResponse(
                    correlation_id=correlation_id,
                    status=status_val,
                    event={},
                    steps=steps,
                )
        except Exception as exc:
            logger.warning("Failed querying agent_runs for correlation_id=%s: %s", correlation_id, exc)

    raise NotFoundError(f"Cascade trace not found for correlation ID: {correlation_id}")

