#!/usr/bin/env bash
# MediFlux Startup Script (Bash for Linux/macOS)
# Starts FastAPI backend and Vite frontend concurrently

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"

echo "=================================================="
echo "  Starting MediFlux Autonomous Pharma Platform     "
echo "=================================================="

# Check for Python
if ! command -v python3 &>/dev/null && ! command -v python &>/dev/null; then
    echo "Error: Python 3.11+ is required but not installed." >&2
    exit 1
fi

PYTHON_CMD="python3"
if ! command -v python3 &>/dev/null; then
    PYTHON_CMD="python"
fi

# Detect virtualenv if present
if [ -f "$BACKEND_DIR/venv/bin/python" ]; then
    PYTHON_CMD="$BACKEND_DIR/venv/bin/python"
    echo "[Backend] Using virtual environment at backend/venv"
fi

# Check for npm
if ! command -v npm &>/dev/null; then
    echo "Error: npm is required but not installed." >&2
    exit 1
fi

echo "[Backend] Starting FastAPI server on http://localhost:8000 ..."
(cd "$BACKEND_DIR" && "$PYTHON_CMD" -m uvicorn app.main:app --reload --port 8000) &
BACKEND_PID=$!

echo "[Frontend] Starting Vite development server on http://localhost:5173 ..."
(cd "$FRONTEND_DIR" && npm run dev) &
FRONTEND_PID=$!

cleanup() {
    echo ""
    echo "Stopping MediFlux background processes (PID $BACKEND_PID, $FRONTEND_PID)..."
    kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
    wait "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
    echo "All processes stopped cleanly."
}

trap cleanup SIGINT SIGTERM EXIT

echo ""
echo "MediFlux services initiated successfully:"
echo "  - Backend API:    http://localhost:8000/docs"
echo "  - Health Check:   http://localhost:8000/health"
echo "  - Frontend Web:   http://localhost:5173"
echo ""
echo "Press Ctrl+C to stop all services..."

wait

