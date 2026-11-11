"""Cold chain telemetry excursion management workflow (Task 20)."""

from typing import Any, TypedDict

from langgraph.graph import END, StateGraph


class ColdChainState(TypedDict):
    """State for cold-chain excursion analysis."""

    shipment_id: str
    temperature_celsius: float
    allowed_range: tuple[float, float]
    excursion_detected: bool
    quarantine_action: str


async def check_temperature_node(state: ColdChainState) -> dict[str, Any]:
    """Check temperature reading against compliant thresholds."""
    low, high = state["allowed_range"]
    temp = state["temperature_celsius"]
    breached = temp < low or temp > high
    return {"excursion_detected": breached}


async def quarantine_remediation_node(state: ColdChainState) -> dict[str, Any]:
    """Flag batch for inspection and halt dispatch if breached."""
    if state.get("excursion_detected"):
        return {"quarantine_action": "isolate_batch"}
    return {"quarantine_action": "none"}


def build_coldchain_graph() -> Any:
    """Build cold chain telemetry monitoring graph."""
    workflow = StateGraph(ColdChainState)
    workflow.add_node("check_temperature", check_temperature_node)
    workflow.add_node("quarantine_remediation", quarantine_remediation_node)
    workflow.set_entry_point("check_temperature")
    workflow.add_edge("check_temperature", "quarantine_remediation")
    workflow.add_edge("quarantine_remediation", END)
    return workflow.compile()
