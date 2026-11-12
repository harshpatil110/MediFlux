"""Dedicated stockist balancing tools for cluster topology, inventory aggregation, demand trends, and transfers."""

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from app.core.config import settings
from app.core.security import get_service_db_client
from app.tools.pharmacy_tools import (
    get_inventory,
    load_drug_schedules,
)
from app.tools.registry import tool

logger = logging.getLogger("mediflux.tools.stockist")

# In-memory mock data stores for offline testing and verification
_in_memory_transfers: list[dict[str, Any]] = []
_mock_cluster_inventory: dict[tuple[str, str], list[dict[str, Any]]] = {}
_mock_demand_trends: dict[tuple[str, str], dict[str, Any]] = {}

_mock_cluster_nodes: dict[str, list[dict[str, Any]]] = {
    "CLUSTER-DELHI-NORTH": [
        {
            "id": "22222222-2222-2222-2222-222222222222",
            "name": "Delhi Central Stockist Hub",
            "tier": "stockist",
            "cluster_id": "CLUSTER-DELHI-NORTH",
            "parent_id": "33333333-3333-3333-3333-333333333333",
        },
        {
            "id": "22222222-2222-2222-2222-222222222223",
            "name": "Delhi North Peer Stockist",
            "tier": "stockist",
            "cluster_id": "CLUSTER-DELHI-NORTH",
            "parent_id": "33333333-3333-3333-3333-333333333333",
        },
    ]
}


def get_in_memory_transfers() -> list[dict[str, Any]]:
    """Retrieve recorded stock transfers from in-memory store."""
    return list(_in_memory_transfers)


def clear_in_memory_transfers() -> None:
    """Clear in-memory recorded transfers."""
    _in_memory_transfers.clear()


def set_mock_cluster_inventory(cluster_id: str, product_id: str, items: list[dict[str, Any]]) -> None:
    """Explicitly set inventory for all stockists in a cluster for testing."""
    _mock_cluster_inventory[(str(cluster_id), str(product_id))] = items


def clear_mock_cluster_inventory() -> None:
    """Clear mock cluster inventory store."""
    _mock_cluster_inventory.clear()


def set_mock_demand_trend(node_id: str, product_id: str, trend: dict[str, Any]) -> None:
    """Explicitly set mock demand trend for a node and product."""
    _mock_demand_trends[(str(node_id), str(product_id))] = trend


def clear_mock_demand_trends() -> None:
    """Clear mock demand trends store."""
    _mock_demand_trends.clear()


def is_high_priority_drug(product_id: str, metadata: dict[str, Any] | None = None) -> tuple[bool, str]:
    """Check if product is classified as lifesaving or cold-chain, returning elevated priority."""
    meta = metadata or {}
    if meta.get("is_lifesaving") is True:
        return True, "critical"
    if meta.get("is_cold_chain") is True:
        return True, "high"

    p_lower = str(product_id).lower()
    if any(k in p_lower for k in ["lifesaving", "life-saving", "critical-care", "insulin", "vaccine"]):
        return True, "critical"
    if any(k in p_lower for k in ["cold-chain", "coldchain", "reefer"]):
        return True, "high"

    schedules = load_drug_schedules()
    for item in schedules:
        sku = str(item.get("sku", "")).lower()
        name = str(item.get("product_name", "")).lower()
        if (sku and sku in p_lower) or (name and name in p_lower) or (p_lower in sku):
            if item.get("is_lifesaving") is True:
                return True, "critical"
            if item.get("is_cold_chain") is True:
                return True, "high"
            category = str(item.get("category", "")).lower()
            if any(c in category for c in ["vaccine", "insulin", "cardiovascular", "oncology"]):
                return True, "critical"

    return False, "medium"


