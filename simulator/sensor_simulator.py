"""Root SensorSimulator proxy (Task 20)."""

import sys
from pathlib import Path

# Ensure backend directory is on sys.path
backend_path = Path(__file__).resolve().parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.simulator.sensor_simulator import SensorSimulator, main

__all__ = ["SensorSimulator", "main"]

if __name__ == "__main__":
    main()
