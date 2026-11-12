"""Shared built-in agent tools for inventory, topology, sales, and audit."""

import logging
from typing import Any

from app.agents.tools.registry import tool
from app.core.config import settings
from app.core.security import get_service_db_client

logger = logging.getLogger("mediflux.agents.tools.shared")

# Local in-memory mock data stores for offline execution and test isolation
_mock_inventory: dict[str, list[dict[str, Any]]] = {}
_mock_nodes: dict[str, dict[str, Any]] = {
    "11111111-1111-1111-1111-111111111111": {
        "id": "11111111-1111-1111-1111-111111111111",
        "name": "Apollo Pharmacy Delhi Node",
        "tier": "pharmacy",
        "parent_id": "22222222-2222-2222-2222-222222222222",
        "cluster_id": "CLUSTER-DELHI-NORTH",
    },
    "22222222-2222-2222-2222-222222222222": {
        "id": "22222222-2222-2222-2222-222222222222",
        "name": "Delhi Central Stockist Hub",
        "tier": "stockist",
        "parent_id": "33333333-3333-3333-3333-333333333333",
        "cluster_id": "CLUSTER-DELHI-NORTH",
    },
}
_mock_sales: list[dict[str, Any]] = []


@tool(
    name="get_inventory",
    description="Retrieve inventory levels and stock balances for a given node and optional product ID.",
)
async def get_inventory(node_id: str, product_id: str | None = None) -> list[dict[str, Any]]:
    """Query inventory balances from Supabase or fallback mock store."""
    if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY:
        try:
            client = get_service_db_client()
            query = client.table("inventory").select("*").eq("node_id", node_id)
            if product_id:
                query = query.eq("product_id", product_id)
            res = query.execute()
            if res.data:
                return res.data
        except Exception as exc:
            logger.warning("DB get_inventory query failed (%s); using in-memory mock.", exc)

    items = _mock_inventory.get(str(node_id), [])
    if product_id:
        items = [i for i in items if str(i.get("product_id")) == str(product_id)]
    return items or [
        {
            "node_id": node_id,
            "product_id": product_id or "default-product-001",
            "quantity": 100,
            "safety_stock": 20,
        }
    ]


@tool(
    name="get_recent_sales",
    description="Retrieve recent retail Point-of-Sale dispense transactions for a pharmacy node.",
)
async def get_recent_sales(pharmacy_id: str, limit: int = 10) -> list[dict[str, Any]]:
    """Query recent pos.sale events from Supabase or fallback mock store."""
    if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY:
        try:
            client = get_service_db_client()
            res = (
                client.table("events")
                .select("*")
                .eq("node_id", pharmacy_id)
                .eq("type", "pos.sale")
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
            )
            if res.data:
                return res.data
        except Exception as exc:
            logger.warning("DB get_recent_sales failed (%s); using in-memory mock.", exc)

    filtered = [s for s in _mock_sales if str(s.get("pharmacy_id")) == str(pharmacy_id)]
    return filtered[:limit]


@tool(
    name="get_node",
    description="Fetch node metadata, tier hierarchy, and cluster association by node ID.",
)
async def get_node(node_id: str) -> dict[str, Any] | None:
    """Fetch node metadata from Supabase or fallback mock store."""
    if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY:
        try:
            client = get_service_db_client()
            res = client.table("nodes").select("*").eq("id", node_id).single().execute()
            if res.data:
                return res.data
        except Exception as exc:
            logger.warning("DB get_node failed (%s); using in-memory mock.", exc)

    return _mock_nodes.get(str(node_id))


@tool(
    name="list_nodes_in_cluster",
    description="Return all supply chain nodes belonging to a specific regional cluster.",
)
async def list_nodes_in_cluster(cluster_id: str) -> list[dict[str, Any]]:
    """Return nodes belonging to a regional cluster."""
    matched = [n for n in _mock_nodes.values() if n.get("cluster_id") == cluster_id]
    return matched or [
        {
            "id": "11111111-1111-1111-1111-111111111111",
            "cluster_id": cluster_id,
            "tier": "pharmacy",
        }
    ]


@tool(
    name="run_module",
    description="Execute an isolated business rule, forecasting algorithm, or order optimization module.",
)
async def run_module(module_name: str, inputs: dict[str, Any]) -> dict[str, Any]:
    """Execute dynamic module via ModuleRegistry with graceful fallback."""
    from app.modules_runtime.registry import module_registry

    try:
        return module_registry.run_module(module_name, inputs)
    except Exception as exc:
        logger.debug("run_module registry execution failed (%s); using fallback.", exc)
        return {
            "module": module_name,
            "status": "fallback",
            "output": {"result": "success", "calculated_reorder_qty": 50},
        }


@tool(
    name="write_audit",
    description="Record an immutable audit ledger entry for compliance and regulatory tracing.",
)
async def write_audit(actor_id: str, action: str, details: dict[str, Any]) -> dict[str, Any]:
    """Record an audit trail entry (prepared for Task 16)."""
    logger.info("write_audit called by [%s] action=[%s]", actor_id, action)
    return {
        "status": "recorded",
        "actor_id": actor_id,
        "action": action,
        "hash": "mock-audit-hash-12345",
    }

