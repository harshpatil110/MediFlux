"""Human-in-the-Loop (HITL) approval management endpoints."""

import logging
import uuid
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.config import settings
from app.core.hitl import (
    _in_memory_hitl_tasks,
    get_hitl_task,
    get_in_memory_hitl_tasks,
    record_audit_log,
    record_hitl_decision,
    resume_graph_thread,
)
from app.core.hitl_policy import get_required_roles
from app.core.security import get_current_user, get_service_db_client
from app.events.bus import in_process_event_bus
from app.events.models import EventEnvelope
from app.schemas.base import UserProfile
from app.schemas.hitl import HITLDecisionRequest, HITLDecisionResponse

logger = logging.getLogger("mediflux.api.v1.hitl")

router = APIRouter(prefix="/hitl", tags=["HITL"])


def _find_task(task_id: str) -> dict[str, Any] | None:
    """Find a HITL task from in-memory store or Supabase database."""
    # 1. In-memory check
    task = get_hitl_task(task_id)
    if task:
        return task

    # 2. Database check
    if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY:
        try:
            client = get_service_db_client()
            if client:
                resp = client.table("hitl_tasks").select("*").eq("id", task_id).execute()
                if resp.data:
                    return resp.data[0]
        except Exception as exc:
            logger.warning("DB lookup failed for task %s: %s", task_id, exc)

    return None


@router.get("/tasks", summary="List HITL Tasks")
async def list_hitl_tasks(
    current_user: Annotated[UserProfile, Depends(get_current_user)],
    task_status: str | None = Query(default="pending", alias="status", description="Filter by status (pending, approved, rejected, expired, all)"),
    task_type: str | None = Query(default=None, description="Filter by task_type"),
    limit: int = Query(default=50, ge=1, le=100, description="Max items to retrieve"),
) -> list[dict[str, Any]]:
    """List pending or historic HITL tasks requiring operator intervention."""
    # Attempt DB retrieval first
    if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY:
        try:
            client = get_service_db_client()
            if client:
                query = client.table("hitl_tasks").select("*")
                if task_status and task_status != "all":
                    query = query.eq("status", task_status)
                if task_type:
                    query = query.eq("task_type", task_type)
                query = query.order("created_at", desc=True).limit(limit)
                resp = query.execute()
                if resp.data:
                    return resp.data
        except Exception as exc:
            logger.warning("DB query for hitl_tasks failed (%s); using in-memory store", exc)

    # In-memory fallback
    all_tasks = get_in_memory_hitl_tasks()
    filtered: list[dict[str, Any]] = []
    for t in all_tasks:
        if task_status and task_status != "all" and t.get("status") != task_status:
            continue
        if task_type and t.get("task_type") != task_type and t.get("step_name") != task_type:
            continue
        filtered.append(t)

    filtered.sort(key=lambda t: t.get("created_at") or "", reverse=True)
    return filtered[:limit]


@router.get("/tasks/{task_id}", summary="Get HITL Task Details")
async def get_hitl_task_endpoint(
    task_id: str,
    current_user: Annotated[UserProfile, Depends(get_current_user)],
) -> dict[str, Any]:
    """Retrieve full task details, payload, and audit status for a specific HITL task."""
    task = _find_task(task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"HITL task with id '{task_id}' not found.",
        )
    return task


@router.post(
    "/tasks/{task_id}/decision",
    response_model=HITLDecisionResponse,
    summary="Submit Human Approval or Rejection Decision",
)
async def submit_hitl_decision(
    task_id: str,
    body: HITLDecisionRequest,
    current_user: Annotated[UserProfile, Depends(get_current_user)],
) -> HITLDecisionResponse:
    """Submit an operator decision (approve or reject) for a pending task with strict RBAC."""
    task = _find_task(task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"HITL task with id '{task_id}' not found.",
        )

    # 1. Verify task is pending
    if task.get("status") != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Task '{task_id}' is not in 'pending' status (current: {task.get('status')}).",
        )

    # 2. RBAC Role Verification
    task_type = str(task.get("task_type") or task.get("step_name") or task.get("action_type") or "")
    required_roles = get_required_roles(task_type)
    user_role = getattr(current_user, "role", "unknown")

    if user_role not in required_roles:
        logger.warning(
            "RBAC check failed: user %s with role '%s' attempted to decide task %s (requires %s)",
            current_user.id,
            user_role,
            task_type,
            required_roles,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"User role '{user_role}' is not authorized to decide task '{task_type}'. "
                f"Required role(s): {required_roles}."
            ),
        )

    # 3. Update task record
    dec_status = "approved" if body.decision == "approve" else "rejected"
    now_iso = datetime.now(UTC).isoformat()
    task["status"] = dec_status
    task["decided_by"] = str(current_user.id)
    task["decided_at"] = now_iso
    task["decision_note"] = body.note

    if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY:
        try:
            client = get_service_db_client()
            if client:
                client.table("hitl_tasks").update({
                    "status": dec_status,
                    "decided_by": str(current_user.id),
                    "decided_at": now_iso,
                    "decision_note": body.note,
                }).eq("id", task_id).execute()
        except Exception as exc:
            logger.warning("DB update failed for task %s: %s", task_id, exc)

    _in_memory_hitl_tasks[task_id] = task

    # 4. Audit Log entry
    record_audit_log(
        action_type="HITL_DECISION_SUBMITTED",
        payload={
            "task_id": task_id,
            "decision": body.decision,
            "status": dec_status,
            "note": body.note,
            "decided_by": str(current_user.id),
            "task_type": task_type,
            "correlation_id": task.get("correlation_id"),
        },
        node_id=task.get("node_id"),
    )

    # 5. Record in-memory decision resolution for graph nodes / workers
    record_hitl_decision(
        task_id,
        {
            "approved": body.decision == "approve",
            "decision": body.decision,
            "note": body.note,
            "decided_by": str(current_user.id),
        },
    )

    # 6. Emit SSE event (hitl_resolved)
    resolved_event = EventEnvelope(
        event_id=str(uuid.uuid4()),
        type="hitl_resolved",
        node_id=str(task.get("node_id", "00000000-0000-0000-0000-000000000000")),
        correlation_id=str(task.get("correlation_id", "")),
        payload={
            "task_id": task_id,
            "decision": body.decision,
            "status": dec_status,
            "decided_by": str(current_user.id),
            "note": body.note,
            "event_type": "hitl_resolved",
        },
    )
    await in_process_event_bus.publish("hitl", resolved_event)

    # 7. Resume LangGraph Execution if active checkpointed thread exists
    resume_outcome: Any = None
    resumed = False
    corr_id = str(task.get("correlation_id", ""))
    resume_payload = {
        "approved": body.decision == "approve",
        "decision": body.decision,
        "note": body.note,
        "decided_by": str(current_user.id),
    }

    try:
        # Try resuming by correlation_id first, then by task_id
        resume_outcome = await resume_graph_thread(corr_id, resume_payload)
        if resume_outcome is None:
            resume_outcome = await resume_graph_thread(task_id, resume_payload)
        if resume_outcome is not None:
            resumed = True
            logger.info("LangGraph thread successfully resumed for task %s", task_id)
    except Exception as exc:
        logger.warning("Error resuming LangGraph thread for task %s: %s", task_id, exc)

    return HITLDecisionResponse(
        status=dec_status,
        task_id=task_id,
        decision=body.decision,
        decided_by=str(current_user.id),
        decided_at=now_iso,
        resumed=resumed,
        task=task,
        execution_outcome=resume_outcome if isinstance(resume_outcome, dict) else None,
    )
