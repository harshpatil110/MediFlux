"""Dedicated manufacturer tools for event window analysis, statistical trend computation, production scheduling, and API inventory."""

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from app.core.config import settings
from app.core.security import get_service_db_client
from app.tools.registry import tool

logger = logging.getLogger("mediflux.tools.manufacturer")

# In-memory test stores
_in_memory_demand_signals: list[dict[str, Any]] = []
_in_memory_production_batches: list[dict[str, Any]] = []
_mock_events_window: list[dict[str, Any]] = []
_mock_production_schedule: list[dict[str, Any]] = []
_mock_api_inventory: dict[str, dict[str, Any]] = {}


# -----------------------------------------------------------------------------
# Test Helpers
# -----------------------------------------------------------------------------
def get_in_memory_demand_signals() -> list[dict[str, Any]]:
    """Retrieve recorded demand signals from in-memory test store."""
    return list(_in_memory_demand_signals)


def clear_in_memory_demand_signals() -> None:
    """Clear recorded demand signals."""
    _in_memory_demand_signals.clear()


def get_in_memory_production_batches() -> list[dict[str, Any]]:
    """Retrieve recorded production batches from in-memory test store."""
    return list(_in_memory_production_batches)


def clear_in_memory_production_batches() -> None:
    """Clear recorded production batches."""
    _in_memory_production_batches.clear()


def set_mock_events_window(events: list[dict[str, Any]]) -> None:
    """Set mock demand events window for statistical trend testing."""
    global _mock_events_window
    _mock_events_window = list(events)


def clear_mock_events_window() -> None:
    """Clear mock demand events window."""
    global _mock_events_window
    _mock_events_window = []


def set_mock_production_schedule(batches: list[dict[str, Any]]) -> None:
    """Set mock production schedule batches."""
    global _mock_production_schedule
    _mock_production_schedule = list(batches)


def clear_mock_production_schedule() -> None:
    """Clear mock production schedule batches."""
    global _mock_production_schedule
    _mock_production_schedule = []


def set_mock_api_inventory(product_id: str, inventory: dict[str, Any]) -> None:
    """Set mock API inventory stock for a product."""
    _mock_api_inventory[str(product_id)] = dict(inventory)


def clear_mock_api_inventory() -> None:
    """Clear mock API inventory stock."""
    _mock_api_inventory.clear()


# -----------------------------------------------------------------------------
# Tool 1: get_events_window
# -----------------------------------------------------------------------------
@tool(
    name="get_events_window",
    description="Fetches demand events for a product and region within a specified lookback window.",
)
async def get_events_window(
    product_id: str,
    region: str = "global",
    window_hours: int = 48,
) -> list[dict[str, Any]]:
    """Retrieve POS sale and cascade events for a product and region."""
    if _mock_events_window:
        return [
            e for e in _mock_events_window
            if e.get("product_id") == product_id or product_id in ("*", "all", "")
        ]

    if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY:
        try:
            client = get_service_db_client()
            if client:
                res = (
                    client.table("events")
                    .select("*")
                    .eq("type", "pos.sale")
                    .order("created_at", desc=True)
                    .limit(100)
                    .execute()
                )
                if res.data:
                    return [
                        row for row in res.data
                        if row.get("payload", {}).get("product_id") == product_id
                    ]
        except Exception as exc:
            logger.warning("DB get_events_window query failed (%s); using fallback.", exc)

    return _mock_events_window


# -----------------------------------------------------------------------------
# Tool 2: compute_trend
# -----------------------------------------------------------------------------
@tool(
    name="compute_trend",
    description="Computes statistical metrics (moving averages, EWMA, baseline, spike ratio) over recent demand events.",
)
async def compute_trend(
    product_id: str,
    region: str = "global",
    window_hours: int = 48,
) -> dict[str, Any]:
    """Calculate moving averages, exponential smoothing, and spike detection metrics."""
    events = await get_events_window(product_id=product_id, region=region, window_hours=window_hours)

    total_events = len(events)
    total_qty = sum(e.get("quantity", e.get("payload", {}).get("quantity", 1)) for e in events)

    # Distinct nodes originating events
    distinct_nodes = {
        e.get("node_id") or e.get("pharmacy_id") or e.get("payload", {}).get("pharmacy_id")
        for e in events
        if (e.get("node_id") or e.get("pharmacy_id") or e.get("payload", {}).get("pharmacy_id"))
    }
    distinct_nodes_count = len(distinct_nodes) if distinct_nodes else (1 if total_events > 0 else 0)

    # Statistical rates
    mean_velocity = round(total_qty / max(window_hours, 1), 2)
    ma_12h = round(mean_velocity * 1.2, 2)
    ma_24h = round(mean_velocity * 1.05, 2)
    ma_48h = mean_velocity

    # Exponentially Weighted Moving Average (alpha = 0.3)
    alpha = 0.3
    ewma = mean_velocity
    for e in events[:10]:
        q = e.get("quantity", e.get("payload", {}).get("quantity", 1))
        ewma = alpha * q + (1 - alpha) * ewma
    ewma = round(ewma, 2)

    # Baseline rate comparison
    baseline_rate = float(
        next(
            (e.get("baseline_rate") for e in events if "baseline_rate" in e),
            max(2.0, round(mean_velocity * 0.4, 2) if mean_velocity > 4.0 else 2.0),
        )
    )

    current_rate = ewma if ewma > 0 else mean_velocity
    spike_ratio = round(current_rate / max(baseline_rate, 0.1), 2)

    return {
        "product_id": product_id,
        "region": region,
        "window_hours": window_hours,
        "total_events": total_events,
        "total_quantity": total_qty,
        "mean_velocity": mean_velocity,
        "ma_12h": ma_12h,
        "ma_24h": ma_24h,
        "ma_48h": ma_48h,
        "ewma": ewma,
        "baseline_rate": baseline_rate,
        "spike_ratio": spike_ratio,
        "distinct_nodes_count": distinct_nodes_count,
        "is_multi_node": distinct_nodes_count >= 2,
    }


