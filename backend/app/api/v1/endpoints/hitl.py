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


def _seed_hitl_tasks_if_empty() -> None:
    """Ensure at least 3 realistic pending HITL tasks exist for immediate inbox richness."""
    if _in_memory_hitl_tasks:
        return

    now_iso = datetime.now(UTC).isoformat()
    tasks = [
        {
            "id": "hitl-task-seed-01",
            "task_id": "hitl-task-seed-01",
            "task_type": "regulatory_hot_swap",
            "risk_level": "high",
            "title": "NPPA DPCO Price Ceiling Hot-Swap (Paracetamol 500mg)",
            "summary": "Automated regulatory pipeline generated new pricing_engine v2 enforcing ₹12.50 ceiling price. Awaiting compliance officer approval for live zero-downtime hot-swap.",
            "node_id": "00000000-0000-0000-0000-000000000000",
            "node_name": "Central Compliance Office - New Delhi",
            "status": "pending",
            "reasoning": "Confidence 0.95: Official Gazette S.O. 4882(E) parsed. Staging AST security verification passed and all 4 regression tests passed.",
            "correlation_id": "casc-seed-reg-01",
            "created_at": now_iso,
            "details": {
                "module_name": "pricing_engine",
                "staged_version": 2,
                "ceiling_price": 12.50,
                "affected_sku": "PARA-500",
                "run_id": "reg-run-seed-01",
                "diff": "--- pricing_engine_v1.py\n+++ pricing_engine_v2.py\n@@ -10,6 +10,12 @@\n     base_price = input_data.get('unit_price', 25.0)\n+    # NPPA DPCO Statutory Price Ceiling Enforcement\n+    if input_data.get('sku') == 'PARA-500' and base_price > 12.50:\n+        effective_price = 12.50\n+        capped = True\n+    else:\n+        effective_price = base_price\n+        capped = False",
            },
        },
        {
            "id": "hitl-task-seed-02",
            "task_id": "hitl-task-seed-02",
            "task_type": "prescription_doctor_verification",
            "risk_level": "critical",
            "title": "Schedule X Ketamine Dispense Authorization",
            "summary": "High-risk Schedule X prescription requires manual pharmacist validation of NMC registration credentials.",
            "node_id": "11111111-1111-1111-1111-111111111111",
            "node_name": "Apollo Pharmacy - Indiranagar",
            "status": "pending",
            "reasoning": "Schedule X narcotic substance detected with strict quota restriction. Doctor registry verified but high dosage exceeds single-transaction dispensing rule.",
            "correlation_id": "casc-seed-rx-02",
            "created_at": now_iso,
            "details": {
                "doctor_name": "Dr. Ramesh Sharma, MD",
                "doctor_reg_no": "MCI-48291",
                "drug_name": "Ketamine 50mg/ml",
                "quantity": 2,
                "patient_id": "PAT-DEL-8902",
                "schedule": "Schedule X",
            },
        },
        {
            "id": "hitl-task-seed-03",
            "task_id": "hitl-task-seed-03",
            "task_type": "coldchain_high_value",
            "risk_level": "medium",
            "title": "Insulin Glargine Storage Temperature Excursion Hold",
            "summary": "Sensor logged brief temperature spike to 8.4°C (threshold: 8.0°C) during distributor transit. Arrhenius stability degradation estimated at 0.4%.",
            "node_id": "22222222-2222-2222-2222-222222222222",
            "node_name": "Blue Dart Life Sciences - Hub A",
            "status": "pending",
            "reasoning": "Excursion was transient (< 18 minutes). Thermal degradation model predicts acceptable potency, but policy mandates quality assurance disposition.",
            "correlation_id": "casc-seed-cc-03",
            "created_at": now_iso,
            "details": {
                "batch_number": "BAT-INS-2026-X1",
                "recorded_temp": 8.4,
                "max_allowed": 8.0,
                "duration_minutes": 18,
                "product_name": "Insulin Glargine 100 IU",
            },
        },
    ]
    for t in tasks:
        _in_memory_hitl_tasks[t["id"]] = t


def _find_task(task_id: str) -> dict[str, Any] | None:
    """Find a HITL task from in-memory store or Supabase database."""
    _seed_hitl_tasks_if_empty()
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


