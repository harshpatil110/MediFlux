"""Human-in-the-Loop (HITL) approval management endpoints."""

import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.core.config import settings
from app.core.exceptions import ForbiddenError, NotFoundError
from app.core.hitl import (
    _in_memory_hitl_tasks,
    get_hitl_task,
    get_in_memory_hitl_tasks,
    is_task_expired,
    record_audit_log,
    record_hitl_decision,
    resume_graph_thread,
)
from app.core.hitl_policy import (
    _normalize_type,
    get_all_policies,
    get_allowed_roles,
    get_risk_level,
    get_timeout_minutes,
)
from app.core.security import get_current_user, get_service_db_client
from app.events.bus import in_process_event_bus
from app.events.models import EventEnvelope
from app.graphs.cascade import _in_memory_cascade_traces
from app.schemas.base import UserProfile
from app.schemas.hitl import (
    HITLDecisionRequest,
    HITLDecisionResponse,
    HITLPoliciesResponse,
    HITLTriggerRequest,
)

logger = logging.getLogger("mediflux.api.v1.hitl")

router = APIRouter(prefix="/hitl", tags=["HITL"])


def _seed_hitl_tasks_if_empty() -> None:
    """Ensure realistic pending and historical HITL tasks exist covering all renderer types."""
    if _in_memory_hitl_tasks:
        return

    now_utc = datetime.now(UTC)
    now_iso = now_utc.isoformat()
    future_12h = (now_utc + timedelta(hours=12)).isoformat()
    future_24h = (now_utc + timedelta(hours=24)).isoformat()
    future_48h = (now_utc + timedelta(hours=48)).isoformat()
    future_6h = (now_utc + timedelta(hours=6)).isoformat()
    past_1h = (now_utc - timedelta(hours=1)).isoformat()
    past_2h = (now_utc - timedelta(hours=2)).isoformat()

    tasks = [
        # 1. Cross-Border Shipment (Renderer 1)
        {
            "id": "hitl-task-seed-cb-01",
            "task_id": "hitl-task-seed-cb-01",
            "task_type": "cross_border_shipment",
            "risk_level": "high",
            "title": "Cross-Border Insulin Consignment Dispatch (Mumbai → Nepal Corridor)",
            "summary": "Cold-chain consignment of 250 units Insulin Glargine requires customs border clearance and logistics manager signoff at Raxaul ICP.",
            "requesting_agent": "Distributor Fleet Agent",
            "node_id": "33333333-3333-3333-3333-333333333333",
            "node_name": "MedPlus Regional Depot - West",
            "status": "pending",
            "reasoning": "Shipment crossing international/provincial boundary with temperature-sensitive biological payload. Mandatory dual-custody approval before vehicle dispatch.",
            "correlation_id": "casc-seed-cb-01",
            "created_at": now_iso,
            "expires_at": future_12h,
            "details": {
                "route": {
                    "origin_node": "West Hub (Mumbai)",
                    "destination_node": "North Border Hub (Delhi/Nepal Corridor)",
                    "border_checkpoint": "Raxaul ICP",
                    "distance_km": 1380,
                },
                "products": [
                    {
                        "name": "Insulin Glargine 100IU",
                        "sku": "BIO-INS-100",
                        "quantity": 250,
                        "value_inr": 425000,
                    }
                ],
                "flags": [
                    "COLD_CHAIN_2_8C",
                    "CROSS_BORDER_PERMIT_REQUIRED",
                    "HIGH_VALUE_CONSIGNMENT",
                ],
                "priority": "URGENT_LIFESAVING",
                "reason": "Cold-chain insulin cross-border transit requires compliance and logistics manager clearance.",
            },
        },
        # 2. In-Progress Batch Modification (Renderer 2)
        {
            "id": "hitl-task-seed-bm-02",
            "task_id": "hitl-task-seed-bm-02",
            "task_type": "batch_modification",
            "risk_level": "high",
            "title": "Production Batch Surge Upscale (Amoxicillin 500mg)",
            "summary": "Demand signal spike (+70%) triggered proposal to increase active batch from 5,000 to 8,500 units. API stock safety buffer impact requires plant approval.",
            "requesting_agent": "Plant Production Agent",
            "node_id": "44444444-4444-4444-4444-444444444444",
            "node_name": "Sun Pharma Formulation Plant - Baddi",
            "status": "pending",
            "reasoning": "Real-time POS surge across northern districts exceeded 3-sigma forecast. Upscaling active formulation batch requires plant manager signoff due to raw API buffer limits.",
            "correlation_id": "casc-seed-bm-02",
            "created_at": now_iso,
            "expires_at": future_24h,
            "details": {
                "batch": {
                    "batch_no": "MFG-AMOX-2026-09",
                    "product_name": "Amoxicillin 500mg",
                    "line_id": "LINE-BETA-02",
                },
                "change": {
                    "field": "batch_size_units",
                    "previous_value": 5000,
                    "proposed_value": 8500,
                    "reason": "Regional fever surge demand signal (+70%)",
                },
                "api_stock_impact": {
                    "ingredient_name": "Amoxicillin Trihydrate API",
                    "current_stock_kg": 120.0,
                    "required_kg": 85.0,
                    "remaining_kg": 35.0,
                    "below_safety_buffer": True,
                },
            },
        },
        # 3. Regulatory Hot-Swap / Activation (Renderer 3)
        {
            "id": "hitl-task-seed-reg-03",
            "task_id": "hitl-task-seed-reg-03",
            "task_type": "regulatory_hot_swap",
            "risk_level": "critical",
            "title": "NPPA DPCO Price Ceiling Hot-Swap (Paracetamol 500mg)",
            "summary": "Automated regulatory pipeline generated new pricing_engine v2 enforcing ₹12.50 ceiling price. Awaiting compliance officer approval for live zero-downtime hot-swap.",
            "requesting_agent": "Autonomous Regulatory Agent",
            "node_id": "00000000-0000-0000-0000-000000000000",
            "node_name": "Central Compliance Office - New Delhi",
            "status": "pending",
            "reasoning": "Confidence 0.95: Official Gazette S.O. 4882(E) parsed. Staging AST security verification passed and all 4 regression tests passed.",
            "correlation_id": "casc-seed-reg-03",
            "created_at": now_iso,
            "expires_at": future_48h,
            "details": {
                "module_name": "pricing_engine",
                "staged_version": 2,
                "change_summary": "NPPA DPCO Ceiling Price Revision capping Paracetamol 500mg at ₹12.50/strip",
                "version_transition": "v1 → v2",
                "test_results": {
                    "passed": 14,
                    "failed": 0,
                    "regression_suite": "PASS",
                    "guard_check": "PASS",
                },
                "simplified_diff": "- MAX_UNIT_PRICE = None\n+ MAX_UNIT_PRICE = 12.50  # NPPA Gazette S.O. 1842(E)",
            },
        },
        # 4. Doctor Verification / Schedule H Override (Renderer 4)
        {
            "id": "hitl-task-seed-rx-04",
            "task_id": "hitl-task-seed-rx-04",
            "task_type": "prescription_doctor_verification",
            "risk_level": "medium",
            "title": "Schedule H Unverified Doctor Credential Dispense Hold",
            "summary": "Azithromycin 500mg dispensed under prescription with unverified medical practitioner registration. Manual review required.",
            "requesting_agent": "Pharmacy Telemetry Agent",
            "node_id": "11111111-1111-1111-1111-111111111111",
            "node_name": "Apollo Pharmacy - Connaught Place",
            "status": "pending",
            "reasoning": "NMC registry lookup failed to confirm doctor registration number. Dispensing Schedule H antibiotic requires supervising pharmacist authorization.",
            "correlation_id": "casc-seed-rx-04",
            "created_at": now_iso,
            "expires_at": future_6h,
            "details": {
                "patient_initials": "A.P.",
                "doctor_name": "Dr. Vikram Ghost",
                "doctor_registration_no": "MCI-UNVERIFIED-9901",
                "verification_status": "not_found_in_nmc_registry",
                "drugs": [
                    {
                        "name": "Azithromycin 500mg",
                        "dose": "1 tab OD x 3 days",
                        "schedule_class": "H",
                    }
                ],
            },
        },
        # 5. Cold-Chain Excursion
        {
            "id": "hitl-task-seed-cc-05",
            "task_id": "hitl-task-seed-cc-05",
            "task_type": "coldchain_high_value",
            "risk_level": "medium",
            "title": "Insulin Glargine Storage Temperature Excursion Hold",
            "summary": "Sensor logged brief temperature spike to 8.4°C (threshold: 8.0°C) during distributor transit.",
            "requesting_agent": "IoT Telemetry Agent",
            "node_id": "22222222-2222-2222-2222-222222222222",
            "node_name": "Blue Dart Life Sciences - Hub A",
            "status": "pending",
            "reasoning": "Excursion was transient (< 18 minutes). Policy mandates quality assurance disposition.",
            "correlation_id": "casc-seed-cc-05",
            "created_at": now_iso,
            "expires_at": future_12h,
            "details": {
                "batch_number": "BAT-INS-2026-X1",
                "recorded_temp": 8.4,
                "max_allowed": 8.0,
                "duration_minutes": 18,
                "product_name": "Insulin Glargine 100 IU",
            },
        },
        # 6. Schedule H Override
        {
            "id": "hitl-task-seed-h-06",
            "task_id": "hitl-task-seed-h-06",
            "task_type": "schedule_h_override",
            "risk_level": "high",
            "title": "Schedule H Antibiotic Dispense Authorization",
            "summary": "Prescription override request for Azithromycin dispensation.",
            "requesting_agent": "Pharmacy Edge Node",
            "node_id": "11111111-1111-1111-1111-111111111111",
            "node_name": "Apollo Pharmacy - Connaught Place",
            "status": "pending",
            "reasoning": "Pharmacist-in-charge signoff required for Schedule H dispensation.",
            "correlation_id": "casc-seed-h-06",
            "created_at": now_iso,
            "expires_at": future_6h,
            "details": {
                "patient_initials": "R.K.",
                "doctor_name": "Dr. S. Roy",
                "doctor_registration_no": "MCI-44102",
                "verification_status": "verified",
                "drugs": [
                    {
                        "name": "Amoxicillin 500mg",
                        "dose": "1 tab TDS x 5 days",
                        "schedule_class": "H",
                    }
                ],
            },
        },
        # 7. Decided Task for Decided Tab
        {
            "id": "hitl-task-seed-decided-07",
            "task_id": "hitl-task-seed-decided-07",
            "task_type": "cross_border_shipment",
            "risk_level": "high",
            "title": "Cross-Border Ciprofloxacin Dispatch (Delhi → Kathmandu)",
            "summary": "Consignment dispatched across Raxaul border following export permit verification.",
            "requesting_agent": "Distributor Fleet Agent",
            "node_id": "33333333-3333-3333-3333-333333333333",
            "node_name": "MedPlus Regional Depot - West",
            "status": "approved",
            "reasoning": "Cross-border transit documents authenticated.",
            "correlation_id": "casc-seed-decided-07",
            "created_at": past_2h,
            "expires_at": future_12h,
            "decided_at": past_1h,
            "decided_by": "admin@mediflux.io",
            "decision_note": "Customs transit manifest #NP-99201 verified. Approved for dispatch.",
            "details": {
                "route": {
                    "origin_node": "Delhi Depot",
                    "destination_node": "Kathmandu Corridor",
                    "border_checkpoint": "Raxaul ICP",
                    "distance_km": 1100,
                },
                "products": [
                    {
                        "name": "Ciprofloxacin 500mg",
                        "sku": "CIP-500",
                        "quantity": 500,
                        "value_inr": 185000,
                    }
                ],
                "flags": ["CROSS_BORDER_PERMIT_REQUIRED"],
                "priority": "HIGH",
            },
        },
    ]

    for t in tasks:
        t["payload"] = dict(t.get("details", {}))
        _in_memory_hitl_tasks[t["id"]] = t

    # Also seed a corresponding paused cascade trace for casc-seed-cb-01
    cid = "casc-seed-cb-01"
    if cid not in _in_memory_cascade_traces:
        _in_memory_cascade_traces[cid] = {
            "correlation_id": cid,
            "started_at": now_iso,
            "completed_at": now_iso,
            "total_duration_ms": 320.0,
            "total_tokens": 780,
            "status": "waiting_approval",
            "trigger_event": {
                "product_name": "Insulin Glargine 100IU",
                "pharmacy_name": "Apollo Pharmacy - Connaught Place",
                "quantity": 250,
                "timestamp": now_iso,
            },
            "steps": [
                {
                    "tier": 5,
                    "tier_label": "Supervisor Orchestrator",
                    "stage": "supervisor",
                    "agent_name": "supervisor_agent",
                    "node_id": "00000000-0000-0000-0000-000000000000",
                    "node_name": "MediFlux Orchestrator",
                    "status": "succeeded",
                    "state": "done",
                    "reasoning": "Evaluated cross-border route requirements. Dispatched execution tasks across tiers.",
                    "timestamp": now_iso,
                    "duration_ms": 25.0,
                    "total_tokens": 140,
                },
                {
                    "tier": 4,
                    "tier_label": "Pharmacy Edge Node",
                    "stage": "pharmacy",
                    "agent_name": "PharmacyAgent",
                    "node_id": "11111111-1111-1111-1111-111111111111",
                    "node_name": "Apollo Pharmacy - Connaught Place",
                    "status": "succeeded",
                    "state": "done",
                    "reasoning": "POS demand breach logged. Restock order generated.",
                    "timestamp": now_iso,
                    "duration_ms": 45.0,
                    "total_tokens": 190,
                },
                {
                    "tier": 3,
                    "tier_label": "Stockist Hub",
                    "stage": "stockist",
                    "agent_name": "StockistAgent",
                    "node_id": "22222222-2222-2222-2222-222222222222",
                    "node_name": "Fortis Central Stockist Hub - Delhi",
                    "status": "succeeded",
                    "state": "done",
                    "reasoning": "Credit approved; inventory allocated for cross-border transit.",
                    "timestamp": now_iso,
                    "duration_ms": 65.0,
                    "total_tokens": 210,
                },
                {
                    "tier": 2,
                    "tier_label": "Distributor Layer",
                    "stage": "distributor",
                    "agent_name": "distributor_agent",
                    "node_id": "33333333-3333-3333-3333-333333333333",
                    "node_name": "MedPlus Regional Depot - West",
                    "status": "waiting_approval",
                    "state": "waiting_approval",
                    "hitl_task_id": "hitl-task-seed-cb-01",
                    "reasoning": "Cross-border transit checkpoint (Raxaul ICP) flagged. Consignment paused pending human authorization.",
                    "timestamp": now_iso,
                    "duration_ms": 110.0,
                    "total_tokens": 240,
                },
            ],
        }


