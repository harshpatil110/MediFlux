"""Human-in-the-Loop (HITL) core approval workflows, task persistence, audit logging, and graph interruption."""

import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from app.core.audit_ledger import (
    _in_memory_audit_ledger,
    clear_in_memory_audit_ledger,
    compute_entry_hash,
    get_in_memory_audit_ledger,
)
from app.core.config import settings
from app.core.hitl_policy import get_expiry_hours, is_hitl_required
from app.core.security import get_service_db_client
from app.events.bus import in_process_event_bus
from app.events.models import EventEnvelope

logger = logging.getLogger("mediflux.core.hitl")

__all__ = [
    "clear_in_memory_audit_ledger",
    "get_in_memory_audit_ledger",
    "record_audit_log",
    "request_human_approval",
    "get_hitl_task",
    "clear_hitl_tasks",
    "get_in_memory_hitl_tasks",
    "is_task_expired",
    "register_resumable_graph",
    "get_resumable_graph",
]

# In-memory storage for test isolation and offline operation
_in_memory_hitl_tasks: dict[str, dict[str, Any]] = {}
_registered_resumable_graphs: dict[str, tuple[Any, dict[str, Any]]] = {}
_hitl_decisions: dict[str, dict[str, Any]] = {}


# -----------------------------------------------------------------------------
# Graph Resumption Registry
# -----------------------------------------------------------------------------
def register_resumable_graph(thread_or_corr_id: str, graph: Any, config: dict[str, Any]) -> None:
    """Register an active graph instance and config for external resumption by thread/correlation ID."""
    _registered_resumable_graphs[str(thread_or_corr_id)] = (graph, config)


def get_resumable_graph(thread_or_corr_id: str) -> tuple[Any, dict[str, Any]] | None:
    """Retrieve registered graph and config by thread/correlation ID."""
    return _registered_resumable_graphs.get(str(thread_or_corr_id))


def unregister_resumable_graph(thread_or_corr_id: str) -> None:
    """Unregister a completed graph thread."""
    _registered_resumable_graphs.pop(str(thread_or_corr_id), None)


def record_hitl_decision(task_id: str, decision_payload: dict[str, Any]) -> None:
    """Store decision resolution in memory."""
    _hitl_decisions[str(task_id)] = decision_payload


def get_hitl_decision(task_id: str) -> dict[str, Any] | None:
    """Retrieve stored decision resolution by task ID."""
    return _hitl_decisions.get(str(task_id))


async def resume_graph_thread(thread_or_corr_id: str, resume_payload: dict[str, Any]) -> Any:
    """Resume execution of a checkpointed LangGraph thread with decision payload."""
    from langgraph.types import Command

    entry = _registered_resumable_graphs.get(str(thread_or_corr_id))
    if entry:
        graph, config = entry
        logger.info("Resuming registered graph thread %s with %s", thread_or_corr_id, resume_payload)
        return await graph.ainvoke(Command(resume=resume_payload), config=config)
    logger.debug("No registered graph thread found for key %s", thread_or_corr_id)
    return None


# -----------------------------------------------------------------------------
# In-Memory Test Helpers
# -----------------------------------------------------------------------------
def get_hitl_task(task_id: str) -> dict[str, Any] | None:
    """Retrieve an in-memory HITL task definition."""
    return _in_memory_hitl_tasks.get(str(task_id))


def get_in_memory_hitl_tasks() -> list[dict[str, Any]]:
    """Retrieve all in-memory HITL tasks."""
    return list(_in_memory_hitl_tasks.values())


def clear_hitl_tasks() -> None:
    """Clear in-memory HITL tasks."""
    _in_memory_hitl_tasks.clear()


def resolve_hitl_task(task_id: str, status: str = "approved", decision_reason: str = "") -> None:
    """Update status of an in-memory HITL task."""
    tid = str(task_id)
    if tid in _in_memory_hitl_tasks:
        _in_memory_hitl_tasks[tid]["status"] = status
        _in_memory_hitl_tasks[tid]["decision_reason"] = decision_reason
        _in_memory_hitl_tasks[tid]["decision_note"] = decision_reason
        _in_memory_hitl_tasks[tid]["decided_at"] = datetime.now(UTC).isoformat()


