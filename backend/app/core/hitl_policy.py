"""HITL policy parser and rule verification."""

import logging
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger("mediflux.core.hitl_policy")

_DEFAULT_POLICIES: dict[str, dict[str, Any]] = {
    "cross_border_shipment": {
        "enabled": True,
        "allowed_roles": ["admin", "distributor", "stockist", "regulator"],
        "required_roles": ["admin", "distributor", "stockist", "regulator"],
        "risk_level": "high",
        "timeout_minutes": 720,
        "expiry_hours": 12,
        "description": "Dispatching shipments crossing regional or international borders.",
    },
    "batch_modification": {
        "enabled": True,
        "allowed_roles": ["admin", "manufacturer"],
        "required_roles": ["admin", "manufacturer"],
        "risk_level": "high",
        "timeout_minutes": 1440,
        "expiry_hours": 24,
        "description": "Modifying or reprioritizing a production batch currently in status in_progress.",
    },
    "regulatory_activation": {
        "enabled": True,
        "allowed_roles": ["admin", "regulator"],
        "required_roles": ["admin", "regulator"],
        "risk_level": "critical",
        "timeout_minutes": 2880,
        "expiry_hours": 48,
        "description": "Approval for hot-swapping regulatory-mandated price ceiling or compliance module updates.",
    },
    "doctor_verification": {
        "enabled": True,
        "allowed_roles": ["admin", "regulator", "stockist"],
        "required_roles": ["admin", "regulator", "stockist"],
        "risk_level": "medium",
        "timeout_minutes": 720,
        "expiry_hours": 12,
        "description": "Verification of unregistered or unknown prescribing doctor credentials before dispensing.",
    },
    "schedule_h_override": {
        "enabled": True,
        "allowed_roles": ["admin", "regulator", "stockist"],
        "required_roles": ["admin", "regulator", "stockist"],
        "risk_level": "high",
        "timeout_minutes": 360,
        "expiry_hours": 6,
        "description": "Fulfilling Schedule H medication orders without automated doctor prescription verification.",
    },
    "in_progress_batch_modification": {
        "enabled": True,
        "allowed_roles": ["admin", "manufacturer"],
        "required_roles": ["admin", "manufacturer"],
        "risk_level": "high",
        "timeout_minutes": 1440,
        "expiry_hours": 24,
        "description": "Modifying or reprioritizing a production batch currently in status in_progress.",
    },
    "in_progress_batch_change": {
        "enabled": True,
        "allowed_roles": ["admin", "manufacturer", "manufacturer_admin", "compliance_officer"],
        "required_roles": ["admin", "manufacturer", "manufacturer_admin", "compliance_officer"],
        "risk_level": "high",
        "timeout_minutes": 1440,
        "expiry_hours": 24,
        "description": "Modifying or reprioritizing a production batch currently in status in_progress.",
    },
    "regulatory_hot_swap": {
        "enabled": True,
        "allowed_roles": ["admin", "regulator", "compliance_officer", "system_admin"],
        "required_roles": ["admin", "regulator", "compliance_officer", "system_admin"],
        "risk_level": "critical",
        "timeout_minutes": 2880,
        "expiry_hours": 48,
        "description": "Approval for hot-swapping regulatory-mandated price ceiling or compliance module updates.",
    },
    "regulatory_module_activation": {
        "enabled": True,
        "allowed_roles": ["admin", "regulator"],
        "required_roles": ["admin", "regulator"],
        "risk_level": "critical",
        "timeout_minutes": 2880,
        "expiry_hours": 48,
        "description": "Approval for hot-swapping regulatory-mandated price ceiling or compliance module updates.",
    },
    "prescription_doctor_verification": {
        "enabled": True,
        "allowed_roles": ["admin", "regulator", "stockist", "pharmacist_in_charge", "compliance_officer"],
        "required_roles": ["admin", "regulator", "stockist", "pharmacist_in_charge", "compliance_officer"],
        "risk_level": "medium",
        "timeout_minutes": 720,
        "expiry_hours": 12,
        "description": "Verification of unregistered or unknown prescribing doctor credentials before dispensing.",
    },
    "prescription_unknown_drug": {
        "enabled": True,
        "allowed_roles": ["admin", "regulator", "stockist", "pharmacist_in_charge", "compliance_officer"],
        "required_roles": ["admin", "regulator", "stockist", "pharmacist_in_charge", "compliance_officer"],
        "risk_level": "medium",
        "timeout_minutes": 720,
        "expiry_hours": 12,
        "description": "Clinical review and schedule classification for unlisted or experimental medication.",
    },
    "compliance_hold": {
        "enabled": True,
        "allowed_roles": ["admin", "regulator", "stockist"],
        "required_roles": ["admin", "regulator", "stockist"],
        "risk_level": "high",
        "timeout_minutes": 360,
        "expiry_hours": 6,
        "description": "Fulfilling Schedule H medication orders without automated doctor prescription verification.",
    },
    "module_activation": {
        "enabled": True,
        "allowed_roles": ["admin", "regulator", "system_admin", "compliance_officer"],
        "required_roles": ["admin", "regulator", "system_admin", "compliance_officer"],
        "risk_level": "critical",
        "timeout_minutes": 2880,
        "expiry_hours": 48,
        "description": "Activating a new WASM or python policy module version.",
    },
    "reorder_approval": {
        "enabled": True,
        "allowed_roles": ["admin", "stockist", "pharmacist_in_charge", "stockist_admin"],
        "required_roles": ["admin", "stockist", "pharmacist_in_charge", "stockist_admin"],
        "risk_level": "medium",
        "timeout_minutes": 1440,
        "expiry_hours": 24,
        "description": "Approval for bulk inventory replenishment reorders.",
    },
    "regulatory_clarification": {
        "enabled": True,
        "allowed_roles": ["admin", "regulator", "compliance_officer"],
        "required_roles": ["admin", "regulator", "compliance_officer"],
        "risk_level": "medium",
        "timeout_minutes": 1440,
        "expiry_hours": 24,
        "description": "Clarification and verification for ambiguous or low-confidence regulatory notices.",
    },
    "coldchain_high_value": {
        "enabled": True,
        "allowed_roles": ["admin", "distributor", "stockist", "logistics_manager"],
        "required_roles": ["admin", "distributor", "stockist", "logistics_manager"],
        "risk_level": "medium",
        "timeout_minutes": 720,
        "expiry_hours": 12,
        "description": "Cold-chain temperature excursion disposition authorization.",
    },
    "cascade_partial_failure_escalation": {
        "enabled": True,
        "allowed_roles": ["admin", "stockist", "distributor", "regulator", "system_admin", "compliance_officer"],
        "required_roles": ["admin", "stockist", "distributor", "regulator", "system_admin", "compliance_officer"],
        "risk_level": "high",
        "timeout_minutes": 1440,
        "expiry_hours": 24,
        "description": "Escalation for demand cascade failure across supply chain tiers.",
    },
}