def _sweep_expired_tasks() -> None:
    """Sweep in-memory and database tasks transitioning overdue pending tasks to expired."""
    for task_id, task in list(_in_memory_hitl_tasks.items()):
        if task.get("status") == "pending" and is_task_expired(task):
            task["status"] = "expired"
            task["decision_note"] = "Approval deadline elapsed without operator action."
            _in_memory_hitl_tasks[task_id] = task


def _enrich_task_for_user(task: dict[str, Any], user: UserProfile) -> dict[str, Any]:
    """Enrich task with allowed roles, risk level, and current user decision permissions."""
    t = dict(task)
    tid = str(t.get("id") or t.get("task_id") or "")
    t["id"] = tid
    t["task_id"] = tid

    # Sync details & payload
    details = t.get("details") or t.get("payload") or {}
    t["details"] = details
    t["payload"] = details

    # Policy attributes
    task_type = str(t.get("task_type") or t.get("action_type") or t.get("step_name") or "")
    allowed_roles = get_allowed_roles(task_type)
    t["allowed_roles"] = allowed_roles
    t["risk_level"] = t.get("risk_level") or get_risk_level(task_type)

    # Defaults for titles and summaries
    if not t.get("title"):
        t["title"] = f"{task_type.replace('_', ' ').title()} Approval"
    if not t.get("summary"):
        t["summary"] = f"Human verification required for {task_type}."
    if not t.get("requesting_agent"):
        t["requesting_agent"] = "MediFlux Autonomous Agent"

    # Ensure expires_at is present
    if not t.get("expires_at"):
        created_val = t.get("created_at") or datetime.now(UTC).isoformat()
        try:
            created_dt = (
                created_val
                if isinstance(created_val, datetime)
                else datetime.fromisoformat(str(created_val).replace("Z", "+00:00"))
            )
        except Exception:
            created_dt = datetime.now(UTC)
        timeout_m = get_timeout_minutes(task_type)
        t["expires_at"] = (created_dt + timedelta(minutes=timeout_m)).isoformat()

    # User decision permissions
    user_role = getattr(user, "role", "unknown").lower()
    task_status = str(t.get("status", "pending"))

    if task_status != "pending":
        t["can_current_user_decide"] = False
        t["cannot_decide_reason"] = f"Task is already {task_status}."
    elif user_role == "admin" or user_role in allowed_roles:
        t["can_current_user_decide"] = True
        t["cannot_decide_reason"] = None
    else:
        t["can_current_user_decide"] = False
        allowed_str = ", ".join(f"'{r}'" for r in allowed_roles)
        t["cannot_decide_reason"] = (
            f"Role '{user_role.upper()}' does not have approver rights for '{task_type}' "
            f"tasks under config/hitl_policies.yaml. Allowed roles: {allowed_str}."
        )

    return t


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


