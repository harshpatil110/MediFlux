# ruff: noqa: E402
"""Root convenience entrypoint for launching MediFlux MCP Server over stdio.

Usage:
    python mcp_server.py
    MEDIFLUX_API_KEY=mfx_live_... python mcp_server.py
"""

import sys
from pathlib import Path

# Ensure backend directory is in sys.path
repo_root = Path(__file__).resolve().parent
backend_dir = repo_root / "backend"

if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from app.mcp.server import mcp_server, run_stdio

__all__ = ["mcp_server", "run_stdio"]

if __name__ == "__main__":
    run_stdio()
