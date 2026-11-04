#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DIR"

echo "======================================================================"
echo " ⚡ RELAYOS: AUTONOMOUS ENTERPRISE DEAL CLOSING PLATFORM"
echo " Track 01: Best Business Workflow — Flip the Switch Hackathon"
echo "======================================================================"

if [[ "$1" == "--replay" ]]; then
    echo "▶ Running in REPLAY MODE (Zero-Key Demonstration)..."
    uv run --project core python -m replay.replay_runner
    echo ""
    echo "Starting background FastAPI server for God-Mode UI inspection..."
fi

echo "✓ Syncing Python 3.11 environment with uv..."
uv sync --project core

echo ""
echo "----------------------------------------------------------------------"
echo " 🌐 RELAYOS LIVE INTERFACES:"
echo " • Admin God-Mode:     http://localhost:8000/god-mode"
echo " • Customer Portal:    http://localhost:8000/t/acme"
echo " • Switch Template:    $DIR/switch/relayos.template.yaml"
echo " • API Documentation:  http://localhost:8000/docs"
echo "----------------------------------------------------------------------"
echo ""

echo "🚀 Starting Uvicorn server on http://localhost:8000..."
exec uv run --project core uvicorn core.main:app --host 0.0.0.0 --port 8000 --reload
