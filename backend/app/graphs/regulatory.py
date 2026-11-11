"""Regulatory Notice ingest and supply chain impact analysis workflow (Task 24)."""

from typing import Any, TypedDict

from langgraph.graph import END, StateGraph


class RegulatoryState(TypedDict):
    """State for CDSCO/state regulatory notice evaluation."""

    notice_id: str
    authority: str
    raw_notice_text: str
    impacted_molecules: list[str]
    compliance_actions: list[str]


async def extract_impact_node(state: RegulatoryState) -> dict[str, Any]:
    """Parse regulatory notice to extract impacted molecules and schedules."""
    return {"impacted_molecules": []}


async def generate_actions_node(state: RegulatoryState) -> dict[str, Any]:
    """Generate recommended actions across stockists and pharmacies."""
    return {"compliance_actions": ["flag_inventory", "notify_pharmacists"]}


def build_regulatory_graph() -> Any:
    """Build regulatory notice ingestion and response graph."""
    workflow = StateGraph(RegulatoryState)
    workflow.add_node("extract_impact", extract_impact_node)
    workflow.add_node("generate_actions", generate_actions_node)
    workflow.set_entry_point("extract_impact")
    workflow.add_edge("extract_impact", "generate_actions")
    workflow.add_edge("generate_actions", END)
    return workflow.compile()