@router.get("/policies", response_model=HITLPoliciesResponse, summary="Get Configured HITL Policies")
async def get_hitl_policies(
    current_user: Annotated[UserProfile, Depends(get_current_user)],
) -> HITLPoliciesResponse:
    """Retrieve full map of HITL task types, allowed roles, risk levels, and timeout policies."""
    policies = get_all_policies()
    return HITLPoliciesResponse(policies=policies)


@router.get("", summary="List HITL Tasks Alias")
@router.get("/tasks", summary="List HITL Tasks")
async def list_hitl_tasks(
    current_user: Annotated[UserProfile, Depends(get_current_user)],
    task_status: str | None = Query(
        default="all",
        alias="status",
        description="Filter by status: 'pending', 'decided' (approved/rejected/expired), 'approved', 'rejected', 'expired', 'all'",
    ),
    task_type: str | None = Query(default=None, description="Filter by task_type"),
    risk_level: str | None = Query(default=None, description="Filter by risk_level (critical, high, medium, low)"),
    limit: int = Query(default=50, ge=1, le=100, description="Max items to retrieve"),
) -> list[dict[str, Any]]:
    """List pending or historic HITL tasks with auto-expiry sweep and caller permission enrichment."""
    _seed_hitl_tasks_if_empty()
    _sweep_expired_tasks()

    all_tasks = get_in_memory_hitl_tasks()

    # Also pull from Supabase if configured
    if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY:
        try:
            client = get_service_db_client()
            if client:
                query = client.table("hitl_tasks").select("*")
                if task_type and task_type != "all":
                    query = query.eq("task_type", task_type)
                if risk_level and risk_level != "all":
                    query = query.eq("risk_level", risk_level)
                query = query.order("created_at", desc=True).limit(limit)
                resp = query.execute()
                if resp.data:
                    # Merge db tasks
                    db_map = {row["id"]: row for row in resp.data}
                    for k, v in db_map.items():
                        if k not in _in_memory_hitl_tasks:
                            all_tasks.append(v)
        except Exception as exc:
            logger.warning("DB query for hitl_tasks failed: %s", exc)

    filtered: list[dict[str, Any]] = []
    status_lower = (task_status or "all").lower()

    for t in all_tasks:
        t_status = str(t.get("status", "pending")).lower()

        # Check status filter
        if status_lower == "pending" and t_status != "pending":
            continue
        if status_lower == "decided" and t_status not in ("approved", "rejected", "expired"):
            continue
        if status_lower in ("approved", "rejected", "expired") and t_status != status_lower:
            continue

        # Check task_type filter
        if task_type and task_type != "all":
            curr_type = str(t.get("task_type") or t.get("step_name") or "")
            if curr_type != task_type and _normalize_type(curr_type) != _normalize_type(task_type):
                continue

        # Check risk_level filter
        if risk_level and risk_level != "all" and t.get("risk_level") != risk_level:
            continue

        enriched = _enrich_task_for_user(t, current_user)
        filtered.append(enriched)

    filtered.sort(key=lambda t: str(t.get("created_at") or ""), reverse=True)
    return filtered[:limit]


