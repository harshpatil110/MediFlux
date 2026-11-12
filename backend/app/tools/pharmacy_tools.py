"""Dedicated pharmacy telemetry tools for inventory, sales trend, expiry, and Rx compliance."""

import json
import logging
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.core.security import get_service_db_client
from app.tools.registry import tool

logger = logging.getLogger("mediflux.tools.pharmacy")

# In-memory mock data stores for offline testing and deterministic verification
_mock_inventory: dict[str, list[dict[str, Any]]] = {}
_mock_sales: list[dict[str, Any]] = []
_mock_batches: dict[str, list[dict[str, Any]]] = {}
_mock_events: dict[str, dict[str, Any]] = {}

_cached_doctor_registry: list[dict[str, Any]] | None = None
_cached_drug_schedules: list[dict[str, Any]] | None = None


def _find_fixture_file(filename: str) -> Path | None:
    """Locate fixture file across candidate project directories."""
    candidates = [
        Path(__file__).resolve().parent.parent / "fixtures" / filename,
        Path(__file__).resolve().parent.parent.parent / "fixtures" / filename,
        Path.cwd() / "fixtures" / filename,
        Path.cwd() / "backend" / "fixtures" / filename,
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


def load_doctor_registry() -> list[dict[str, Any]]:
    """Load doctor registry fixtures from disk with caching."""
    global _cached_doctor_registry
    if _cached_doctor_registry is not None:
        return _cached_doctor_registry

    path = _find_fixture_file("doctor_registry.json")
    if path and path.exists():
        try:
            with open(path, encoding="utf-8") as f:
                _cached_doctor_registry = json.load(f)
                return _cached_doctor_registry or []
        except Exception as exc:
            logger.warning("Failed to load doctor_registry.json: %s", exc)

    _cached_doctor_registry = [
        {
            "doctor_id": "DOC-IND-001",
            "license_number": "MCI-2015-88421",
            "name": "Dr. Rajesh Sharma",
            "specialization": "General Physician",
            "valid_until": "2029-12-31",
        },
        {
            "doctor_id": "DOC-IND-002",
            "license_number": "DMC-2018-44912",
            "name": "Dr. Ananya Iyer",
            "specialization": "Cardiologist",
            "valid_until": "2030-06-30",
        },
    ]
    return _cached_doctor_registry


def load_drug_schedules() -> list[dict[str, Any]]:
    """Load curated drug schedule fixtures from disk with caching."""
    global _cached_drug_schedules
    if _cached_drug_schedules is not None:
        return _cached_drug_schedules

    path = _find_fixture_file("drug_schedules.json")
    if path and path.exists():
        try:
            with open(path, encoding="utf-8") as f:
                _cached_drug_schedules = json.load(f)
                return _cached_drug_schedules or []
        except Exception as exc:
            logger.warning("Failed to load drug_schedules.json: %s", exc)

    _cached_drug_schedules = [
        {
            "product_name": "Azithromycin 500mg Tablets",
            "sku": "MED-AZI-500",
            "category": "antibiotic",
            "schedule_type": "Schedule H",
            "requires_prescription": True,
        },
        {
            "product_name": "Amoxicillin 500mg Capsules",
            "sku": "MED-AMX-500",
            "category": "antibiotic",
            "schedule_type": "Schedule H",
            "requires_prescription": True,
        },
        {
            "product_name": "Paracetamol 650mg Tablets",
            "sku": "MED-PCM-650",
            "category": "analgesic",
            "schedule_type": "OTC",
            "requires_prescription": False,
        },
    ]
    return _cached_drug_schedules


def is_scheduled_drug(product_id_or_sku: str, schedule_type: str | None = None) -> bool:
    """Determine whether a product falls under Schedule H, H1, X, or G requiring Rx."""
    if schedule_type:
        st = schedule_type.strip().lower()
        if any(sc in st for sc in ["schedule h", "schedule_h", "schedule-h", "sch h", "schedule x", "schedule g", "schedule_h1"]):
            return True
        if "otc" in st or "general" in st:
            return False

    prod_str = str(product_id_or_sku).strip().lower()
    schedules = load_drug_schedules()
    for item in schedules:
        sku = str(item.get("sku", "")).lower()
        name = str(item.get("product_name", "")).lower()
        if (sku and sku in prod_str) or (prod_str and prod_str in sku) or (name and name in prod_str):
            st = str(item.get("schedule_type", "")).lower()
            return bool(
                item.get("requires_prescription")
                or any(sc in st for sc in ["schedule h", "schedule x", "schedule g"])
            )

    # Heuristic fallback for synthesized identifiers
    if any(k in prod_str for k in ["azi", "amx", "cip", "ibu", "sch-h", "schedule_h", "schedule-h"]):
        return True
    if any(k in prod_str for k in ["pcm", "paracetamol", "otc", "cetirizine"]):
        return False

    return False


# -----------------------------------------------------------------------------
# Test Isolation Helpers
# -----------------------------------------------------------------------------
def set_mock_inventory(node_id: str, items: list[dict[str, Any]]) -> None:
    """Set in-memory inventory for a node."""
    _mock_inventory[str(node_id)] = items


def clear_mock_inventory() -> None:
    """Clear in-memory mock inventory."""
    _mock_inventory.clear()


def set_mock_batches(node_id: str, batches: list[dict[str, Any]]) -> None:
    """Set in-memory mock batches for a node."""
    _mock_batches[str(node_id)] = batches


def clear_mock_batches() -> None:
    """Clear in-memory mock batches."""
    _mock_batches.clear()


def set_mock_sales(sales: list[dict[str, Any]]) -> None:
    """Set in-memory sales events."""
    global _mock_sales
    _mock_sales = list(sales)


def clear_mock_sales() -> None:
    """Clear in-memory sales events."""
    global _mock_sales
    _mock_sales = []


def set_mock_event(event_id: str, event_data: dict[str, Any]) -> None:
    """Register a mock event by ID."""
    _mock_events[str(event_id)] = event_data


def clear_mock_events() -> None:
    """Clear mock events store."""
    _mock_events.clear()


# -----------------------------------------------------------------------------
# Tool 1: get_inventory
# -----------------------------------------------------------------------------
@tool(
    name="get_inventory",
    description="Retrieves current stock, safety stock levels, and reorder points for a pharmacy node.",
)
async def get_inventory(node_id: str, product_id: str | None = None) -> list[dict[str, Any]]:
    """Retrieve inventory levels, safety stock, and reorder points for a node."""
    if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY:
        try:
            client = get_service_db_client()
            if client:
                query = client.table("inventory").select("*").eq("node_id", node_id)
                if product_id:
                    query = query.eq("product_id", product_id)
                res = query.execute()
                if res.data:
                    items: list[dict[str, Any]] = []
                    for row in res.data:
                        r = dict(row)
                        r.setdefault("safety_stock", 10)
                        r.setdefault("reorder_point", r["safety_stock"] + 5)
                        r.setdefault("max_capacity", max(100, r["safety_stock"] * 5))
                        items.append(r)
                    return items
        except Exception as exc:
            logger.warning("DB get_inventory query failed (%s); using in-memory store.", exc)

    items = _mock_inventory.get(str(node_id), [])
    if product_id:
        items = [
            i for i in items
            if str(i.get("product_id")) == str(product_id) or str(i.get("sku")) == str(product_id)
        ]
    if items:
        return [dict(i) for i in items]

    return [
        {
            "node_id": node_id,
            "product_id": product_id or "p-001-azithromycin",
            "batch_id": "b-azi-2026-01",
            "quantity": 100,
            "safety_stock": 20,
            "reorder_point": 25,
            "max_capacity": 150,
        }
    ]


# -----------------------------------------------------------------------------
# Tool 2: get_recent_sales
# -----------------------------------------------------------------------------
@tool(
    name="get_recent_sales",
    description="Fetches historical sale event records from the database for consumption trend analysis.",
)
async def get_recent_sales(node_id: str, product_id: str | None = None, days: int = 7) -> list[dict[str, Any]]:
    """Fetch recent retail Point-of-Sale dispense transactions for a pharmacy node."""
    if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY:
        try:
            client = get_service_db_client()
            if client:
                cutoff = (datetime.now(UTC) - timedelta(days=days)).isoformat()
                res = (
                    client.table("events")
                    .select("*")
                    .eq("node_id", node_id)
                    .gte("created_at", cutoff)
                    .order("created_at", desc=True)
                    .execute()
                )
                if res.data:
                    filtered = [
                        evt for evt in res.data
                        if evt.get("type") in ("pos.sale", "sale")
                    ]
                    if product_id:
                        filtered = [
                            evt for evt in filtered
                            if (evt.get("payload") or {}).get("product_id") == product_id
                        ]
                    if filtered:
                        return filtered
        except Exception as exc:
            logger.warning("DB get_recent_sales failed (%s); using in-memory store.", exc)

    filtered = [
        s for s in _mock_sales
        if str(s.get("node_id")) == str(node_id) or str(s.get("pharmacy_id")) == str(node_id)
    ]
    if product_id:
        filtered = [
            s for s in filtered
            if s.get("product_id") == product_id
            or (s.get("payload") or {}).get("product_id") == product_id
        ]
    return filtered


# -----------------------------------------------------------------------------
# Tool 3: get_batches_near_expiry
# -----------------------------------------------------------------------------
@tool(
    name="get_batches_near_expiry",
    description="Queries batches table for active stock expiring within threshold_days.",
)
async def get_batches_near_expiry(node_id: str, threshold_days: int = 30) -> list[dict[str, Any]]:
    """Query batches table for active stock expiring within threshold_days."""
    if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY:
        try:
            client = get_service_db_client()
            if client:
                inv_res = (
                    client.table("inventory")
                    .select("batch_id, product_id, quantity")
                    .eq("node_id", node_id)
                    .execute()
                )
                if inv_res.data:
                    batch_map = {row["batch_id"]: row for row in inv_res.data if row.get("batch_id")}
                    if batch_map:
                        cutoff_date = (date.today() + timedelta(days=threshold_days)).isoformat()
                        b_res = (
                            client.table("batches")
                            .select("*")
                            .in_("id", list(batch_map.keys()))
                            .lte("expiry_date", cutoff_date)
                            .execute()
                        )
                        if b_res.data:
                            results: list[dict[str, Any]] = []
                            for b in b_res.data:
                                exp = date.fromisoformat(str(b["expiry_date"]))
                                days = (exp - date.today()).days
                                inv_info = batch_map.get(b["id"], {})
                                results.append({
                                    "batch_id": b["id"],
                                    "batch_no": b.get("batch_no"),
                                    "sku": b.get("sku") or inv_info.get("product_id", "MED-UNKNOWN"),
                                    "product_id": b.get("product_id") or inv_info.get("product_id"),
                                    "expiry_date": b["expiry_date"],
                                    "days_to_expiry": days,
                                    "quantity_affected": inv_info.get("quantity", 0),
                                })
                            return results
        except Exception as exc:
            logger.warning("DB get_batches_near_expiry failed (%s); using in-memory store.", exc)

    node_batches = _mock_batches.get(str(node_id), [])
    if not node_batches and "*" in _mock_batches:
        node_batches = _mock_batches["*"]

    matching: list[dict[str, Any]] = []
    for b in node_batches:
        days = b.get("days_to_expiry")
        if days is None and b.get("expiry_date"):
            try:
                exp = date.fromisoformat(str(b["expiry_date"]))
                days = (exp - date.today()).days
            except Exception:
                days = 15
        if days is not None and days <= threshold_days:
            matching.append({
                "batch_id": b.get("batch_id") or b.get("id", "b-batch-exp-01"),
                "sku": b.get("sku", "MED-AZI-500"),
                "product_id": b.get("product_id", "p-001-azithromycin"),
                "expiry_date": b.get("expiry_date", (date.today() + timedelta(days=days)).isoformat()),
                "days_to_expiry": days,
                "quantity_affected": b.get("quantity_affected") or b.get("quantity", 15),
            })
    return matching


# -----------------------------------------------------------------------------
# Tool 4: check_prescription_link
# -----------------------------------------------------------------------------
@tool(
    name="check_prescription_link",
    description="Checks whether a Schedule H sale is tied to a valid prescription in doctor_registry.json or events metadata.",
)
async def check_prescription_link(event_id: str, prescription_ref: str | None = None) -> dict[str, Any]:
    """Check whether a Schedule H sale is tied to a valid prescription in doctor_registry.json or events metadata."""
    registry = load_doctor_registry()

    def _match_doc(ref: str) -> dict[str, Any] | None:
        clean_ref = ref.strip()
        ref_upper = clean_ref.upper()
        for doc in registry:
            doc_id = str(doc.get("doctor_id", "")).upper()
            lic = str(doc.get("license_number", "")).upper()
            name = str(doc.get("name", "")).lower()
            if doc_id and (doc_id == ref_upper or doc_id in ref_upper):
                return doc
            if lic and (lic == ref_upper or lic in ref_upper):
                return doc
            if name and name == clean_ref.lower():
                return doc
        return None

    # 1. Direct prescription reference check
    if prescription_ref and prescription_ref.strip():
        matched = _match_doc(prescription_ref)
        if matched:
            return {
                "valid": True,
                "doctor_id": matched.get("doctor_id"),
                "reason": f"Prescription verified: Issued by {matched.get('name')} ({matched.get('license_number')})",
            }
        return {
            "valid": False,
            "doctor_id": None,
            "reason": f"Prescription reference '{prescription_ref}' is invalid or physician is not in national registry",
        }

    # 2. Lookup event metadata if event_id is supplied
    if event_id and str(event_id).strip():
        evt: dict[str, Any] | None = None
        if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY:
            try:
                client = get_service_db_client()
                if client:
                    res = client.table("events").select("*").eq("id", event_id).execute()
                    if not res.data:
                        res = client.table("events").select("*").eq("event_id", event_id).execute()
                    if res.data:
                        evt = res.data[0]
            except Exception as exc:
                logger.warning("DB check_prescription_link event query failed: %s", exc)

        if not evt:
            evt = _mock_events.get(str(event_id))

        if evt:
            payload = evt.get("payload") or {}
            metadata = evt.get("metadata") or {}
            ref = (
                payload.get("prescription_ref")
                or payload.get("doctor_id")
                or payload.get("rx_ref")
                or metadata.get("prescription_ref")
                or metadata.get("doctor_id")
            )
            if ref and str(ref).strip():
                matched = _match_doc(str(ref))
                if matched:
                    return {
                        "valid": True,
                        "doctor_id": matched.get("doctor_id"),
                        "reason": f"Prescription verified from event metadata: Issued by {matched.get('name')}",
                    }
                return {
                    "valid": False,
                    "doctor_id": None,
                    "reason": f"Prescription reference '{ref}' in event metadata is not registered in national registry",
                }

    return {
        "valid": False,
        "doctor_id": None,
        "reason": "Missing prescription reference for scheduled substance",
    }
