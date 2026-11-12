"""Administrative control endpoints for POS traffic simulator."""

import asyncio
import logging
from typing import Any, Literal

from fastapi import APIRouter, Request, status
from pydantic import BaseModel, Field

from app.simulator.pos_simulator import POSSimulator

logger = logging.getLogger("mediflux.api.simulator")

router = APIRouter(prefix="/simulator", tags=["Simulator Admin Control"])

# Active background simulation state
_active_simulator: POSSimulator | None = None
_active_task: asyncio.Task[Any] | None = None


class SimulationRunRequest(BaseModel):
    """Payload to trigger a background POS traffic simulation."""

    mode: Literal["single", "steady", "burst", "stockout_run"] = "steady"
    rate: float = Field(default=2.0, ge=0.1, le=100.0, description="Sales per second for steady mode")
    duration_seconds: int = Field(default=10, ge=1, le=3600, description="Simulation duration in seconds")
    intensity: int = Field(default=50, ge=1, le=1000, description="Total sales for burst mode")
    target_node_id: str | None = Field(default=None, description="Optional target pharmacy UUID")
    target_product_id: str | None = Field(default=None, description="Optional target product UUID")
    region: str | None = Field(default=None, description="Optional geographic region filter")


class SimulationRunResponse(BaseModel):
    status: str
    simulation_id: str
    mode: str


class SimulationStatusResponse(BaseModel):
    simulation_id: str | None = None
    status: str
    mode: str | None = None
    rate: float | None = None
    events_sent: int = 0
    errors_count: int = 0
    last_event_time: str | None = None
    target_node_id: str | None = None
    target_product_id: str | None = None


@router.post(
    "/run",
    response_model=SimulationRunResponse,
    status_code=status.HTTP_200_OK,
    summary="Start background POS simulation",
)
async def start_simulation(payload: SimulationRunRequest, request: Request) -> SimulationRunResponse:
    """Spawn an asyncio.Task running POSSimulator in the background."""
    global _active_simulator, _active_task

    # Stop any previous task
    if _active_simulator and _active_simulator.is_running:
        _active_simulator.stop()
    if _active_task and not _active_task.done():
        _active_task.cancel()

    sim = POSSimulator(
        app=request.app,
        mode=payload.mode,
        rate=payload.rate,
        duration_seconds=payload.duration_seconds,
        intensity=payload.intensity,
        target_pharmacy_id=payload.target_node_id,
        target_product_id=payload.target_product_id,
        region=payload.region,
    )
    _active_simulator = sim

    # Run background task
    async def _runner() -> None:
        try:
            await sim.run()
        except asyncio.CancelledError:
            logger.info("Simulation task %s cancelled", sim.simulation_id)
        except Exception as exc:
            logger.error("Simulation background error: %s", exc)

    _active_task = asyncio.create_task(_runner())

    return SimulationRunResponse(
        status="started",
        simulation_id=sim.simulation_id,
        mode=payload.mode,
    )


@router.post(
    "/stop",
    summary="Stop active POS simulation",
    status_code=status.HTTP_200_OK,
)
async def stop_simulation() -> dict[str, str]:
    """Cancel active background simulation task."""
    global _active_simulator, _active_task

    if _active_simulator:
        _active_simulator.stop()
    if _active_task and not _active_task.done():
        _active_task.cancel()

    return {"status": "stopped"}


@router.get(
    "/status",
    response_model=SimulationStatusResponse,
    summary="Get active POS simulation status",
)
async def get_simulation_status() -> SimulationStatusResponse:
    """Retrieve telemetry and operational status for POS simulator."""
    global _active_simulator

    if not _active_simulator:
        return SimulationStatusResponse(
            status="idle",
            events_sent=0,
            errors_count=0,
        )

    st = _active_simulator.get_status()
    return SimulationStatusResponse(
        simulation_id=st["simulation_id"],
        status=st["status"],
        mode=st["mode"],
        rate=st["rate"],
        events_sent=st["events_sent"],
        errors_count=st["errors_count"],
        last_event_time=st["last_event_time"],
        target_node_id=st["target_node_id"],
        target_product_id=st["target_product_id"],
    )

