"""HITL policy parser and rule verification."""

import logging
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger("mediflux.core.hitl_policy")

_DEFAULT_POLICIES: dict[str, dict[str, Any]] = {
    "in_progress_batch_change": {
        "enabled": True,
        "required_roles": ["manufacturer_admin", "compliance_officer", "admin"],
        "expiry_hours": 24,
        "description": "Modifying or reprioritizing a production batch currently in status in_progress.",
    },
    "cross_border_shipment": {
        "enabled": True,
        "required_roles": ["logistics_manager", "compliance_officer", "admin"],
        "expiry_hours": 12,
        "description": "Dispatching shipments crossing regional or international borders.",
    },
    "schedule_h_override": {
        "enabled": True,
        "required_roles": ["pharmacist_in_charge", "compliance_officer", "admin"],
        "expiry_hours": 6,
        "description": "Fulfilling Schedule H medication orders without automated doctor prescription verification.",
    },
    "module_activation": {
        "enabled": True,
        "required_roles": ["system_admin", "compliance_officer", "admin"],
        "expiry_hours": 48,
        "description": "Activating a new WASM or python policy module version.",
    },
    "reorder_approval": {
        "enabled": True,
        "required_roles": ["pharmacist_in_charge", "stockist_admin", "admin"],
        "expiry_hours": 24,
        "description": "Approval for bulk inventory replenishment reorders.",
    },
    "regulatory_hot_swap": {
        "enabled": True,
        "required_roles": ["compliance_officer", "admin", "pharmacist_in_charge", "system_admin"],
        "expiry_hours": 48,
        "description": "Approval for hot-swapping regulatory-mandated price ceiling or compliance module updates.",
    },
    "regulatory_clarification": {
        "enabled": True,
        "required_roles": ["compliance_officer", "admin"],
        "expiry_hours": 24,
        "description": "Clarification and verification for ambiguous or low-confidence regulatory notices.",
    },
}

_cached_policies: dict[str, dict[str, Any]] | None = None


def load_hitl_policies(policy_file_path: str = "config/hitl_policies.yaml") -> dict[str, dict[str, Any]]:
    """Load and parse YAML HITL policies from disk with fallback to defaults."""
    global _cached_policies

    candidates = [
        Path(policy_file_path),
        Path("backend") / policy_file_path,
        Path(__file__).resolve().parent.parent.parent.parent / policy_file_path,
        Path(__file__).resolve().parent.parent.parent / policy_file_path,
    ]

    for p in candidates:
        if p.is_file():
            try:
                content = p.read_text(encoding="utf-8")
                parsed = yaml.safe_load(content)
                if isinstance(parsed, dict) and "policies" in parsed:
                    _cached_policies = parsed["policies"]
                    return _cached_policies
            except Exception as exc:
                logger.warning("Failed to parse HITL policy file %s (%s); using defaults", p, exc)

    _cached_policies = dict(_DEFAULT_POLICIES)
    return _cached_policies


def get_hitl_policy(task_type: str) -> dict[str, Any]:
    """Retrieve policy configuration for a given task type."""
    policies = _cached_policies if _cached_policies is not None else load_hitl_policies()
    if task_type in policies:
        return policies[task_type]

    # Normalize underscores vs hyphens
    normalized = task_type.replace("-", "_")
    if normalized in policies:
        return policies[normalized]

    if normalized.startswith("approve_") and normalized[8:] in policies:
        return policies[normalized[8:]]

    return {
        "enabled": False,
        "required_roles": ["admin"],
        "expiry_hours": 24,
        "description": f"Default fallback policy for {task_type}",
    }


def is_hitl_required(task_type: str) -> bool:
    """Check whether human approval is required for the task type."""
    policy = get_hitl_policy(task_type)
    return bool(policy.get("enabled", False))


def get_required_roles(task_type: str) -> list[str]:
    """Get the authorized roles allowed to decide a task of this type."""
    policy = get_hitl_policy(task_type)
    return list(policy.get("required_roles", ["admin"]))


def get_expiry_hours(task_type: str) -> int:
    """Get expiry duration in hours for this task type."""
    policy = get_hitl_policy(task_type)
    return int(policy.get("expiry_hours", 24))
