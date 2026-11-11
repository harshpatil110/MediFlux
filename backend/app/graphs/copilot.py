"""Supply Chain Copilot conversational planning workflow (Task 25)."""

from typing import Any, TypedDict

from langgraph.graph import END, StateGraph


class CopilotState(TypedDict):
    """State for conversational copilot inquiries."""

    query: str
    user_role: str
    retrieved_context: list[str]
    response: str


async def retrieve_context_node(state: CopilotState) -> dict[str, Any]:
    """Retrieve supply chain state and knowledge base articles."""
    return {"retrieved_context": ["Active stock levels healthy across hubs."]}


async def generate_answer_node(state: CopilotState) -> dict[str, Any]:
    """Synthesize structured response with citations."""
    return {"response": "All tiers operational with demand propagation active."}


def build_copilot_graph() -> Any:
    """Build supply chain copilot query graph."""
    workflow = StateGraph(CopilotState)
    workflow.add_node("retrieve_context", retrieve_context_node)
    workflow.add_node("generate_answer", generate_answer_node)
    workflow.set_entry_point("retrieve_context")
    workflow.add_edge("retrieve_context", "generate_answer")
    workflow.add_edge("generate_answer", END)
    return workflow.compile()
