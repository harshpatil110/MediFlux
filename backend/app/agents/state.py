"""State schemas for LangGraph execution graphs across the MediFlux agent ecosystem."""

from typing import Any, TypedDict


class AgentGraphState(TypedDict):
    """Shared LangGraph state container across MediFlux autonomous agent workflows."""

    correlation_id: str
    trace_id: str
    node_id: str
    user_id: str
    messages: list[dict[str, Any]]
    current_agent: str
    next_step: str
    data: dict[str, Any]
    hitl_pending: bool
    hitl_task_id: str | None

