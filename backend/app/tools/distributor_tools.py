"""Dedicated distributor tools for credit accounts, trade financing, fleet vehicles, and shipments."""

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from app.core.config import settings
from app.core.security import get_service_db_client
from app.tools.registry import tool

logger = logging.getLogger("mediflux.tools.distributor")

# In-memory stores for offline testing and deterministic verification
_in_memory_settlements: list[dict[str, Any]] = []
_in_memory_shipments: list[dict[str, Any]] = []

_mock_credit_accounts: dict[str, dict[str, Any]] = {
    "22222222-2222-2222-2222-222222222222": {
        "node_id": "22222222-2222-2222-2222-222222222222",
        "credit_limit": 100000.0,
        "current_balance": 15000.0,
        "outstanding_balance": 15000.0,
        "payment_terms_days": 30,
        "currency": "INR",
    }
}

_mock_vehicles: list[dict[str, Any]] = [
    {
        "id": "11111111-aaaa-bbbb-cccc-000000000001",
        "distributor_id": "33333333-3333-3333-3333-333333333333",
        "vehicle_plate": "DL-01-RF-1001",
        "license_plate": "DL-01-RF-1001",
        "vehicle_number": "DL-01-RF-1001",
        "capacity_kg": 2500,
        "is_reefer": True,
        "is_available": True,
        "status": "available",
    },
    {
        "id": "11111111-aaaa-bbbb-cccc-000000000002",
        "distributor_id": "33333333-3333-3333-3333-333333333333",
        "vehicle_plate": "DL-02-AM-2002",
        "license_plate": "DL-02-AM-2002",
        "vehicle_number": "DL-02-AM-2002",
        "capacity_kg": 3000,
        "is_reefer": False,
        "is_available": True,
        "status": "available",
    },
]

_mock_bank_override: dict[str, Any] | None = None


# -----------------------------------------------------------------------------
# Test Helpers
# -----------------------------------------------------------------------------
def get_in_memory_settlements() -> list[dict[str, Any]]:
    """Retrieve recorded settlements from in-memory test store."""
    return list(_in_memory_settlements)


def clear_in_memory_settlements() -> None:
    """Clear in-memory recorded settlements."""
    _in_memory_settlements.clear()


def get_in_memory_shipments() -> list[dict[str, Any]]:
    """Retrieve recorded shipments from in-memory test store."""
    return list(_in_memory_shipments)


def clear_in_memory_shipments() -> None:
    """Clear in-memory recorded shipments."""
    _in_memory_shipments.clear()


def set_mock_credit_account(node_id: str, account_data: dict[str, Any]) -> None:
    """Set in-memory mock credit account for a buyer node."""
    _mock_credit_accounts[str(node_id)] = account_data


def clear_mock_credit_accounts() -> None:
    """Clear in-memory mock credit accounts."""
    _mock_credit_accounts.clear()


def set_mock_vehicles(vehicles: list[dict[str, Any]]) -> None:
    """Set in-memory fleet vehicles list."""
    global _mock_vehicles
    _mock_vehicles = list(vehicles)


def clear_mock_vehicles() -> None:
    """Clear in-memory fleet vehicles list."""
    global _mock_vehicles
    _mock_vehicles = []


def set_mock_bank_finance_decision(approved: bool, reason: str = "") -> None:
    """Explicitly override bank financing approval for tests."""
    global _mock_bank_override
    _mock_bank_override = {"approved": approved, "reason": reason}


def clear_mock_bank_finance_override() -> None:
    """Clear bank financing mock override."""
    global _mock_bank_override
    _mock_bank_override = None


# -----------------------------------------------------------------------------
# Tool 1: get_credit_account
# -----------------------------------------------------------------------------
@tool(
    name="get_credit_account",
    description="Fetches credit limit, current outstanding balance, and payment terms for a buyer node.",
)
async def get_credit_account(node_id: str) -> dict[str, Any]:
    """Retrieve buyer credit limit and current outstanding balance."""
    if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY:
        try:
            client = get_service_db_client()
            if client:
                res = client.table("credit_accounts").select("*").eq("node_id", node_id).execute()
                if res.data:
                    acc = res.data[0]
                    bal = float(acc.get("current_balance", acc.get("outstanding_balance", 0.0)))
                    lim = float(acc.get("credit_limit", 50000.0))
                    return {
                        "node_id": node_id,
                        "credit_limit": lim,
                        "current_balance": bal,
                        "outstanding_balance": bal,
                        "payment_terms_days": acc.get("payment_terms_days", 30),
                    }
        except Exception as exc:
            logger.warning("DB get_credit_account query failed (%s); using mock store.", exc)

    mock_acc = _mock_credit_accounts.get(str(node_id))
    if mock_acc:
        return dict(mock_acc)

    return {
        "node_id": node_id,
        "credit_limit": 100000.0,
        "current_balance": 15000.0,
        "outstanding_balance": 15000.0,
        "payment_terms_days": 30,
        "currency": "INR",
    }


