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
        logger.info("Simulation completed: %s", result)
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

