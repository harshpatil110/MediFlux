"""Root re-export alias for Regulatory pipeline graph."""

import sys
from pathlib import Path

# Ensure backend is in python path
backend_path = str(Path(__file__).resolve().parent.parent / "backend")
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from app.graphs.regulatory import (
    RegChange,
    RegulatoryState,
    activate_regulatory_run,
    build_regulatory_graph,
    clear_regulatory_store,
    crawl_regulatory_notice,
    ensure_baseline_regulatory_modules,
    get_notification,
    get_regulatory_run,
    list_notifications,
    regulatory_graph,
    rollback_regulatory_run,
    run_regulatory_pipeline,
    save_notification,
    save_regulatory_run,
)

__all__ = [
    "RegChange",
    "RegulatoryState",
    "activate_regulatory_run",
    "build_regulatory_graph",
    "clear_regulatory_store",
    "crawl_regulatory_notice",
    "ensure_baseline_regulatory_modules",
    "get_notification",
    "get_regulatory_run",
    "list_notifications",
    "regulatory_graph",
    "rollback_regulatory_run",
    "run_regulatory_pipeline",
    "save_notification",
    "save_regulatory_run",
]
