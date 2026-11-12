"""Schemas for Human-in-the-Loop (HITL) approval workflows and decisions."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class HITLDecisionRequest(BaseModel):
    """Payload for submitting an approval or rejection decision on a pending HITL task."""

    decision: Literal["approve", "reject"] = Field(
        ...,
        description="Decision choice: 'approve' to execute gated action, 'reject' to abort/cancel.",
    )
    note: str = Field(
        ...,
        min_length=3,
        description="Justification note for human decision audit trail.",
    )


class HITLTaskResponse(BaseModel):
    """Schema representing an individual HITL task."""

    id: str
    task_type: str
    node_id: str | None = None
    correlation_id: str
    status: str = "pending"  # pending, approved, rejected, expired
    details: dict[str, Any] = Field(default_factory=dict)
    expires_at: str | datetime
    decided_by: str | None = None
    decided_at: str | datetime | None = None
    decision_note: str | None = None
    created_at: str | datetime | None = None


class HITLDecisionResponse(BaseModel):
    """Response returned upon submitting a decision for a HITL task."""

    status: str
    task_id: str
    decision: str
    decided_by: str | None = None
    decided_at: str | None = None
    resumed: bool = False
    task: dict[str, Any] = Field(default_factory=dict)
    execution_outcome: dict[str, Any] | None = None