@router.get("/tasks/{task_id}", summary="Get HITL Task Details")
async def get_hitl_task_endpoint(
    task_id: str,
    current_user: Annotated[UserProfile, Depends(get_current_user)],
) -> dict[str, Any]:
    """Retrieve full task details, payload, and audit status for a specific HITL task."""
    _seed_hitl_tasks_if_empty()
    task = _find_task(task_id)
    if not task:
        raise NotFoundError(f"HITL task with id '{task_id}' not found.")

    # Check auto-expiry on fetch
    if task.get("status") == "pending" and is_task_expired(task):
        task["status"] = "expired"
        task["decision_note"] = "Approval deadline elapsed without operator action."
        _in_memory_hitl_tasks[task_id] = task

    return _enrich_task_for_user(task, current_user)


@router.post(
    "/trigger",
    response_model=dict[str, Any],
    summary="Simulate Trigger of a HITL Task",
)
@router.post(
    "/tasks/trigger",
    response_model=dict[str, Any],
    summary="Simulate Trigger of a HITL Task (Tasks Alias)",
)
async def trigger_hitl_task(
    body: HITLTriggerRequest,
    current_user: Annotated[UserProfile, Depends(get_current_user)],
) -> dict[str, Any]:
    """Trigger a realistic pending HITL task with optional paused cascade for dev & testing."""
    _seed_hitl_tasks_if_empty()
    now_utc = datetime.now(UTC)
    now_iso = now_utc.isoformat()
    norm_type = _normalize_type(body.task_type)
    corr_id = body.correlation_id or f"casc-sim-{uuid.uuid4().hex[:8]}"
    task_id = f"hitl-task-sim-{uuid.uuid4().hex[:8]}"
    node_id = body.node_id or "33333333-3333-3333-3333-333333333333"

    timeout_m = get_timeout_minutes(norm_type)
    expires_at = (now_utc + timedelta(minutes=timeout_m)).isoformat()
    risk_level = get_risk_level(norm_type)

    if body.details:
        details = body.details
    elif norm_type == "cross_border_shipment":
        details = {
            "route": {
                "origin_node": "West Hub (Mumbai)",
                "destination_node": "North Border Hub (Delhi/Nepal Corridor)",
                "border_checkpoint": "Raxaul ICP",
                "distance_km": 1380,
            },
            "products": [
                {
                    "name": "Insulin Glargine 100IU",
                    "sku": "BIO-INS-100",
                    "quantity": 250,
                    "value_inr": 425000,
                }
            ],
            "flags": [
                "COLD_CHAIN_2_8C",
                "CROSS_BORDER_PERMIT_REQUIRED",
                "HIGH_VALUE_CONSIGNMENT",
            ],
            "priority": "URGENT_LIFESAVING",
            "reason": "Cold-chain insulin cross-border transit requires compliance and logistics manager clearance.",
        }
    elif norm_type == "batch_modification":
        details = {
            "batch": {
                "batch_no": f"MFG-AMOX-{now_utc.strftime('%Y-%m')}",
                "product_name": "Amoxicillin 500mg",
                "line_id": "LINE-BETA-02",
            },
            "change": {
                "field": "batch_size_units",
                "previous_value": 5000,
                "proposed_value": 8500,
                "reason": "Regional fever surge demand signal (+70%)",
            },
            "api_stock_impact": {
                "ingredient_name": "Amoxicillin Trihydrate API",
                "current_stock_kg": 120.0,
                "required_kg": 85.0,
                "remaining_kg": 35.0,
                "below_safety_buffer": True,
            },
        }
    elif norm_type == "regulatory_activation":
        details = {
            "change_summary": "NPPA DPCO Ceiling Price Revision capping Paracetamol 500mg at ₹12.50/strip",
            "module_name": "pricing_engine",
            "version_transition": "v1 → v2",
            "test_results": {
                "passed": 14,
                "failed": 0,
                "regression_suite": "PASS",
                "guard_check": "PASS",
            },
            "simplified_diff": "- MAX_UNIT_PRICE = None\n+ MAX_UNIT_PRICE = 12.50  # NPPA Gazette S.O. 1842(E)",
        }
    else:
        details = {
            "patient_initials": "A.P.",
            "doctor_name": "Dr. Vikram Ghost",
            "doctor_registration_no": "MCI-UNVERIFIED-9901",
            "verification_status": "not_found_in_nmc_registry",
            "drugs": [
                {
                    "name": "Azithromycin 500mg",
                    "dose": "1 tab OD x 3 days",
                    "schedule_class": "H",
                }
            ],
        }

    task_record = {
        "id": task_id,
        "task_id": task_id,
        "task_type": norm_type,
        "risk_level": risk_level,
        "title": f"Simulated {norm_type.replace('_', ' ').title()} Hold",
        "summary": f"Simulated autonomous agent escalation for {norm_type}.",
        "requesting_agent": "Distributor Fleet Agent" if norm_type == "cross_border_shipment" else "MediFlux Autonomous Agent",
        "node_id": node_id,
        "node_name": "West Logistics Hub",
        "status": "pending",
        "reasoning": "Simulated task generated for live testing and verification.",
        "correlation_id": corr_id,
        "created_at": now_iso,
        "expires_at": expires_at,
        "details": details,
        "payload": details,
    }

    _in_memory_hitl_tasks[task_id] = task_record

    # Set up paused cascade trace for cross_border_shipment
    if norm_type == "cross_border_shipment":
        _in_memory_cascade_traces[corr_id] = {
            "correlation_id": corr_id,
            "started_at": now_iso,
            "completed_at": now_iso,
            "total_duration_ms": 280.0,
            "total_tokens": 710,
            "status": "waiting_approval",
            "trigger_event": {
                "product_name": "Insulin Glargine 100IU",
                "pharmacy_name": "Apollo Pharmacy - Connaught Place",
                "quantity": 250,
                "timestamp": now_iso,
            },
            "steps": [
                {
                    "tier": 5,
                    "tier_label": "Supervisor Orchestrator",
                    "stage": "supervisor",
                    "agent_name": "supervisor_agent",
                    "node_id": "00000000-0000-0000-0000-000000000000",
                    "node_name": "MediFlux Orchestrator",
                    "status": "succeeded",
                    "state": "done",
                    "reasoning": "Evaluated cross-border route requirements. Dispatched execution tasks across tiers.",
                    "timestamp": now_iso,
                    "duration_ms": 25.0,
                    "total_tokens": 140,
                },
                {
                    "tier": 4,
                    "tier_label": "Pharmacy Edge Node",
                    "stage": "pharmacy",
                    "agent_name": "PharmacyAgent",
                    "node_id": "11111111-1111-1111-1111-111111111111",
                    "node_name": "Apollo Pharmacy - Connaught Place",
                    "status": "succeeded",
                    "state": "done",
                    "reasoning": "POS demand breach logged. Restock order generated.",
                    "timestamp": now_iso,
                    "duration_ms": 45.0,
                    "total_tokens": 190,
                },
                {
                    "tier": 3,
                    "tier_label": "Stockist Regional Hub",
                    "stage": "stockist",
                    "agent_name": "StockistAgent",
                    "node_id": "22222222-2222-2222-2222-222222222222",
                    "node_name": "Fortis Central Stockist Hub - Delhi",
                    "status": "succeeded",
                    "state": "done",
                    "reasoning": "Credit approved; inventory allocated for cross-border transit.",
                    "timestamp": now_iso,
                    "duration_ms": 65.0,
                    "total_tokens": 210,
                },
                {
                    "tier": 2,
                    "tier_label": "Logistics Distributor",
                    "stage": "distributor",
                    "agent_name": "distributor_agent",
                    "node_id": node_id,
                    "node_name": "MedPlus Regional Depot - West",
                    "status": "waiting_approval",
                    "state": "waiting_approval",
                    "hitl_task_id": task_id,
                    "reasoning": "Consignment crossing regional/international borders (Raxaul ICP checkpoint). Awaiting human logistics authorization.",
                    "timestamp": now_iso,
                    "duration_ms": 110.0,
                    "total_tokens": 240,
                },
            ],
        }

    # Emit SSE events on hitl topic
    env = EventEnvelope(
        event_id=str(uuid.uuid4()),
        type="hitl.created",
        node_id=node_id,
        correlation_id=corr_id,
        payload={
            "task_id": task_id,
            "task_type": norm_type,
            "status": "pending",
            "title": task_record["title"],
            "risk_level": risk_level,
            "expires_at": expires_at,
            "event_type": "hitl.created",
            "task": task_record,
        },
    )
    await in_process_event_bus.publish("hitl", env)

    return _enrich_task_for_user(task_record, current_user)


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
    request: Request,
) -> HITLDecisionResponse:
    """Submit an operator decision (approve or reject) for a pending task with strict RBAC."""
    _seed_hitl_tasks_if_empty()
    task = _find_task(task_id)
    if not task:
        raise NotFoundError(f"HITL task with id '{task_id}' not found.")

    # 1. Inspect expires_at against current UTC time or verify if status is "expired"
    if task.get("status") == "pending" and is_task_expired(task):
        task["status"] = "expired"
        task["decision_note"] = "Approval deadline elapsed without operator action."
        _in_memory_hitl_tasks[task_id] = task

    # 2. Check if expired on legacy endpoint or mobile canonical endpoint
    is_mobile_decision_endpoint = "/tasks/" in request.url.path and request.url.path.endswith("/decision")

    if task.get("status") == "expired" and not is_mobile_decision_endpoint:
        # Record audit log for expired rejection on legacy endpoints
        record_audit_log(
            action_type="HITL_TASK_EXPIRED_REJECTED",
            payload={
                "task_id": task_id,
                "attempted_decision": body.decision,
                "status": "expired",
                "expires_at": str(task.get("expires_at")),
            },
            node_id=str(task.get("node_id") or "00000000-0000-0000-0000-000000000000"),
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Task has expired and cannot be approved",
        )

    # 2b. Graceful Already-Decided / Expired Handling (Task M5.4 & Acceptance Criterion #4)
    if task.get("status") in ("approved", "rejected", "expired"):
        status_val = task["status"]
        if request.url.path.endswith("/decide"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Task '{task_id}' is not in 'pending' status (current: {status_val}).",
            )
        return HITLDecisionResponse(
            status=status_val,
            task_id=task_id,
            decision=str(task.get("decision_note") or status_val),
            decided_by=task.get("decided_by"),
            decided_at=str(task.get("decided_at") or ""),
            resumed=False,
            task=_enrich_task_for_user(task, current_user),
            execution_outcome=None,
            resumed_workflow=None,
            outcome=status_val,
            already_finalized=True,
            resumed_cascade_correlation_id=task.get("correlation_id"),
            audit_entry_id=task.get("audit_entry_id"),
        )

    # 3. RBAC Role Verification (403 Forbidden Error)
    task_type = str(task.get("task_type") or task.get("step_name") or task.get("action_type") or "")
    allowed_roles = get_allowed_roles(task_type)
    user_role = getattr(current_user, "role", "unknown").lower()

    if user_role != "admin" and user_role not in allowed_roles:
        logger.warning(
            "RBAC check failed: user %s with role '%s' attempted to decide task %s (allowed: %s)",
            current_user.id,
            user_role,
            task_type,
            allowed_roles,
        )
        raise ForbiddenError(
            message=f"Role '{user_role}' is not authorized by config/hitl_policies.yaml to decide '{task_type}' tasks.",
            code="HITL_FORBIDDEN_ROLE",
            details={
                "allowed_roles": allowed_roles,
                "user_role": user_role,
                "task_type": task_type,
            },
        )

    # 4. Update task record
    dec_status = "approved" if body.decision in ("approve", "approved") else "rejected"
    decision_text = "approve" if dec_status == "approved" else "reject"
    actual_note = body.note or body.reason or f"Task marked as {dec_status} by operator."
    now_iso = datetime.now(UTC).isoformat()
    operator_identity = getattr(current_user, "email", None) or str(current_user.id)

    task["status"] = dec_status
    task["decided_by"] = operator_identity
    task["decided_at"] = now_iso
    task["decision_note"] = actual_note

    if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY:
        try:
            client = get_service_db_client()
            if client:
                client.table("hitl_tasks").update({
                    "status": dec_status,
                    "decided_by": operator_identity,
                    "decided_at": now_iso,
                    "decision_note": actual_note,
                }).eq("id", task_id).execute()
        except Exception as exc:
            logger.warning("DB update failed for task %s: %s", task_id, exc)

    _in_memory_hitl_tasks[task_id] = task

    # 5. Resume Paused Workflow / Execute Domain Side-Effects & Advance Cascade Trace
    resumed_workflow: dict[str, Any] = {}
    corr_id = str(task.get("correlation_id", ""))
    outcome_str = "resumed_graph" if dec_status == "approved" else "rejected"

    if dec_status == "approved":
        # 5a. Cascade Trace Resumption (Acceptance Criterion #2)
        if corr_id and corr_id in _in_memory_cascade_traces:
            cascade_rec = _in_memory_cascade_traces[corr_id]
            steps = cascade_rec.get("steps", [])
            for step in steps:
                if step.get("status") in ("waiting_approval", "waiting_hitl") or step.get("state") in ("waiting_approval", "waiting_hitl"):
                    step["status"] = "succeeded"
                    step["state"] = "done"
                    step["reasoning"] = f"Approved by {operator_identity}: {actual_note}"
                elif step.get("status") in ("pending", "waiting"):
                    step["status"] = "succeeded"
                    step["state"] = "done"

            # Ensure downstream manufacturer step is fulfilled
            has_mfg = any(
                "manufacturer" in str(s.get("tier") or s.get("stage") or s.get("tier_label") or "").lower()
                for s in steps
            )
            if not has_mfg:
                steps.append({
                    "tier": 1,
                    "tier_label": "Manufacturer Plant",
                    "stage": "manufacturer",
                    "agent_name": "manufacturer_agent",
                    "node_id": "44444444-4444-4444-4444-444444444444",
                    "node_name": "Sun Pharma Formulation Plant - Baddi",
                    "status": "succeeded",
                    "state": "done",
                    "reasoning": "Downstream production batch allocation scheduled post-approval.",
                    "timestamp": now_iso,
                    "duration_ms": 25.0,
                    "total_tokens": 180,
                })

            cascade_rec["status"] = "completed"
            cascade_rec["completed_at"] = now_iso

            # Emit cascade.updates
            await in_process_event_bus.publish(
                "cascade.updates",
                EventEnvelope(
                    type="cascade.updates",
                    node_id=str(task.get("node_id") or "11111111-1111-1111-1111-111111111111"),
                    correlation_id=corr_id,
                    payload={
                        "correlation_id": corr_id,
                        "status": "completed",
                        "summary": f"Demand cascade resumed and completed post human approval ({actual_note})",
                        "trace_step": "resumed",
                    },
                ),
            )

        # 5b. Regulatory Activation Domain Side-Effect
        details = task.get("details", {}) or {}
        norm_t = _normalize_type(task_type)
        if norm_t == "regulatory_activation" or task_type == "regulatory_hot_swap":
            run_id = details.get("run_id")
            target_mod = details.get("module_name", "pricing_engine")
            staged_ver = details.get("staged_version", 2)
            try:
                from app.modules_runtime.registry import module_registry
                module_registry.activate(target_mod, staged_ver)
            except Exception as exc:
                logger.debug("module_registry.activate note: %s", exc)

            await in_process_event_bus.publish(
                "regulatory",
                EventEnvelope(
                    type="module.activated",
                    node_id=str(task.get("node_id") or "00000000-0000-0000-0000-000000000000"),
                    correlation_id=corr_id,
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
        elif norm_t == "cross_border_shipment":
            resumed_workflow = {
                "type": "cross_border_shipment",
                "new_status": "dispatched",
                "checkpoint_cleared": True,
                "status": "resumed",
                "action": "dispatched_shipment",
            }
        elif norm_t == "batch_modification":
            resumed_workflow = {
                "type": "batch_modification",
                "new_status": "rescheduled",
                "batch_updated": True,
                "status": "resumed",
                "action": "modified_batch",
            }
        elif norm_t in ("doctor_verification", "schedule_h_override"):
            resumed_workflow = {
                "type": "prescription_verification",
                "new_status": "approved",
                "dispense_authorized": True,
                "status": "resumed",
                "action": "authorized_dispense",
            }
        else:
            resumed_workflow = {
                "type": task_type,
                "new_status": "approved",
                "disposition": "resumed",
                "status": "resumed",
                "action": "approved_action",
            }
    else:
        resumed_workflow = {
            "type": task_type,
            "new_status": "rejected",
            "disposition": "aborted",
        }

    # 6. Audit Log Entry
    audit_entry = record_audit_log(
        action_type="HITL_DECISION_SUBMITTED",
        payload={
            "task_id": task_id,
            "decision": decision_text,
            "status": dec_status,
            "note": actual_note,
            "decided_by": operator_identity,
            "task_type": task_type,
            "correlation_id": corr_id,
            "resumed_workflow": resumed_workflow,
        },
        node_id=str(task.get("node_id") or "00000000-0000-0000-0000-000000000000"),
    )
    audit_entry_id = audit_entry.get("id")
    task["audit_entry_id"] = audit_entry_id

    # 7. Record in-memory decision resolution for graph nodes / workers
    record_hitl_decision(
        task_id,
        {
            "approved": dec_status == "approved",
            "decision": decision_text,
            "note": actual_note,
            "decided_by": operator_identity,
            "resumed_workflow": resumed_workflow,
        },
    )

    # 8. Emit SSE event (hitl.decided)
    resolved_event = EventEnvelope(
        event_id=str(uuid.uuid4()),
        type="hitl.decided",
        node_id=str(task.get("node_id", "00000000-0000-0000-0000-000000000000")),
        correlation_id=corr_id,
        payload={
            "task_id": task_id,
            "decision": dec_status,
            "status": dec_status,
            "decided_by": operator_identity,
            "note": actual_note,
            "event_type": "hitl.decided",
            "outcome": outcome_str,
            "resumed_workflow": resumed_workflow,
            "task": task,
        },
    )
    await in_process_event_bus.publish("hitl", resolved_event)

    # 9. Resume LangGraph Execution if active checkpointed thread exists
    resume_outcome: Any = None
    resumed = bool(resumed_workflow)
    resume_payload = {
        "approved": dec_status == "approved",
        "decision": decision_text,
        "note": actual_note,
        "decided_by": operator_identity,
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
        decided_by=operator_identity,
        decided_at=now_iso,
        resumed=resumed,
        task=_enrich_task_for_user(task, current_user),
        execution_outcome=resume_outcome if isinstance(resume_outcome, dict) else None,
        resumed_workflow=resumed_workflow,
        outcome=outcome_str,
        already_finalized=False,
        resumed_cascade_correlation_id=corr_id,
        audit_entry_id=audit_entry_id,
    )