# -----------------------------------------------------------------------------
# Tool 1: list_nodes_in_cluster
# -----------------------------------------------------------------------------
@tool(
    name="list_nodes_in_cluster",
    description="Returns metadata for all peer stockist nodes within the same regional cluster.",
)
async def list_nodes_in_cluster(node_id: str, cluster_id: str | None = None) -> list[dict[str, Any]]:
    """Return all stockist nodes belonging to the regional cluster of the given node or cluster_id."""
    resolved_cluster = cluster_id

    # If Supabase is connected, query nodes
    if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY:
        try:
            client = get_service_db_client()
            if client:
                if not resolved_cluster:
                    n_res = client.table("nodes").select("*").eq("id", node_id).execute()
                    if n_res.data:
                        resolved_cluster = n_res.data[0].get("cluster_id") or n_res.data[0].get("region")

                if resolved_cluster:
                    c_res = (
                        client.table("nodes")
                        .select("*")
                        .eq("cluster_id", resolved_cluster)
                        .eq("tier", "stockist")
                        .execute()
                    )
                    if c_res.data:
                        return c_res.data
        except Exception as exc:
            logger.warning("DB list_nodes_in_cluster query failed (%s); using mock store.", exc)

    if not resolved_cluster:
        # Check in mock cluster nodes
        for cid, nodes in _mock_cluster_nodes.items():
            if any(n.get("id") == node_id for n in nodes):
                resolved_cluster = cid
                break

    resolved_cluster = resolved_cluster or "CLUSTER-DELHI-NORTH"
    return _mock_cluster_nodes.get(resolved_cluster, _mock_cluster_nodes["CLUSTER-DELHI-NORTH"])


# -----------------------------------------------------------------------------
# Tool 2: get_cluster_inventory
# -----------------------------------------------------------------------------
@tool(
    name="get_cluster_inventory",
    description="Returns current stock and safety stock levels for every stockist node in the specified cluster.",
)
async def get_cluster_inventory(cluster_id: str, product_id: str) -> list[dict[str, Any]]:
    """Return stock and safety stock levels for all stockist nodes in the cluster."""
    explicit_mock = _mock_cluster_inventory.get((str(cluster_id), str(product_id)))
    if explicit_mock is not None:
        return [dict(item) for item in explicit_mock]

    if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY:
        try:
            client = get_service_db_client()
            if client:
                nodes_res = (
                    client.table("nodes")
                    .select("id, name, cluster_id")
                    .eq("cluster_id", cluster_id)
                    .eq("tier", "stockist")
                    .execute()
                )
                if nodes_res.data:
                    node_ids = [n["id"] for n in nodes_res.data]
                    inv_res = (
                        client.table("inventory")
                        .select("node_id, product_id, quantity, safety_stock")
                        .in_("node_id", node_ids)
                        .eq("product_id", product_id)
                        .execute()
                    )
                    if inv_res.data:
                        results: list[dict[str, Any]] = []
                        for row in inv_res.data:
                            qty = int(row.get("quantity", 0))
                            safety = int(row.get("safety_stock", 20))
                            results.append({
                                "node_id": row["node_id"],
                                "product_id": product_id,
                                "quantity": qty,
                                "safety_stock": safety,
                                "surplus": max(0, qty - safety),
                            })
                        return results
        except Exception as exc:
            logger.warning("DB get_cluster_inventory failed (%s); using mock store.", exc)

    # Fallback default: query nodes in cluster and inspect each node's inventory
    cluster_nodes = _mock_cluster_nodes.get(cluster_id, _mock_cluster_nodes["CLUSTER-DELHI-NORTH"])
    aggregated: list[dict[str, Any]] = []
    for n in cluster_nodes:
        n_id = n["id"]
        inv_list = await get_inventory(node_id=n_id, product_id=product_id)
        qty = int(inv_list[0].get("quantity", 0)) if inv_list else 0
        safety = int(inv_list[0].get("safety_stock", 20)) if inv_list else 20
        aggregated.append({
            "node_id": n_id,
            "product_id": product_id,
            "quantity": qty,
            "safety_stock": safety,
            "surplus": max(0, qty - safety),
        })

    return aggregated


