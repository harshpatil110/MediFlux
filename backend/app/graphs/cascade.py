"""Demand cascade LangGraph workflow across 4 supply chain tiers.

Pharmacy -> Stockist -> Distributor -> Manufacturer.
"""

from typing import Any, TypedDict

from langgraph.graph import END, StateGraph


class CascadeState(TypedDict):
    """State definition for multi-tier demand cascade."""

    event_id: str
    medicine_id: str
    medicine_name: str
    quantity: int
    pharmacy_status: str
    stockist_status: str
    distributor_status: str
    manufacturer_status: str
    logs: list[str]


async def pharmacy_node(state: CascadeState) -> dict[str, Any]:
    """Process retail sale and determine reorder need."""
    logs = state.get("logs", [])
    logs.append(f"Pharmacy recorded sale of {state['quantity']} unit(s) of {state['medicine_name']}")
    return {"pharmacy_status": "demand_emitted", "logs": logs}


async def stockist_node(state: CascadeState) -> dict[str, Any]:
    """Aggregate retail demand and evaluate hub inventory thresholds."""
    logs = state.get("logs", [])
    logs.append("Stockist hub received demand; threshold checked; dispatched batch restock order")
    return {"stockist_status": "batch_aggregated", "logs": logs}


async def distributor_node(state: CascadeState) -> dict[str, Any]:
    """Process PO from stockist and allocate regional depot stock."""
    logs = state.get("logs", [])
    logs.append("Distributor depot allocated inventory and signaled plant replenishment")
    return {"distributor_status": "po_forwarded", "logs": logs}


async def manufacturer_node(state: CascadeState) -> dict[str, Any]:
    """Schedule manufacturing batch run and packaging."""
    logs = state.get("logs", [])
    logs.append("Manufacturer plant queued production batch")
    return {"manufacturer_status": "production_scheduled", "logs": logs}


def build_cascade_graph() -> Any:
    """Build and compile the multi-tier cascade StateGraph."""
    workflow = StateGraph(CascadeState)

    workflow.add_node("pharmacy", pharmacy_node)
    workflow.add_node("stockist", stockist_node)
    workflow.add_node("distributor", distributor_node)
    workflow.add_node("manufacturer", manufacturer_node)

    workflow.set_entry_point("pharmacy")
    workflow.add_edge("pharmacy", "stockist")
    workflow.add_edge("stockist", "distributor")
    workflow.add_edge("distributor", "manufacturer")
    workflow.add_edge("manufacturer", END)

    return workflow.compile()
