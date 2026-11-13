"""Root alias for Network Copilot graph."""

import sys
from pathlib import Path

backend_dir = str(Path(__file__).resolve().parent.parent / "backend")
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.graphs.copilot import (
    CopilotGraphState,
    CopilotReference,
    CopilotScope,
    answer_node,
    build_copilot_graph,
    copilot_graph,
    get_cold_chain_status,
    get_demand_signals,
    get_inventory_summary,
    get_open_hitl_tasks,
    get_recent_agent_activity,
    get_stockout_risk,
    planner_node,
    run_copilot,
    search_semantic,
    stream_copilot_events,
    tool_executor_node,
)

__all__ = [
    "CopilotGraphState",
    "CopilotReference",
    "CopilotScope",
    "answer_node",
    "build_copilot_graph",
    "copilot_graph",
    "get_cold_chain_status",
    "get_demand_signals",
    "get_inventory_summary",
    "get_open_hitl_tasks",
    "get_recent_agent_activity",
    "get_stockout_risk",
    "planner_node",
    "run_copilot",
    "search_semantic",
    "stream_copilot_events",
    "tool_executor_node",
]
