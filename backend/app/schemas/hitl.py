"""Schemas for Human-in-the-Loop (HITL) approval workflows and decisions."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class HITLDecisionRequest(BaseModel):
    """Payload for submitting an approval or rejection decision on a pending HITL task."""

    decision: Literal["approve", "approved", "reject", "rejected"] = Field(
        default="approved",
        description="Decision choice: 'approve'/'approved' to execute gated action, 'reject'/'rejected' to abort/cancel.",
    )
    note: str | None = Field(
        default=None,
        description="Justification note for human decision audit trail.",
    )
    reason: str | None = Field(
        default=None,
        description="Alias for justification note.",
    )
    decided_by: str | None = Field(
        default=None,
        description="Operator identity submitting the decision.",
    )


class HITLTaskResponse(BaseModel):
    """Schema representing an individual HITL task."""

    id: str
    task_type: str
    title: str | None = None
    summary: str | None = None
    risk_level: str = "medium"
    requesting_agent: str | None = None
    node_id: str | None = None
    node_name: str | None = None
    correlation_id: str | None = None
    status: str = "pending"  # pending, approved, rejected, expired
    details: dict[str, Any] = Field(default_factory=dict)
    payload: dict[str, Any] = Field(default_factory=dict)
    reasoning: str | None = None
    audit_entry_id: str | None = None
    allowed_roles: list[str] = Field(default_factory=list)
    can_current_user_decide: bool = False
    cannot_decide_reason: str | None = None
    expires_at: str | datetime | None = None
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
    resumed_workflow: dict[str, Any] | None = None
    outcome: str | None = None  # "resumed_graph" | "rejected" | "expired" | status
    already_finalized: bool = False
    resumed_cascade_correlation_id: str | None = None
    audit_entry_id: str | None = None


class HITLTriggerRequest(BaseModel):
    """Payload for triggering a simulated HITL task."""

    task_type: str = Field(default="cross_border_shipment", description="HITL task type to simulate")
    correlation_id: str | None = Field(default=None, description="Optional correlation ID to link with a cascade")
    details: dict[str, Any] | None = Field(default=None, description="Custom details/payload override")
    node_id: str | None = Field(default=None, description="Originating node ID")


class HITLPoliciesResponse(BaseModel):
    """Response returned by GET /api/v1/hitl/policies."""

    policies: dict[str, dict[str, Any]] = Field(default_factory=dict)
