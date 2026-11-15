"""Export FastAPI OpenAPI schema to docs/openapi.json (Task 30)."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

os.environ["LLM_CACHE_MODE"] = "replay"
os.environ["DEMO_MODE"] = "true"

from app.core.config import settings

settings.LLM_CACHE_MODE = "replay"
settings.DEMO_MODE = True

from app.main import app


def export_openapi() -> Path:
    """Generate OpenAPI 3.1.0 schema dictionary and save to docs/openapi.json."""
    schema = app.openapi()
    out_path = ROOT_DIR / "docs" / "openapi.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(schema, indent=2, sort_keys=True), encoding="utf-8")
    num_paths = len(schema.get("paths", {}))
    print(f"OpenAPI schema successfully exported ({num_paths} paths) -> {out_path}")
    return out_path


if __name__ == "__main__":
    export_openapi()