def is_task_expired(task: dict[str, Any]) -> bool:
    """Return True if task status is 'expired' or expires_at is in the past."""
    if task.get("status") == "expired":
        return True
    expires_at_val = task.get("expires_at")
    if not expires_at_val:
        return False
    try:
        exp_dt = (
            expires_at_val
            if isinstance(expires_at_val, datetime)
            else datetime.fromisoformat(str(expires_at_val).replace("Z", "+00:00"))
        )
        if exp_dt.tzinfo is None:
            exp_dt = exp_dt.replace(tzinfo=UTC)
        return exp_dt < datetime.now(UTC)
    except Exception:
        return False


# -----------------------------------------------------------------------------
# Audit Ledger Writer
# -----------------------------------------------------------------------------
def record_audit_log(
    action_type: str,
    payload: dict[str, Any],
    node_id: str | None = None,
) -> dict[str, Any]:
    """Record an immutable entry in the audit ledger and in-memory store."""
    now_iso = datetime.now(UTC).isoformat()
    latest_seq = len(_in_memory_audit_ledger)
    prev_hash = "0" * 64
    if _in_memory_audit_ledger:
        prev_hash = str(_in_memory_audit_ledger[-1].get("hash") or _in_memory_audit_ledger[-1].get("current_hash") or ("0" * 64))

    new_seq = latest_seq + 1
    new_hash = compute_entry_hash(
        prev_hash=prev_hash,
        seq=new_seq,
        ts=now_iso,
        actor="system",
        action=action_type,
        entity_type="hitl_task",
        entity_id=str(payload.get("task_id", node_id or "system")),
        payload=payload,
        explanation="",
    )

    record = {
        "id": str(uuid.uuid4()),
        "seq": new_seq,
        "sequence_id": new_seq,
        "ts": now_iso,
        "timestamp": now_iso,
        "actor": "system",
        "action": action_type,
        "action_type": action_type,
        "entity_type": "hitl_task",
        "entity_id": str(payload.get("task_id", node_id or "system")),
        "payload": payload,
        "explanation": "",
        "prev_hash": prev_hash,
        "previous_hash": prev_hash,
        "hash": new_hash,
        "current_hash": new_hash,
        "node_id": node_id if node_id and len(str(node_id)) == 36 else None,
    }

    if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY:
        try:
            client = get_service_db_client()
            if client:
                client.table("audit_ledger").insert(record).execute()
        except Exception as exc:
            logger.warning("DB audit_ledger insert failed (%s); saved to in-memory store.", exc)

    _in_memory_audit_ledger.append(record)
    return record


def create_hitl_task(
    task_type: str,
    payload: dict[str, Any],
    correlation_id: str = "",
    node_id: str = "00000000-0000-0000-0000-000000000000",
    workflow_name: str = "workflow",
    risk_level: str = "high",
) -> dict[str, Any]:
    """Create and persist a pending HITL task record in database and in-memory store."""
    task_id = str(uuid.uuid4())
    expiry_h = get_expiry_hours(task_type)
    expires_at = datetime.now(UTC) + timedelta(hours=expiry_h)

    task_record = {
        "id": task_id,
        "task_id": task_id,
        "action_type": task_type,
        "task_type": task_type,
        "correlation_id": correlation_id,
        "workflow_name": workflow_name,
        "step_name": task_type,
        "task_data": {
            **payload,
            "risk_level": risk_level,
            "node_id": node_id,
        },
        "payload": payload,
        "details": payload,
        "status": "pending",
        "expires_at": expires_at.isoformat(),
        "decided_by": None,
        "decided_at": None,
        "decision_note": None,
        "created_at": datetime.now(UTC).isoformat(),
    }

    if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY:
        try:
            client = get_service_db_client()
            if client:
                client.table("hitl_tasks").insert(task_record).execute()
        except Exception as exc:
            logger.warning("Database hitl_tasks insertion failed (%s); using in-memory store.", exc)

    _in_memory_hitl_tasks[task_id] = task_record
    return task_record


