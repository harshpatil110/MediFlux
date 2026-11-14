"""FastAPI endpoints for scripted demo state reset and telemetry inspection (Task 29)."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, status

from app.core.config import settings
from app.graphs.coldchain import (
    get_in_memory_coldchain_batches,
    get_in_memory_quarantine_actions,
)
from app.llm.cache import llm_cache
from app.modules_runtime.registry import module_registry

logger = logging.getLogger("mediflux.api.demo")

router = APIRouter(prefix="/demo", tags=["Demo Management"])


@router.post(
    "/reset",
    status_code=status.HTTP_200_OK,
    summary="Reset Demo State to Clean Baseline",
)
async def reset_demo_endpoint() -> dict[str, Any]:
    """Reset all dynamic modules to v1, un-quarantine batches, and clear transient tasks."""
    try:
        from scripts.reset_demo import reset_demo_state

        result = reset_demo_state()
    except ImportError:
        # Fallback if scripts package is not on sys.path
        import sys
        from pathlib import Path

        root_dir = Path(__file__).resolve().parent.parent.parent.parent.parent
        if str(root_dir) not in sys.path:
            sys.path.insert(0, str(root_dir))
        from scripts.reset_demo import reset_demo_state

        result = reset_demo_state()

    return {
        "status": "ok",
        "success": True,
        "message": "Demo state reset to clean baseline",
        **result,
    }


@router.get(
    "/status",
    status_code=status.HTTP_200_OK,
    summary="Get Demo & Cache Runtime Status",
)
async def demo_status_endpoint() -> dict[str, Any]:
    """Inspect active demo mode, LLM replay cache depth, and quarantined batch counts."""
    from app.core.hitl import get_in_memory_hitl_tasks

    batches = get_in_memory_coldchain_batches()
    quarantined = [b for b in batches if b.get("status") == "quarantined" or b.get("is_quarantined")]
    active_mods = module_registry.list_active_modules()
    hitl_tasks = get_in_memory_hitl_tasks()
    pending_hitl = [t for t in hitl_tasks if t.get("status") == "pending"]

    return {
        "demo_mode": settings.DEMO_MODE,
        "cache_mode": settings.LLM_CACHE_MODE,
        "cache_entries": llm_cache.count(),
        "baseline_module_status": {
            mod.name: f"v{mod.version} ({mod.status})" for mod in active_mods
        },
        "modules_status": {
            mod.name: f"v{mod.version} ({mod.status})" for mod in active_mods
        },
        "quarantine_count": len(quarantined),
        "total_batches": len(batches),
        "quarantined_batches": [b.get("batch_id") for b in quarantined],
        "quarantine_actions_count": len(get_in_memory_quarantine_actions()),
        "pending_hitl_tasks": len(pending_hitl),
        "pending_hitl_count": len(pending_hitl),
    }