# -----------------------------------------------------------------------------
# Tool 3: get_demand_trend
# -----------------------------------------------------------------------------
@tool(
    name="get_demand_trend",
    description="Calculates recent sale velocity, velocity growth rate, and predicted depletion time.",
)
async def get_demand_trend(node_id: str, product_id: str, window_hours: int = 24) -> dict[str, Any]:
    """Calculate recent consumption velocity and growth rate to detect demand surges."""
    explicit = _mock_demand_trends.get((str(node_id), str(product_id)))
    if explicit is not None:
        return dict(explicit)

    # Default baseline trend
    return {
        "node_id": node_id,
        "product_id": product_id,
        "window_hours": window_hours,
        "velocity_units_per_hour": 2.5,
        "velocity_growth_rate": 1.1,  # 110% of normal
        "predicted_depletion_hours": 36.0,
        "is_burst_spike": False,
    }


# -----------------------------------------------------------------------------
# Tool 4: create_transfer
# -----------------------------------------------------------------------------
@tool(
    name="create_transfer",
    description="Inserts a peer-to-peer stock transfer record into the transfers table.",
)
async def create_transfer(
    from_node_id: str,
    to_node_id: str,
    product_id: str,
    quantity: int,
    priority: str = "medium",
    correlation_id: str = "",
) -> dict[str, Any]:
    """Insert a peer-to-peer transfer record into Supabase transfers table and memory store."""
    corr_id = correlation_id or str(uuid.uuid4())
    transfer_record = {
        "id": str(uuid.uuid4()),
        "from_node_id": from_node_id,
        "to_node_id": to_node_id,
        "product_id": product_id,
        "quantity": quantity,
        "status": "pending",
        "priority": priority,
        "correlation_id": corr_id,
        "metadata": {"is_synthetic": True, "created_by": "StockistAgent"},
        "created_at": datetime.now(UTC).isoformat(),
    }

    if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY:
        try:
            client = get_service_db_client()
            if client:
                client.table("transfers").insert(transfer_record).execute()
                logger.info("Transfer [%s] persisted to Supabase transfers table", transfer_record["id"])
        except Exception as exc:
            logger.warning("DB create_transfer failed (%s); saved to in-memory store.", exc)

    _in_memory_transfers.append(transfer_record)
    return transfer_record


# -----------------------------------------------------------------------------
# Tool 5: create_order
# -----------------------------------------------------------------------------
@tool(
    name="create_order",
    description="Inserts an escalation replenishment order record into the orders table targeting a distributor.",
)
async def create_order(
    from_node_id: str,
    to_node_id: str,
    product_id: str,
    quantity: int,
    priority: str = "medium",
    correlation_id: str = "",
) -> dict[str, Any]:
    """Insert an escalation order record targeting parent distributor into Supabase orders table."""
    corr_id = correlation_id or str(uuid.uuid4())
    order_record = {
        "id": str(uuid.uuid4()),
        "pharmacy_id": from_node_id,  # Buyer node in orders schema
        "stockist_id": to_node_id,    # Seller node in orders schema (distributor)
        "product_id": product_id,
        "quantity": quantity,
        "status": "requested",
        "priority": priority,
        "correlation_id": corr_id,
        "metadata": {
            "is_synthetic": True,
            "escalated_from": from_node_id,
            "escalated_to": to_node_id,
            "reason": "Cluster-wide stock deficit; escalated to distributor",
        },
        "created_at": datetime.now(UTC).isoformat(),
    }

    if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY:
        try:
            client = get_service_db_client()
            if client:
                client.table("orders").insert(order_record).execute()
                logger.info("Escalation order [%s] persisted to Supabase orders table", order_record["id"])
        except Exception as exc:
            logger.warning("DB create_order escalation failed (%s); saved to in-memory store.", exc)

    from app.agents.pharmacy_agent import _in_memory_orders
    _in_memory_orders.append(order_record)
    return order_record