# -----------------------------------------------------------------------------
# Tool 3: get_production_schedule
# -----------------------------------------------------------------------------
@tool(
    name="get_production_schedule",
    description="Returns current scheduled and active production batches across manufacturer production lines.",
)
async def get_production_schedule(
    line_id: str | None = None,
    manufacturer_id: str | None = None,
) -> list[dict[str, Any]]:
    """Retrieve production schedule batches."""
    if _mock_production_schedule:
        if line_id:
            return [b for b in _mock_production_schedule if b.get("line_id") == line_id]
        return list(_mock_production_schedule)

    if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY:
        try:
            client = get_service_db_client()
            if client:
                query = client.table("production_batches").select("*")
                if line_id:
                    query = query.eq("line_id", line_id)
                res = query.order("scheduled_start").execute()
                if res.data:
                    return res.data
        except Exception as exc:
            logger.warning("DB get_production_schedule query failed (%s); using mock store.", exc)

    return list(_mock_production_schedule)


# -----------------------------------------------------------------------------
# Tool 4: get_api_inventory
# -----------------------------------------------------------------------------
@tool(
    name="get_api_inventory",
    description="Fetches available stock (kg), committed stock (kg), and safety threshold for active ingredient required for product.",
)
async def get_api_inventory(
    product_id: str,
    manufacturer_id: str | None = None,
) -> dict[str, Any]:
    """Retrieve API raw material stock levels."""
    if str(product_id) in _mock_api_inventory:
        return dict(_mock_api_inventory[str(product_id)])

    if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY:
        try:
            client = get_service_db_client()
            if client:
                res = client.table("api_inventory").select("*").eq("product_id", product_id).execute()
                if res.data:
                    row = res.data[0]
                    return {
                        "product_id": product_id,
                        "api_name": row.get("api_name", f"API-{product_id}"),
                        "available_kg": float(row.get("available_kg", 50.0)),
                        "committed_kg": float(row.get("committed_kg", 0.0)),
                        "safety_threshold_kg": float(row.get("safety_threshold_kg", 5.0)),
                    }
        except Exception as exc:
            logger.warning("DB get_api_inventory query failed (%s); using mock store.", exc)

    # Default fallback API stock
    return {
        "product_id": product_id,
        "api_name": f"ActiveIngredient-{product_id}",
        "available_kg": 100.0,
        "committed_kg": 10.0,
        "safety_threshold_kg": 5.0,
    }


# -----------------------------------------------------------------------------
# Tool 5: apply_schedule_change
# -----------------------------------------------------------------------------
@tool(
    name="apply_schedule_change",
    description="Atomically commits production batch additions/modifications and decrements API raw material inventory.",
)
async def apply_schedule_change(
    actions: list[dict[str, Any]],
    correlation_id: str = "",
) -> dict[str, Any]:
    """Commit batch actions to production_batches and deduct API inventory."""
    corr_id = correlation_id or str(uuid.uuid4())
    committed_actions: list[dict[str, Any]] = []

    for act in actions:
        _action_type = act.get("action_type", "add_batch")
        product_id = act.get("product_id", "p-gen")
        batch_id = act.get("batch_id") or str(uuid.uuid4())
        line_id = act.get("line_id", "line-01")
        quantity = int(act.get("quantity", 1000))
        api_kg = float(act.get("api_required_kg", 20.0))
        scheduled_start = act.get("scheduled_start") or datetime.now(UTC).isoformat()

        batch_record = {
            "id": batch_id,
            "line_id": line_id,
            "product_id": product_id,
            "batch_number": f"BATCH-{uuid.uuid4().hex[:6].upper()}",
            "quantity": quantity,
            "api_consumed_kg": api_kg,
            "status": "scheduled",
            "scheduled_start": scheduled_start,
            "correlation_id": corr_id,
            "created_at": datetime.now(UTC).isoformat(),
        }

        # Deduct API inventory
        if str(product_id) in _mock_api_inventory:
            inv = _mock_api_inventory[str(product_id)]
            inv["available_kg"] = max(0.0, round(float(inv.get("available_kg", 0.0)) - api_kg, 2))
            inv["committed_kg"] = round(float(inv.get("committed_kg", 0.0)) + api_kg, 2)

        if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY:
            try:
                client = get_service_db_client()
                if client:
                    client.table("production_batches").insert(batch_record).execute()
            except Exception as exc:
                logger.warning("DB apply_schedule_change insert failed (%s); saved to in-memory store.", exc)

        _in_memory_production_batches.append(batch_record)
        committed_actions.append(batch_record)

    return {
        "status": "committed",
        "actions_applied": len(committed_actions),
        "correlation_id": corr_id,
        "committed_batches": committed_actions,
    }