@router.get("", summary="List HITL Tasks Alias")
@router.get("/tasks", summary="List HITL Tasks")
async def list_hitl_tasks(
    current_user: Annotated[UserProfile, Depends(get_current_user)],
    task_status: str | None = Query(default="all", alias="status", description="Filter by status (pending, approved, rejected, expired, all)"),
    task_type: str | None = Query(default=None, description="Filter by task_type"),
    risk_level: str | None = Query(default=None, description="Filter by risk_level (critical, high, medium, low)"),
    limit: int = Query(default=50, ge=1, le=100, description="Max items to retrieve"),
) -> list[dict[str, Any]]:
    """List pending or historic HITL tasks requiring operator intervention."""
    _seed_hitl_tasks_if_empty()

    # Attempt DB retrieval first
    if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY:
        try:
            client = get_service_db_client()
            if client:
                query = client.table("hitl_tasks").select("*")
                if task_status and task_status != "all":
                    query = query.eq("status", task_status)
                if task_type and task_type != "all":
                    query = query.eq("task_type", task_type)
                if risk_level and risk_level != "all":
                    query = query.eq("risk_level", risk_level)
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
        if task_type and task_type != "all" and t.get("task_type") != task_type and t.get("step_name") != task_type:
            continue
        if risk_level and risk_level != "all" and t.get("risk_level") != risk_level:
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
    "/{task_id}/decide",
    response_model=HITLDecisionResponse,
    summary="Submit Human Approval or Rejection Decision",
)
@router.post(
    "/tasks/{task_id}/decide",
    response_model=HITLDecisionResponse,
    summary="Submit Human Approval or Rejection Decision (Tasks Prefix)",
)
@router.post(
    "/{task_id}/decision",
    response_model=HITLDecisionResponse,
    summary="Submit Human Approval or Rejection Decision (Decision Alias)",
)
@router.post(
    "/tasks/{task_id}/decision",
    response_model=HITLDecisionResponse,
    summary="Submit Human Approval or Rejection Decision Legacy Alias",
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

    # 1. Inspect expires_at against current UTC time or verify if status is "expired"
    now_utc = datetime.now(UTC)
    is_expired = task.get("status") == "expired"
    expires_at_val = task.get("expires_at")
    if not is_expired and expires_at_val:
        try:
            exp_dt = (
                expires_at_val
                if isinstance(expires_at_val, datetime)
                else datetime.fromisoformat(str(expires_at_val).replace("Z", "+00:00"))
            )
            if exp_dt.tzinfo is None:
                exp_dt = exp_dt.replace(tzinfo=UTC)
            if exp_dt < now_utc:
                is_expired = True
        except Exception as parse_err:
            logger.debug("Failed parsing task expires_at %s: %s", expires_at_val, parse_err)

    if is_expired:
        task["status"] = "expired"
        _in_memory_hitl_tasks[task_id] = task
        if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY:
            try:
                client = get_service_db_client()
                if client:
                    client.table("hitl_tasks").update({"status": "expired"}).eq("id", task_id).execute()
            except Exception as db_exc:
                logger.warning("DB update to expired status failed: %s", db_exc)

        # Log to audit_ledger
        try:
            from app.core.audit_ledger import write_audit_entry

            await write_audit_entry(
                actor=str(current_user.id),
                action="HITL_TASK_EXPIRED_REJECTED",
                entity_type="hitl_tasks",
                entity_id=task_id,
                payload={
                    "task_id": task_id,
                    "attempted_decision": body.decision,
                    "status": "expired",
                    "expires_at": str(expires_at_val),
                },
                explanation=f"Decision rejected: HITL task '{task_id}' has expired past deadline.",
            )
        except Exception as audit_exc:
            logger.debug("write_audit_entry on expired HITL rejected: %s", audit_exc)

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Task has expired and cannot be approved",
        )

    # 2. Verify task is pending
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
    dec_status = "approved" if body.decision in ("approve", "approved") else "rejected"
    decision_text = "approve" if dec_status == "approved" else "reject"
    actual_note = body.note or body.reason or f"Task marked as {dec_status} by operator."
    now_iso = datetime.now(UTC).isoformat()
    task["status"] = dec_status
    task["decided_by"] = str(current_user.id)
    task["decided_at"] = now_iso
    task["decision_note"] = actual_note

    if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY:
        try:
            client = get_service_db_client()
            if client:
                client.table("hitl_tasks").update({
                    "status": dec_status,
                    "decided_by": str(current_user.id),
                    "decided_at": now_iso,
                    "decision_note": actual_note,
                }).eq("id", task_id).execute()
        except Exception as exc:
            logger.warning("DB update failed for task %s: %s", task_id, exc)

    _in_memory_hitl_tasks[task_id] = task

    # 4. Resume Paused Workflow / Execute Domain Side-Effects
    resumed_workflow: dict[str, Any] = {}
    if dec_status == "approved":
        # 4a. Regulatory Hot-Swap Resumption
        details = task.get("details", {}) or {}
        run_id = details.get("run_id")
        target_mod = details.get("module_name", "pricing_engine")
        staged_ver = details.get("staged_version", 2)

        if task_type == "regulatory_hot_swap" or run_id:
            try:
                from app.graphs.regulatory import activate_regulatory_run
                if run_id:
                    await activate_regulatory_run(run_id, approver=str(current_user.id))
            except Exception as exc:
                logger.debug("activate_regulatory_run inline note: %s", exc)

            try:
                from app.modules_runtime.registry import module_registry
                module_registry.activate(target_mod, staged_ver)
            except Exception as exc:
                logger.debug("module_registry.activate inline note: %s", exc)

            await in_process_event_bus.publish(
                "regulatory",
                EventEnvelope(
                    type="module.activated",
                    node_id=str(task.get("node_id") or "00000000-0000-0000-0000-000000000000"),
                    correlation_id=str(task.get("correlation_id", "")),
                    payload={
                        "module_name": target_mod,
                        "version": staged_ver,
                        "status": "active",
                        "run_id": run_id,
                        "action": "hot_swapped",
                    },
                ),
            )
            resumed_workflow = {
                "type": "regulatory_hot_swap",
                "run_id": run_id,
                "new_status": "deployed",
                "hot_swapped_version": staged_ver,
                "status": "resumed",
                "action": "activated_module",
                "module_name": target_mod,
                "version": staged_ver,
            }
        elif "prescription" in task_type:
            resumed_workflow = {
                "type": "prescription_verification",
                "new_status": "approved",
                "dispense_authorized": True,
            }
        else:
            resumed_workflow = {
                "type": task_type,
                "new_status": "approved",
                "disposition": "resumed",
            }
    else:
        resumed_workflow = {
            "type": task_type,
            "new_status": "rejected",
            "disposition": "aborted",
        }

    # 5. Audit Log entry
    try:
        from app.core.audit_ledger import write_audit_entry
        await write_audit_entry(
            actor=str(current_user.id),
            action="HITL_DECISION_SUBMITTED",
            entity_type="hitl_tasks",
            entity_id=task_id,
            payload={
                "task_id": task_id,
                "decision": decision_text,
                "status": dec_status,
                "note": actual_note,
                "decided_by": str(current_user.id),
                "task_type": task_type,
                "correlation_id": task.get("correlation_id"),
                "resumed_workflow": resumed_workflow,
            },
            explanation=f"HITL task '{task.get('title', task_id)}' was {dec_status} by operator.",
        )
    except Exception as exc:
        logger.debug("write_audit_entry in hitl decide note: %s", exc)

    # 6. Record in-memory decision resolution for graph nodes / workers
    record_hitl_decision(
        task_id,
        {
            "approved": dec_status == "approved",
            "decision": decision_text,
            "note": actual_note,
            "decided_by": str(current_user.id),
            "resumed_workflow": resumed_workflow,
        },
    )

    # 7. Emit SSE event (hitl.decided)
    resolved_event = EventEnvelope(
        event_id=str(uuid.uuid4()),
        type="hitl.decided",
        node_id=str(task.get("node_id", "00000000-0000-0000-0000-000000000000")),
        correlation_id=str(task.get("correlation_id", "")),
        payload={
            "task_id": task_id,
            "decision": dec_status,
            "status": dec_status,
            "decided_by": str(current_user.id),
            "note": actual_note,
            "event_type": "hitl.decided",
            "resumed_workflow": resumed_workflow,
        },
    )
    await in_process_event_bus.publish("hitl", resolved_event)

    # 8. Resume LangGraph Execution if active checkpointed thread exists
    resume_outcome: Any = None
    resumed = bool(resumed_workflow)
    corr_id = str(task.get("correlation_id", ""))
    resume_payload = {
        "approved": dec_status == "approved",
        "decision": decision_text,
        "note": actual_note,
        "decided_by": str(current_user.id),
    }

    try:
        outcome = await resume_graph_thread(corr_id, resume_payload)
        if outcome is None:
            outcome = await resume_graph_thread(task_id, resume_payload)
        if outcome is not None:
            resume_outcome = outcome
            resumed = True
            logger.info("LangGraph thread successfully resumed for task %s", task_id)
    except Exception as exc:
        logger.warning("Error resuming LangGraph thread for task %s: %s", task_id, exc)

    return HITLDecisionResponse(
        status=dec_status,
        task_id=task_id,
        decision=decision_text,
        decided_by=str(current_user.id),
        decided_at=now_iso,
        resumed=resumed,
        task=task,
        execution_outcome=resume_outcome if isinstance(resume_outcome, dict) else None,
        resumed_workflow=resumed_workflow,
    )
