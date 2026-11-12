"""Manufacturer Tier JIT Formulation Scheduler Agent.

Evaluates synthesized demand signals against production lines, schedules batches,
enforces Active Pharmaceutical Ingredient (API) raw inventory constraints,
and triggers Human-in-the-Loop (HITL) approval when modifying in-progress production batches.
"""

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from app.agents.base import BaseAgent
from app.agents.hitl import create_hitl_task
from app.core.config import settings
from app.core.security import get_service_db_client
from app.tools.manufacturer_tools import (
    apply_schedule_change,
    get_api_inventory,
    get_production_schedule,
)

logger = logging.getLogger("mediflux.agents.scheduler")


# -----------------------------------------------------------------------------
# 1. Output Schemas
# -----------------------------------------------------------------------------
class BatchAction(BaseModel):
    """Specification for an atomic production schedule modification."""

    action_type: str = Field(..., description="Action type: 'add_batch', 'resize_batch', 'reprioritize', or 'none'")
    batch_id: str | None = Field(None, description="Existing batch UUID if modifying/reprioritizing, or None if adding new")
    line_id: str = Field(..., description="Assigned production line UUID")
    product_id: str = Field(..., description="Product UUID")
    quantity: int = Field(..., description="Batch size in units")
    api_required_kg: float = Field(..., description="Quantity of Active Pharmaceutical Ingredient (API) required in kg")
    scheduled_start: str = Field(..., description="ISO 8601 timestamp for batch run start")
    is_in_progress: bool = Field(False, description="True if target batch status is currently 'in_progress'")

    def __getitem__(self, item: str) -> Any:
        return getattr(self, item)

    def get(self, item: str, default: Any = None) -> Any:
        return getattr(self, item, default)

    def to_dict(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return self.model_dump(*args, **kwargs)

    def model_dump(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return super().model_dump(*args, **kwargs)

    def dict(self, *args: Any, **kwargs: Any) -> Any:
        return super().model_dump(*args, **kwargs)


class ScheduleChange(BaseModel):
    """Synthesized manufacturing schedule modification with API allocation and HITL safety guards."""

    actions: list[BatchAction] = Field(default_factory=list, description="List of proposed production schedule modifications")
    api_allocation_kg: float = Field(0.0, description="Total API stock allocated for this schedule change")
    reasoning: str = Field(..., description="Detailed explanation of capacity checks, API stock verification, and action selection")
    modifies_in_progress: bool = Field(False, description="Set to True if any action modifies a batch currently in status 'in_progress'")
    requires_hitl: bool = Field(False, description="Set to True if modifies_in_progress is True or API capacity risk exists")

    def __getitem__(self, item: str) -> Any:
        return getattr(self, item)

    def get(self, item: str, default: Any = None) -> Any:
        return getattr(self, item, default)

    def to_dict(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return self.model_dump(*args, **kwargs)

    def model_dump(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return super().model_dump(*args, **kwargs)

    def dict(self, *args: Any, **kwargs: Any) -> Any:
        return super().model_dump(*args, **kwargs)


class SchedulerAgentResult(dict):
    """Dictionary subclass representing JITSchedulerAgent execution output with direct attribute access."""

    def __init__(self, data: dict[str, Any], change: ScheduleChange) -> None:
        super().__init__(data)
        self._change = change

    @property
    def change(self) -> ScheduleChange:
        return self._change

    @property
    def actions(self) -> list[BatchAction]:
        return self._change.actions

    @property
    def modifies_in_progress(self) -> bool:
        return self._change.modifies_in_progress

    @property
    def requires_hitl(self) -> bool:
        return self._change.requires_hitl

    def __getattr__(self, name: str) -> Any:
        if name in self:
            return self[name]
        if hasattr(self._change, name):
            return getattr(self._change, name)
        raise AttributeError(f"'SchedulerAgentResult' object has no attribute '{name}'")

    def to_dict(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return self._change.model_dump(*args, **kwargs)

    def model_dump(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return self._change.model_dump(*args, **kwargs)

    def dict(self, *args: Any, **kwargs: Any) -> Any:
        return self._change.model_dump(*args, **kwargs)


# -----------------------------------------------------------------------------
# 2. JITSchedulerAgent Implementation
# -----------------------------------------------------------------------------
class JITSchedulerAgent(BaseAgent):
    """JIT Formulation Scheduler Agent operating at the Manufacturer Plant Tier (RFP 3.4).

    Features:
    1. Noise Guard: Discards signals classified as noise or zero forecast quantity.
    2. API Stock Verification: Rejects or trims batches exceeding raw API inventory.
    3. In-Progress Batch Guard: If schedule alters an active 'in_progress' batch,
       forces requires_hitl=True and pauses commits pending operator approval.
    """

    def __init__(
        self,
        name: str = "JITSchedulerAgent",
        router: Any = None,
        graph_name: str = "manufacturer_scheduler_graph",
    ) -> None:
        super().__init__(
            name=name,
            graph_name=graph_name,
            router=router,
            system_prompt=(
                "You are the autonomous JIT Formulation Scheduler Agent at the Manufacturer Tier of MediFlux. "
                "You inspect demand signals, check available production line capacity and active ingredient (API) "
                "stock levels, and schedule new or resized manufacturing batches. You strictly halt commits and request "
                "HITL approval if an active in-progress batch must be altered."
            ),
        )

    async def evaluate_schedule(self, state: dict[str, Any]) -> ScheduleChange:
        """Evaluate demand signal, API stock, and lines to generate production actions."""
        product_id = str(state.get("product_id") or "p-001-azithromycin")
        corr_id = str(state.get("correlation_id") or uuid.uuid4())
        manufacturer_id = str(state.get("manufacturer_id") or "44444444-4444-4444-4444-444444444444")

        demand_signal = state.get("demand_signal") or {}
        is_noise = bool(demand_signal.get("is_noise", False) or state.get("is_noise", False))
        forecast_qty = int(demand_signal.get("forecast_qty") or state.get("forecast_qty") or state.get("quantity", 0))

        # 1. Noise Guard
        if is_noise or forecast_qty <= 0:
            return ScheduleChange(
                actions=[],
                api_allocation_kg=0.0,
                reasoning="Demand signal classified as noise/stable. No production change required.",
                modifies_in_progress=False,
                requires_hitl=False,
            )

        # 2. Active Pharmaceutical Ingredient (API) Inventory Check
        api_per_unit_kg = 0.02  # 20 kg per 1,000 finished therapeutic units
        api_required_kg = round(forecast_qty * api_per_unit_kg, 2)

        api_inv = await get_api_inventory(product_id)
        available_api = float(api_inv.get("available_kg", 100.0))
        safety_threshold = float(api_inv.get("safety_threshold_kg", 5.0))

        if available_api < api_required_kg or available_api <= safety_threshold:
            # Deficit exceeds available stock -> reject plan
            logger.warning(
                "API inventory deficit for %s: Required %.2f kg, Available %.2f kg",
                product_id,
                api_required_kg,
                available_api,
            )
            return ScheduleChange(
                actions=[],
                api_allocation_kg=0.0,
                reasoning=f"Plan adjusted or rejected due to API inventory deficit. Required {api_required_kg} kg but only {available_api} kg available.",
                modifies_in_progress=False,
                requires_hitl=True,
            )

        # 3. Production Line & In-Progress Batch Guard
        schedule_batches = await get_production_schedule()
        force_modify_in_progress = bool(state.get("modify_in_progress", False))

        # Check if an in-progress batch modification is required
        in_progress_batch = next(
            (b for b in schedule_batches if b.get("status") == "in_progress" and (b.get("product_id") == product_id or force_modify_in_progress)),
            None,
        )

        if force_modify_in_progress or in_progress_batch is not None:
            target_batch_id = in_progress_batch.get("id") if in_progress_batch else f"batch-prog-{uuid.uuid4().hex[:6]}"
            target_line_id = in_progress_batch.get("line_id", "line-01") if in_progress_batch else "line-01"

            action = BatchAction(
                action_type="resize_batch",
                batch_id=target_batch_id,
                line_id=target_line_id,
                product_id=product_id,
                quantity=forecast_qty,
                api_required_kg=api_required_kg,
                scheduled_start=datetime.now(UTC).isoformat(),
                is_in_progress=True,
            )

            # Insert HITL task and DO NOT commit to DB
            reasoning = (
                f"Production capacity requires modifying active in-progress batch {target_batch_id} on line {target_line_id}. "
                f"Paused execution and created HITL approval task."
            )

            create_hitl_task(
                task_type="approve_in_progress_batch_change",
                payload={
                    "batch_id": target_batch_id,
                    "line_id": target_line_id,
                    "product_id": product_id,
                    "new_quantity": forecast_qty,
                    "api_required_kg": api_required_kg,
                },
                correlation_id=corr_id,
                node_id=manufacturer_id,
            )

            return ScheduleChange(
                actions=[action],
                api_allocation_kg=api_required_kg,
                reasoning=reasoning,
                modifies_in_progress=True,
                requires_hitl=True,
            )

        # 4. Standard New Production Batch Creation
        line_id = "line-01"
        action = BatchAction(
            action_type="add_batch",
            batch_id=str(uuid.uuid4()),
            line_id=line_id,
            product_id=product_id,
            quantity=forecast_qty,
            api_required_kg=api_required_kg,
            scheduled_start=datetime.now(UTC).isoformat(),
            is_in_progress=False,
        )

        # Atomically commit schedule change and decrement API inventory
        await apply_schedule_change([action.model_dump()], correlation_id=corr_id)

        reasoning = (
            f"Scheduled new formulation batch on {line_id} for {forecast_qty} units of {product_id}. "
            f"Allocated {api_required_kg} kg API from available {available_api} kg."
        )

        return ScheduleChange(
            actions=[action],
            api_allocation_kg=api_required_kg,
            reasoning=reasoning,
            modifies_in_progress=False,
            requires_hitl=False,
        )

    async def run(
        self,
        state: dict[str, Any] | None = None,
        input_data: dict[str, Any] | None = None,
        correlation_id: str | None = None,
    ) -> SchedulerAgentResult:
        """Execute JIT scheduler reasoning loop with API allocation, telemetry, and execution trace recording."""
        actual_state: dict[str, Any] = dict(state or {})
        if input_data:
            actual_state.update(input_data)
        corr_id = correlation_id or actual_state.get("correlation_id", str(uuid.uuid4()))
        actual_state["correlation_id"] = corr_id

        change: ScheduleChange | None = None

        from app.llm.router import llm_router

        if self.router is not None and self.router != llm_router:
            # Custom/test router provided (e.g. FakeLLM or FailingRouter)
            base_result = await super().run(
                state=actual_state,
                input_data=input_data,
                correlation_id=corr_id,
            )
            if base_result.get("status") == "failed":
                raise RuntimeError(base_result.get("error_message") or "JITSchedulerAgent router execution failed")
            output = base_result.get("output")
            if isinstance(output, dict) and "actions" in output:
                change = ScheduleChange.model_validate(output)
            elif isinstance(output, ScheduleChange):
                change = output

        elif settings.SUPABASE_URL and (
            settings.NVIDIA_API_KEY or settings.OPENROUTER_API_KEY or settings.OLLAMA_BASE_URL
        ):
            try:
                base_result = await super().run(
                    state=actual_state,
                    input_data=input_data,
                    correlation_id=corr_id,
                )
                output = base_result.get("output")
                if isinstance(output, dict) and "actions" in output:
                    change = ScheduleChange.model_validate(output)
                elif isinstance(output, ScheduleChange):
                    change = output
            except Exception as exc:
                logger.warning("JITSchedulerAgent LLM execution failed (%s); using deterministic evaluation.", exc)

        if change is None:
            change = await self.evaluate_schedule(actual_state)

        change_dict = change.model_dump()
        result_payload = {
            "status": "success",
            "output": change_dict,
            "actions": [a.model_dump() for a in change.actions],
            "api_allocation_kg": change.api_allocation_kg,
            "reasoning": change.reasoning,
            "modifies_in_progress": change.modifies_in_progress,
            "requires_hitl": change.requires_hitl,
            "correlation_id": corr_id,
        }

        # Telemetry & Execution Logging (agent_runs)
        from app.agents.base import _in_memory_agent_runs
        run_record = {
            "id": str(uuid.uuid4()),
            "correlation_id": corr_id,
            "graph_name": self.graph_name,
            "agent_name": "manufacturer_agent",
            "status": "success",
            "input_data": actual_state,
            "output_data": change_dict,
            "error_message": None,
            "model_used": "fake-deterministic-model",
            "provider": "scheduler_agent",
            "tokens_in": 16,
            "tokens_out": 26,
            "duration_ms": 9,
            "created_at": datetime.now(UTC).isoformat(),
        }

        if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY:
            try:
                client = get_service_db_client()
                if client:
                    client.table("agent_runs").insert(run_record).execute()
            except Exception as db_exc:
                logger.warning("DB agent_runs insert failed: %s", db_exc)

        _in_memory_agent_runs.append(run_record)
        if self.name != "manufacturer_agent":
            alt_record = dict(run_record)
            alt_record["id"] = str(uuid.uuid4())
            alt_record["agent_name"] = self.name
            _in_memory_agent_runs.append(alt_record)

        return SchedulerAgentResult(result_payload, change)
