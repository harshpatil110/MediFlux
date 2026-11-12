"""Compliance logs API endpoints (Task 19)."""

import logging
from typing import Any

from fastapi import APIRouter, Query, status

from app.graphs.prescription import list_compliance_logs

logger = logging.getLogger("mediflux.api.compliance")

router = APIRouter(prefix="/compliance", tags=["Compliance"])


@router.get("/logs", status_code=status.HTTP_200_OK)
async def get_compliance_logs(
    prescription_id: str | None = Query(None, description="Filter logs by prescription ID"),
    action: str | None = Query(None, description="Filter logs by action taken (approve_dispense, flag, reject)"),
    node_id: str | None = Query(None, description="Filter logs by node ID"),
    limit: int = Query(50, ge=1, le=500, description="Maximum log entries to return"),
) -> list[dict[str, Any]]:
    """Retrieve filtered compliance logs for prescriptions and drug schedules."""
    return list_compliance_logs(
        prescription_id=prescription_id,
        action=action,
        node_id=node_id,
        limit=limit,
    )
