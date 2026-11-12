"""Human-in-the-Loop (HITL) primitives and approval workflows for MediFlux agents."""

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from langgraph.types import interrupt

from app.agents.state import AgentGraphState
from app.core.config import settings
from app.core.security import get_service_db_client
from app.events.bus import in_process_event_bus
from app.events.models import EventEnvelope

logger = logging.getLogger("mediflux.agents.hitl")

# In-memory store for HITL tasks in offline test environments
_in_memory_hitl_tasks: dict[str, dict[str, Any]] = {}


def get_hitl_task(task_id: str) -> dict[str, Any] | None:
    """Retrieve an in-memory HITL task definition."""
    return _in_memory_hitl_tasks.get(task_id)


def resolve_hitl_task(task_id: str, status: str = "approved", decision_reason: str = "") -> None:
    """Update status of a HITL task."""
    if task_id in _in_memory_hitl_tasks:
        _in_memory_hitl_tasks[task_id]["status"] = status
        _in_memory_hitl_tasks[task_id]["decision_reason"] = decision_reason


def clear_hitl_tasks() -> None:
    """Clear in-memory HITL tasks."""
    _in_memory_hitl_tasks.clear()


def get_in_memory_hitl_tasks() -> list[dict[str, Any]]:
    """Retrieve all in-memory HITL tasks."""
    return list(_in_memory_hitl_tasks.values())


def create_hitl_task(
    task_type: str,
    payload: dict[str, Any],
    correlation_id: str = "",
    node_id: str = "00000000-0000-0000-0000-000000000000",
    workflow_name: str = "manufacturer_scheduler",
    risk_level: str = "high",
) -> dict[str, Any]:
    """Create and persist a pending HITL task record in database and in-memory store."""
    task_id = str(uuid.uuid4())
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
        "status": "pending",
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


async def request_human_approval(
    state: AgentGraphState,
    task_type: str,
    payload: dict[str, Any],
    risk_level: str = "medium",
) -> Any:
    """Pause graph execution, record pending task in hitl_tasks, emit event, and trigger LangGraph interrupt.

    When resumed, the return value of `interrupt()` will be returned to the caller.
    """
    task_id = str(uuid.uuid4())
    correlation_id = state.get("correlation_id", str(uuid.uuid4()))
    node_id = state.get("node_id", "00000000-0000-0000-0000-000000000000")
    workflow_name = state.get("current_agent", "autonomous_workflow")

    task_record = {
        "id": task_id,
        "correlation_id": correlation_id,
        "workflow_name": workflow_name,
        "step_name": task_type,
        "task_data": {
            **payload,
            "risk_level": risk_level,
            "node_id": node_id,
        },
        "status": "pending",
    }

    # 1. Persist to database if available
    if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY:
        try:
            client = get_service_db_client()
            client.table("hitl_tasks").insert(task_record).execute()
        except Exception as exc:
            logger.warning("Database hitl_tasks insertion failed (%s); using in-memory store.", exc)

    _in_memory_hitl_tasks[task_id] = task_record

    # 2. Update state flags
    state["hitl_pending"] = True
    state["hitl_task_id"] = task_id

    # 3. Publish to hitl topic on Event Bus
    hitl_event = EventEnvelope(
        event_id=str(uuid.uuid4()),
        type="hitl",
        node_id=str(node_id),
        correlation_id=correlation_id,
        payload={
            "task_id": task_id,
            "task_type": task_type,
            "workflow": workflow_name,
            "risk_level": risk_level,
            "details": payload,
        },
    )
    await in_process_event_bus.publish("hitl", hitl_event)

    logger.info(
        "HITL interrupt initiated: task_id=%s workflow=%s type=%s risk=%s",
        task_id,
        workflow_name,
        task_type,
        risk_level,
    )

    # 4. Trigger LangGraph interrupt primitive to pause execution
    resume_data = interrupt({
        "task_id": task_id,
        "task_type": task_type,
        "payload": payload,
        "risk_level": risk_level,
        "hitl_pending": True,
    })

    # When resumed via graph.invoke(Command(resume=...)), state is updated
    state["hitl_pending"] = False
    return resume_data
