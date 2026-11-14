"""Background worker identifying and auto-rejecting expired HITL tasks."""

import asyncio
import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from app.core.config import settings
from app.core.hitl import (
    get_in_memory_hitl_tasks,
    record_audit_log,
    record_hitl_decision,
    resume_graph_thread,
)
from app.core.security import get_service_db_client
from app.events.bus import in_process_event_bus
from app.events.models import EventEnvelope

logger = logging.getLogger("mediflux.workers.hitl_expiry")


async def process_expired_hitl_tasks() -> list[dict[str, Any]]:
    """Scan and safely auto-reject pending HITL tasks past their expiration deadline."""
    now_dt = datetime.now(UTC)
    now_iso = now_dt.isoformat()
    expired_tasks: list[dict[str, Any]] = []

    # 1. Query Supabase database if configured
    if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY:
        try:
            client = get_service_db_client()
            if client:
                resp = (
                    client.table("hitl_tasks")
                    .select("*")
                    .eq("status", "pending")
                    .lt("expires_at", now_iso)
                    .execute()
                )
                if resp.data:
                    expired_tasks.extend(resp.data)
        except Exception as exc:
            logger.warning("DB query for expired hitl_tasks failed (%s); checking memory", exc)

    # 2. Check in-memory store for pending expired tasks
    for task in get_in_memory_hitl_tasks():
        if task.get("status") == "pending":
            exp_val = task.get("expires_at")
            if exp_val:
                try:
                    exp_dt = (
                        exp_val
                        if isinstance(exp_val, datetime)
                        else datetime.fromisoformat(str(exp_val))
                    )
                    if exp_dt.tzinfo is None:
                        exp_dt = exp_dt.replace(tzinfo=UTC)
                    if exp_dt < now_dt:
                        task_id = str(task.get("id") or task.get("task_id"))
                        if not any(str(t.get("id") or t.get("task_id")) == task_id for t in expired_tasks):
                            expired_tasks.append(task)
                except Exception as parse_err:
                    logger.debug("Could not parse expiry date %s: %s", exp_val, parse_err)

    if not expired_tasks:
        return []

    logger.info("Found %d expired HITL task(s) to auto-reject", len(expired_tasks))
    processed: list[dict[str, Any]] = []

    # 3. Process auto-rejection for each expired task
    for task in expired_tasks:
        task_id = str(task.get("id") or task.get("task_id"))
        corr_id = str(task.get("correlation_id", ""))
        nid = str(task.get("node_id", "00000000-0000-0000-0000-000000000000"))
        task_type = str(task.get("task_type") or task.get("step_name") or "unknown")

        # Mutate task record
        task["status"] = "expired"
        task["decision_note"] = "Auto-expired: Task expired without human intervention."
        task["decided_at"] = now_iso
        task["decided_by"] = "system:hitl_expiry_worker"

        # Update Supabase database
        if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY:
            try:
                client = get_service_db_client()
                if client:
                    client.table("hitl_tasks").update({
                        "status": "expired",
                        "decision_note": "Auto-expired: Task expired without human intervention.",
                        "decided_at": now_iso,
                    }).eq("id", task_id).execute()
            except Exception as exc:
                logger.warning("DB auto-reject update failed for task %s: %s", task_id, exc)

        # Write immutable audit ledger entry
        record_audit_log(
            action_type="HITL_TASK_AUTO_EXPIRED",
            payload={
                "task_id": task_id,
                "task_type": task_type,
                "correlation_id": corr_id,
                "reason": "expired",
                "auto_rejected_at": now_iso,
            },
            node_id=nid,
        )

        # Record decision resolution in memory
        record_hitl_decision(
            task_id,
            {
                "approved": False,
                "decision": "reject",
                "status": "expired",
                "reason": "expired",
                "note": "Auto-rejected: Task expired without human intervention.",
            },
        )

        # Emit SSE event (hitl_expired)
        expired_event = EventEnvelope(
            event_id=str(uuid.uuid4()),
            type="hitl_expired",
            node_id=nid,
            correlation_id=corr_id,
            payload={
                "task_id": task_id,
                "status": "expired",
                "decision": "reject",
                "reason": "expired",
                "event_type": "hitl_expired",
            },
        )
        await in_process_event_bus.publish("hitl", expired_event)

        # Resume paused LangGraph thread with rejection fallback
        try:
            resume_outcome = await resume_graph_thread(
                corr_id,
                {"approved": False, "reason": "expired"},
            )
            if resume_outcome is None:
                await resume_graph_thread(
                    task_id,
                    {"approved": False, "reason": "expired"},
                )
        except Exception as resume_err:
            logger.warning("Error resuming expired thread for task %s: %s", task_id, resume_err)

        processed.append(task)

    return processed


class HITLExpiryWorker:
    """Asynchronous background worker periodically checking for and expiring HITL tasks."""

    def __init__(self, check_interval_seconds: float = 30.0) -> None:
        self._running = False
        self._task: asyncio.Task[Any] | None = None
        self._interval = check_interval_seconds

    @property
    def is_running(self) -> bool:
        return self._running

    async def start(self) -> None:
        """Start the background periodic expiry loop."""
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("HITLExpiryWorker started with interval=%.1fs", self._interval)

    async def stop(self) -> None:
        """Stop background worker loop gracefully."""
        if not self._running:
            return

        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        logger.info("HITLExpiryWorker stopped")

    async def _run_loop(self) -> None:
        """Periodic evaluation loop."""
        while self._running:
            try:
                await process_expired_hitl_tasks()
            except Exception as exc:
                logger.error("Error in HITL expiry processing loop: %s", exc)

            try:
                await asyncio.sleep(self._interval)
            except asyncio.CancelledError:
                break


# Singleton background expiry worker
hitl_expiry_worker = HITLExpiryWorker()
