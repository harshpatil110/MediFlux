"""Command-line runner for POS traffic simulator."""

import argparse
import asyncio
import logging
from pathlib import Path
import sys

# Ensure backend/ is in sys.path
backend_path = Path(__file__).resolve().parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.main import app
from app.simulator.pos_simulator import POSSimulator

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("mediflux.scripts.simulate")


async def run_simulation(args: argparse.Namespace) -> None:
    """Run POS simulation with given arguments."""
    logger.info("Initializing POS Simulator (Mode: %s)...", args.mode)

    # Use in-process app if specified or as fallback
    simulator = POSSimulator(
        base_url=args.base_url,
        app=app,
        mode=args.mode,
        rate=args.rate,
        duration_seconds=args.duration,
        intensity=args.intensity,
        target_pharmacy_id=args.pharmacy_id,
        target_product_id=args.product_id,
        region=args.region,
    )

    try:
        result = await simulator.run()
        if args.mode == "single":
            last_res = result.get("last_result", {})
            event_id = last_res.get("event_id", "evt-sim-pos-001")
            print(f"[SUCCESS] Posted single SaleEvent (event_id: {event_id}). Inventory decremented.")
        elif args.mode == "steady":
            sent = result.get("events_sent", 0)
            dur = result.get("duration_seconds", 0)
            print(f"[SUCCESS] Steady mode completed: {sent} sales emitted over {dur}s.")
        elif args.mode == "burst":
            sent = result.get("events_sent", 0)
            print(f"[SUCCESS] Burst mode completed: {sent} sales emitted.")
        elif args.mode == "stockout_run":
            sent = result.get("events_sent", 0)
            f_stock = result.get("final_stock", 0)
            print(f"[SUCCESS] Stockout run completed: {sent} sales emitted. Final stock: {f_stock}.")
        else:
            print(f"[SUCCESS] Simulation completed: {result}")
    finally:
        await simulator.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Simulate retail point-of-sale (POS) traffic in MediFlux.")
    parser.add_argument(
        "--mode",
        choices=["single", "steady", "burst", "stockout_run"],
        default="single",
        help="Simulation traffic mode",
    )
    parser.add_argument("--pharmacy-id", type=str, default=None, help="Target pharmacy node UUID")
    parser.add_argument("--product-id", type=str, default=None, help="Target product UUID")
    parser.add_argument("--rate", type=float, default=2.0, help="Sales per second for steady mode")
    parser.add_argument("--duration", type=int, default=10, help="Duration in seconds for steady mode")
    parser.add_argument("--region", type=str, default=None, help="Geographic region for burst mode")
    parser.add_argument("--intensity", type=int, default=50, help="Total burst sales count")
    parser.add_argument("--base-url", type=str, default="http://127.0.0.1:8000", help="FastAPI backend base URL")

    args = parser.parse_args()
    asyncio.run(run_simulation(args))


if __name__ == "__main__":
    main()

