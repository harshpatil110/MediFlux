"""Agent trace query endpoints for AI observability and execution inspection."""

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from app.agents.base import get_in_memory_agent_runs
from app.core.config import settings
from app.core.security import CurrentUser, get_current_user, get_service_db_client

logger = logging.getLogger("mediflux.api.agents")

router = APIRouter(prefix="/agents", tags=["AI Agents & Graph Observability"])


@router.get(
    "",
    summary="List Agent Execution Runs Alias",
)
@router.get(
    "/runs",
    summary="List AI Agent Execution Traces",
    description="Retrieve recent agent runs, model invocations, execution duration, and statuses.",
)
async def list_agent_runs(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    agent_name: str | None = Query(None, description="Filter by agent name"),
    status: str | None = Query(None, description="Filter by status (completed, running, failed)"),
    limit: int = Query(50, ge=1, le=100, description="Max traces to retrieve"),
) -> list[dict[str, Any]]:
    """Retrieve in-memory and database agent execution traces."""
    traces: list[dict[str, Any]] = []

    # 1. Collect in-memory traces first
    in_memory = list(reversed(get_in_memory_agent_runs()))
    for r in in_memory:
        if agent_name and r.get("agent_name") != agent_name:
            continue
        if status and r.get("status") != status:
            continue
        traces.append(r)
        if len(traces) >= limit:
            return traces

    # 2. Query Supabase agent_runs if database is configured
    if len(traces) < limit and settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY:
        try:
            client = get_service_db_client()
            if client:
                query = client.table("agent_runs").select("*").order("created_at", desc=True).limit(limit)
                if agent_name:
                    query = query.eq("agent_name", agent_name)
                if status:
                    query = query.eq("status", status)
                res = query.execute()
                for row in res.data or []:
                    rid = row.get("id") or row.get("run_id")
                    if not any(t.get("run_id") == rid or t.get("id") == rid for t in traces):
                        traces.append({
                            "run_id": rid,
                            "agent_name": row.get("agent_name", "agent"),
                            "graph": row.get("graph", "cascade"),
                            "model": row.get("model", "llama-3.1-70b"),
                            "node_id": row.get("node_id"),
                            "status": row.get("status", "completed"),
                            "duration_ms": row.get("duration_ms", 120.0),
                            "correlation_id": row.get("correlation_id"),
                            "created_at": row.get("created_at"),
                            "summary": row.get("output_summary") or row.get("summary") or "Execution trace completed.",
                        })
                        if len(traces) >= limit:
                            break
        except Exception as exc:
            logger.debug("Database agent_runs query failed: %s", exc)

    return traces
