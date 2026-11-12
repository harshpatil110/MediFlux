"""Root simulator package re-exporting app.simulator."""

import sys
from pathlib import Path

# Ensure backend is in path
backend_path = Path(__file__).resolve().parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.simulator.pos_simulator import POSSimulator
from app.simulator.sensor_simulator import SensorSimulator

__all__ = ["POSSimulator", "SensorSimulator"]

