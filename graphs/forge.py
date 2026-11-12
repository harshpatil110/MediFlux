"""Root re-export alias for Adapter Forge graph."""

import sys
from pathlib import Path

# Ensure backend is in python path
backend_path = str(Path(__file__).resolve().parent.parent / "backend")
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from app.graphs.forge import (  # noqa: E402
    ForgeState,
    build_forge_graph,
    clear_adapter_store,
    forge_graph,
    get_adapter,
    get_forge_job,
    list_adapter_versions,
    list_adapters,
    rollback_adapter,
    run_forge,
    save_adapter,
    save_forge_job,
)

__all__ = [
    "ForgeState",
    "build_forge_graph",
    "clear_adapter_store",
    "forge_graph",
    "get_adapter",
    "get_forge_job",
    "list_adapter_versions",
    "list_adapters",
    "rollback_adapter",
    "run_forge",
    "save_adapter",
    "save_forge_job",
]
