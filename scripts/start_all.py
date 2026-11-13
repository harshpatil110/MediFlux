"""MediFlux Unified Full-Stack Launcher (Task 28).

Orchestrates FastAPI backend, Vite web frontend, and Electron/Tauri desktop wrapper.
Supports --check-only flag for CI/pytest verification without spawning daemon processes.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Literal

ROOT_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT_DIR / "backend"
FRONTEND_DIR = ROOT_DIR / "frontend"
DESKTOP_DIR = ROOT_DIR / "desktop"


def verify_environment(verbose: bool = True) -> bool:
    """Verify all required files and artifacts exist for desktop and web packaging."""
    critical_paths = [
        BACKEND_DIR / "app" / "main.py",
        BACKEND_DIR / "app" / "core" / "config.py",
        FRONTEND_DIR / "vite.config.ts",
        FRONTEND_DIR / "src" / "App.tsx",
        FRONTEND_DIR / "src" / "config" / "env.ts",
        FRONTEND_DIR / "src" / "components" / "layout" / "BackendSettingsModal.tsx",
        DESKTOP_DIR / "package.json",
        DESKTOP_DIR / "main.cjs",
        DESKTOP_DIR / "preload.cjs",
        DESKTOP_DIR / "icons" / "icon.ico",
        DESKTOP_DIR / "icons" / "icon.png",
        DESKTOP_DIR / "src-tauri" / "tauri.conf.json",
        DESKTOP_DIR / "src-tauri" / "Cargo.toml",
    ]

    missing = [str(p.relative_to(ROOT_DIR)) for p in critical_paths if not p.exists()]
    if missing:
        if verbose:
            print(f"[FAIL] Missing critical paths: {missing}", file=sys.stderr)
        return False

    if verbose:
        print("[OK] All critical backend, frontend, Tauri, and Electron files verified.")
        print(f"     Root Directory: {ROOT_DIR}")
        print(f"     Desktop Entry:  {DESKTOP_DIR / 'main.cjs'}")
        print(f"     Tauri Conf:     {DESKTOP_DIR / 'src-tauri' / 'tauri.conf.json'}")

    return True


def run_check_only() -> int:
    """Execute dry-run environment validation and exit cleanly."""
    print("==================================================")
    print("  MediFlux Desktop & Full-Stack Preflight Check   ")
    print("==================================================")
    is_valid = verify_environment(verbose=True)
    if is_valid:
        print("\n[SUCCESS] MediFlux Desktop & Full-Stack launcher check passed cleanly.")
        return 0
    print("\n[FAILURE] Preflight check failed.")
    return 1


def launch(mode: Literal["desktop", "web", "both"], port: int = 8000) -> int:
    """Launch backend along with selected client interface."""
    if not verify_environment(verbose=True):
        return 1

    venv_python = BACKEND_DIR / "venv" / "Scripts" / "python.exe"
    python_exec = str(venv_python) if venv_python.exists() else sys.executable

    npm_cmd = "npm.cmd" if os.name == "nt" else "npm"

    processes: list[subprocess.Popen] = []

    try:
        print(f"[Backend] Starting FastAPI on http://localhost:{port} ...")
        backend_proc = subprocess.Popen(
            [python_exec, "-m", "uvicorn", "app.main:app", "--reload", "--port", str(port)],
            cwd=str(BACKEND_DIR),
        )
        processes.append(backend_proc)

        # Allow backend to bind socket
        time.sleep(2)

        if mode in ("web", "both"):
            print("[Frontend] Starting Vite dev server on http://localhost:5173 ...")
            web_proc = subprocess.Popen(
                [npm_cmd, "run", "dev"],
                cwd=str(FRONTEND_DIR),
            )
            processes.append(web_proc)

        if mode in ("desktop", "both"):
            print("[Desktop] Launching MediFlux Desktop shell (Electron) ...")
            desktop_proc = subprocess.Popen(
                [npm_cmd, "run", "desktop:dev"],
                cwd=str(DESKTOP_DIR),
            )
            processes.append(desktop_proc)

        print("\nAll MediFlux processes running. Press Ctrl+C to terminate.")
        while True:
            time.sleep(1)
            for p in processes:
                if p.poll() is not None:
                    print(f"Process {p.args} exited with code {p.returncode}")
                    return p.returncode

    except KeyboardInterrupt:
        print("\nShutting down all MediFlux processes gracefully...")
    finally:
        for p in processes:
            if p.poll() is None:
                p.terminate()
                try:
                    p.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    p.kill()

    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="MediFlux Full-Stack & Desktop Application Launcher")
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Run environment and desktop packaging preflight checks without launching processes.",
    )
    parser.add_argument(
        "--mode",
        choices=["desktop", "web", "both"],
        default="both",
        help="Launch target: desktop shell, web browser, or both (default: both).",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="FastAPI backend port (default: 8000).",
    )

    args = parser.parse_args()

    if args.check_only:
        sys.exit(run_check_only())

    sys.exit(launch(mode=args.mode, port=args.port))


if __name__ == "__main__":
    main()
