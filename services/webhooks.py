# ruff: noqa: E402
"""Root alias re-export for app.services.webhooks."""
import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent / "backend"
if backend_dir.exists() and str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.services.webhooks import *  # noqa: F401, F403
