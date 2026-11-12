"""Idempotent seed pipeline script to populate MediFlux supply chain network."""

import argparse
import logging
from pathlib import Path
import sys

# Ensure backend/ is in sys.path
backend_path = Path(__file__).resolve().parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.agents.seed_agent import seed_agent

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("mediflux.scripts.seed")


def run_seed(dry_run: bool = False) -> dict[str, int]:
    """Execute synthetic supply chain database seeding."""
    logger.info("Initializing synthetic supply chain seeding pipeline...")

    if dry_run:
        data = seed_agent.generate_all()
        summary = {k: len(v) for k, v in data.items()}
        logger.info("[DRY RUN] Generated entities (not written to DB): %s", summary)
        return summary

    results = seed_agent.seed_database()
    logger.info("Seeding pipeline completed successfully.")
    for table, count in results.items():
        logger.info("  -> %-18s: %d records", table, count)

    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed MediFlux with realistic synthetic supply chain data.")
    parser.add_argument("--dry-run", action="store_true", help="Generate synthetic data without writing to database")
    args = parser.parse_args()

    run_seed(dry_run=args.dry_run)


if __name__ == "__main__":
    main()

