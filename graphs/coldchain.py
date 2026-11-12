"""Root alias for Cold-Chain Telemetry Graph."""

import sys
from pathlib import Path

# Add backend directory to sys.path if not present
backend_dir = str(Path(__file__).resolve().parent.parent / "backend")
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.graphs.coldchain import (
    DEFAULT_COLDCHAIN_BATCHES,
    ColdChainState,
    build_coldchain_graph,
    clear_coldchain_state,
    coldchain_graph,
    estimate_shelf_life,
    excursion_analyst_node,
    get_in_memory_coldchain_batches,
    get_in_memory_quarantine_actions,
    get_in_memory_sensor_readings,
    quarantine_execution_node,
    reset_coldchain_state,
    run_coldchain_pipeline,
    telemetry_agent_node,
)

__all__ = [
    "DEFAULT_COLDCHAIN_BATCHES",
    "ColdChainState",
    "build_coldchain_graph",
    "clear_coldchain_state",
    "coldchain_graph",
    "estimate_shelf_life",
    "excursion_analyst_node",
    "get_in_memory_coldchain_batches",
    "get_in_memory_quarantine_actions",
    "get_in_memory_sensor_readings",
    "quarantine_execution_node",
    "reset_coldchain_state",
    "run_coldchain_pipeline",
    "telemetry_agent_node",
]