# -----------------------------------------------------------------------------
# Core HITL Request Function
# -----------------------------------------------------------------------------
async def request_human_approval(
    task_type: Any = None,
    node_id: str | None = None,
    correlation_id: str | None = None,
    details: dict[str, Any] | None = None,
    state: dict[str, Any] | None = None,
    risk_level: str = "medium",
    payload: dict[str, Any] | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Check policy, create pending HITL task, write audit ledger, emit SSE, and handle graph interrupt."""
    # Handle Task 7 positional call: request_human_approval(state, task_type, payload, risk_level)
    if isinstance(task_type, dict) and isinstance(node_id, str):
        passed_state = task_type
        actual_task_type = node_id
        actual_details = correlation_id if isinstance(correlation_id, dict) else (details or payload or {})
        actual_corr_id = str(passed_state.get("correlation_id", uuid.uuid4()))
        actual_node_id = str(passed_state.get("node_id", "00000000-0000-0000-0000-000000000000"))
        state = passed_state
        task_type = actual_task_type
        node_id = actual_node_id
        correlation_id = actual_corr_id
        details = actual_details

    # Handle keyword arguments when payload or details provided
    task_details = dict(details or payload or kwargs.get("data") or {})
    task_type_str = str(task_type or "manual_approval")

    # If state passed via kwarg
    if state is not None and isinstance(state, dict):
        if not correlation_id:
            correlation_id = str(state.get("correlation_id", uuid.uuid4()))
        if not node_id:
            node_id = str(state.get("node_id", "00000000-0000-0000-0000-000000000000"))

    corr_id = str(correlation_id or uuid.uuid4())
    nid = str(node_id or "00000000-0000-0000-0000-000000000000")

    # 1. Check policy via is_hitl_required
    if not is_hitl_required(task_type_str):
        return {
            "status": "bypassed",
            "approved": True,
            "requires_hitl": False,
            "task_type": task_type_str,
        }

    # 2. Compute expiration time based on policy expiry_hours
    expiry_h = get_expiry_hours(task_type_str)
    expires_at = datetime.now(UTC) + timedelta(hours=expiry_h)

    task_id = str(uuid.uuid4())
    task_record = {
        "id": task_id,
        "task_id": task_id,
        "task_type": task_type_str,
        "action_type": task_type_str,
        "step_name": task_type_str,
        "workflow_name": state.get("current_agent", "cascade_workflow") if state else "cascade_workflow",
        "node_id": nid,
        "correlation_id": corr_id,
        "status": "pending",
        "details": task_details,
        "payload": task_details,
        "task_data": {
            **task_details,
            "risk_level": risk_level,
            "node_id": nid,
        },
        "expires_at": expires_at.isoformat(),
        "decided_by": None,
        "decided_at": None,
        "decision_note": None,
        "created_at": datetime.now(UTC).isoformat(),
    }

    # Persist task in database if available
    if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY:
        try:
            client = get_service_db_client()
            if client:
                client.table("hitl_tasks").insert(task_record).execute()
        except Exception as exc:
            logger.warning("DB hitl_tasks insert failed (%s); saved to in-memory store.", exc)

    _in_memory_hitl_tasks[task_id] = task_record

    # 3. Write entry to audit_ledger
    record_audit_log(
        action_type="HITL_TASK_CREATED",
        payload={
            "task_id": task_id,
            "task_type": task_type_str,
            "correlation_id": corr_id,
            "details": task_details,
            "expires_at": task_record["expires_at"],
        },
        node_id=nid,
    )

    # 4. Emit SSE events (both event type "hitl" for backwards compatibility and "hitl_pending")
    hitl_event = EventEnvelope(
        event_id=str(uuid.uuid4()),
        type="hitl",
        node_id=nid,
        correlation_id=corr_id,
        payload={
            "task_id": task_id,
            "task_type": task_type_str,
            "event_type": "hitl_pending",
            "details": task_details,
            "expires_at": task_record["expires_at"],
        },
    )
    await in_process_event_bus.publish("hitl", hitl_event)

    # 5. Update state flags if state dictionary passed
    if state is not None:
        state["hitl_pending"] = True
        state["hitl_task_id"] = task_id
        state["status"] = "waiting_hitl"

    logger.info("HITL task created: id=%s type=%s expires_at=%s", task_id, task_type_str, task_record["expires_at"])

    # 6. Attempt LangGraph native interrupt() if requested or in checkpointer context
    if state is not None and (
        state.get("use_interrupt")
        or state.get("current_agent") == "stockist_order_agent"
        or task_type_str == "reorder_approval"
    ):
        try:
            from langgraph.types import interrupt

            resume_data = interrupt({
                "task_id": task_id,
                "task_type": task_type_str,
                "details": task_details,
                "payload": task_details,
                "risk_level": risk_level,
                "hitl_pending": True,
            })
            if state is not None:
                state["hitl_pending"] = False
            if isinstance(resume_data, dict):
                return resume_data
            return {
                "status": "resumed",
                "approved": True,
                "resume_data": resume_data,
                "task_id": task_id,
            }
        except RuntimeError:
            # Outside runnable context
            pass

    return {
        "status": "waiting_hitl",
        "task_id": task_id,
        "approved": False,
        "requires_hitl": True,
        "task_type": task_type_str,
        "expires_at": task_record["expires_at"],
    }