# -----------------------------------------------------------------------------
# Tool 2: mock_bank_finance
# -----------------------------------------------------------------------------
@tool(
    name="mock_bank_finance",
    description="Simulated trade financing API for buyers exceeding primary credit limits.",
)
async def mock_bank_finance(node_id: str, amount: float, credit_score_mock: int = 750) -> dict[str, Any]:
    """Simulate partner bank trade credit underwriting and financing approval."""
    if _mock_bank_override is not None:
        approved = bool(_mock_bank_override.get("approved", True))
        reason = _mock_bank_override.get(
            "reason",
            "Trade financing approved by partner bank" if approved else "Credit underwriting rejected by bank",
        )
        return {
            "approved": approved,
            "financing_id": f"MOCK-FIN-{uuid.uuid4().hex[:8].upper()}",
            "amount_approved": amount if approved else 0.0,
            "interest_rate": 0.045,
            "reason": reason,
        }

    approved = credit_score_mock >= 650 and amount <= 500000.0
    return {
        "approved": approved,
        "financing_id": f"MOCK-FIN-{uuid.uuid4().hex[:8].upper()}",
        "amount_approved": amount if approved else 0.0,
        "interest_rate": 0.045,
        "reason": (
            "Trade financing approved by partner bank (automated underwriting)"
            if approved
            else "Credit limit exceeded and trade financing rejected by bank."
        ),
    }


# -----------------------------------------------------------------------------
# Tool 3: list_vehicles
# -----------------------------------------------------------------------------
@tool(
    name="list_vehicles",
    description="Returns fleet vehicles for a distributor node, optionally filtering for available status.",
)
async def list_vehicles(distributor_id: str, only_available: bool = True) -> list[dict[str, Any]]:
    """Return fleet vehicles for a distributor node."""
    if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY:
        try:
            client = get_service_db_client()
            if client:
                query = client.table("fleet_vehicles").select("*").eq("distributor_id", distributor_id)
                if only_available:
                    query = query.eq("is_available", True)
                res = query.execute()
                if res.data:
                    vehicles: list[dict[str, Any]] = []
                    for row in res.data:
                        vehicles.append({
                            "id": row["id"],
                            "vehicle_id": row["id"],
                            "distributor_id": distributor_id,
                            "license_plate": row.get("vehicle_number") or row.get("license_plate", "DL-01-XX-0000"),
                            "vehicle_plate": row.get("vehicle_number") or row.get("license_plate", "DL-01-XX-0000"),
                            "capacity_kg": row.get("capacity_kg", 2000),
                            "is_reefer": bool(row.get("is_reefer", False)),
                            "status": "available" if row.get("is_available", True) else "busy",
                        })
                    return vehicles
        except Exception as exc:
            logger.warning("DB list_vehicles query failed (%s); using mock store.", exc)

    vehicles = _mock_vehicles
    if only_available:
        vehicles = [v for v in vehicles if v.get("is_available", True) or v.get("status") == "available"]

    matched = [v for v in vehicles if v.get("distributor_id") == distributor_id]
    return matched or vehicles


# -----------------------------------------------------------------------------
# Tool 4: create_shipment
# -----------------------------------------------------------------------------
@tool(
    name="create_shipment",
    description="Inserts a dispatch record into the shipments table with scheduling priority and vehicle assignment.",
)
async def create_shipment(
    order_ids: list[str],
    vehicle_id: str,
    priority: str = "medium",
    sequence: int = 1,
    is_cold_chain: bool = False,
    requires_hitl: bool = False,
    eta_hours: float = 2.5,
    distributor_id: str = "33333333-3333-3333-3333-333333333333",
    correlation_id: str = "",
) -> dict[str, Any]:
    """Insert a shipment dispatch record into Supabase shipments table and memory store."""
    corr_id = correlation_id or str(uuid.uuid4())
    shipment_record = {
        "id": str(uuid.uuid4()),
        "order_ids": order_ids,
        "vehicle_id": vehicle_id,
        "distributor_id": distributor_id,
        "sequence": sequence,
        "priority": priority,
        "is_cold_chain": is_cold_chain,
        "requires_hitl": requires_hitl,
        "status": "scheduled",
        "eta_hours": eta_hours,
        "correlation_id": corr_id,
        "created_at": datetime.now(UTC).isoformat(),
    }

    if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY:
        try:
            client = get_service_db_client()
            if client:
                client.table("shipments").insert(shipment_record).execute()
                logger.info("Shipment [%s] inserted into Supabase shipments table", shipment_record["id"])
        except Exception as exc:
            logger.warning("DB create_shipment failed (%s); saved to in-memory store.", exc)

    _in_memory_shipments.append(shipment_record)
    return shipment_record