_cached_policies: dict[str, dict[str, Any]] | None = None


def clear_policy_cache() -> None:
    """Clear cached policy definitions to force reloading from disk."""
    global _cached_policies
    _cached_policies = None


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
                    loaded: dict[str, dict[str, Any]] = dict(parsed["policies"])
                    # Ensure both allowed_roles and required_roles are present on each policy
                    for _key, val in loaded.items():
                        if isinstance(val, dict):
                            roles = val.get("allowed_roles") or val.get("required_roles") or ["admin"]
                            val["allowed_roles"] = list(roles)
                            val["required_roles"] = list(roles)
                    _cached_policies = loaded
                    return _cached_policies
            except Exception as exc:
                logger.warning("Failed to parse HITL policy file %s (%s); using defaults", p, exc)

    _cached_policies = dict(_DEFAULT_POLICIES)
    return _cached_policies


def get_all_policies() -> dict[str, dict[str, Any]]:
    """Return all configured HITL policies."""
    return _cached_policies if _cached_policies is not None else load_hitl_policies()


def _normalize_type(task_type: str) -> str:
    """Normalize task type string for alias resolution."""
    normalized = task_type.strip().lower().replace("-", "_").replace(" ", "_")
    alias_map = {
        "cross_border": "cross_border_shipment",
        "cross_border_shipment": "cross_border_shipment",
        "in_progress_batch_modification": "batch_modification",
        "in_progress_batch_change": "batch_modification",
        "batch_modification": "batch_modification",
        "regulatory_hot_swap": "regulatory_activation",
        "regulatory_module_activation": "regulatory_activation",
        "regulatory_activation": "regulatory_activation",
        "prescription_doctor_verification": "doctor_verification",
        "prescription_unknown_drug": "doctor_verification",
        "doctor_verification": "doctor_verification",
        "compliance_hold": "schedule_h_override",
        "schedule_h_override": "schedule_h_override",
    }
    return alias_map.get(normalized, normalized)


def get_hitl_policy(task_type: str) -> dict[str, Any]:
    """Retrieve policy configuration for a given task type."""
    policies = get_all_policies()

    if task_type in policies:
        return policies[task_type]

    normalized = _normalize_type(task_type)
    if normalized in policies:
        return policies[normalized]

    raw_normalized = task_type.strip().lower().replace("-", "_").replace(" ", "_")
    if raw_normalized in policies:
        return policies[raw_normalized]

    if raw_normalized.startswith("approve_") and raw_normalized[8:] in policies:
        return policies[raw_normalized[8:]]

    return {
        "enabled": False,
        "allowed_roles": ["admin"],
        "required_roles": ["admin"],
        "risk_level": "medium",
        "timeout_minutes": 1440,
        "expiry_hours": 24,
        "description": f"Default fallback policy for {task_type}",
    }


def is_hitl_required(task_type: str) -> bool:
    """Check whether human approval is required for the task type."""
    policy = get_hitl_policy(task_type)
    return bool(policy.get("enabled", False))


def get_allowed_roles(task_type: str) -> list[str]:
    """Get the authorized roles allowed to decide a task of this type."""
    policy = get_hitl_policy(task_type)
    return list(policy.get("allowed_roles") or policy.get("required_roles") or ["admin"])


def get_required_roles(task_type: str) -> list[str]:
    """Get the authorized roles allowed to decide a task of this type (backwards compatibility)."""
    return get_allowed_roles(task_type)


def get_risk_level(task_type: str) -> str:
    """Get risk level for task type."""
    policy = get_hitl_policy(task_type)
    return str(policy.get("risk_level", "medium"))


def get_timeout_minutes(task_type: str) -> int:
    """Get timeout in minutes for task type."""
    policy = get_hitl_policy(task_type)
    if "timeout_minutes" in policy:
        return int(policy["timeout_minutes"])
    return int(policy.get("expiry_hours", 24)) * 60


def get_expiry_hours(task_type: str) -> int:
    """Get expiry duration in hours for this task type."""
    policy = get_hitl_policy(task_type)
    if "timeout_minutes" in policy:
        return max(1, int(policy["timeout_minutes"]) // 60)
    return int(policy.get("expiry_hours", 24))
