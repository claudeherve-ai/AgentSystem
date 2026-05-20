#!/usr/bin/env bash
# AgentSystem — Unified Entrypoint
# =============================================================================
# Starts the AgentSystem with the appropriate mode based on AGENTSYSTEM_MODE env var.
#
# Modes:
#   dashboard  — Streamlit web dashboard (default, port 8501)
#   api         — FastAPI REST backend (port 8080)
#   all         — Both dashboard + API (dashboard on 8501, API on 8080)
#   cli         — Interactive CLI loop
#
# Usage:
#   AGENTSYSTEM_MODE=dashboard ./start.sh
#   AGENTSYSTEM_MODE=api ./start.sh
#   AGENTSYSTEM_MODE=all ./start.sh
#   AGENTSYSTEM_MODE=cli ./start.sh
# =============================================================================
set -euo pipefail

cd "$(dirname "$0")"
export PYTHONPATH="${PYTHONPATH:-}:$(pwd)"

MODE="${AGENTSYSTEM_MODE:-dashboard}"
PORT_DASHBOARD="${PORT_DASHBOARD:-8501}"
PORT_API="${PORT_API:-8080}"

echo "======================================================"
echo "  AgentSystem — Boil the Ocean"
echo "  Mode: $MODE"
echo "  Python: $(python3 --version)"
echo "======================================================"

case "$MODE" in
    dashboard)
        echo "Starting Streamlit dashboard on port $PORT_DASHBOARD..."
        exec streamlit run dashboard.py \
            --server.port="$PORT_DASHBOARD" \
            --server.address=0.0.0.0 \
            --server.headless=true \
            --browser.serverAddress=0.0.0.0
        ;;

    api)
        echo "Starting FastAPI backend on port $PORT_API..."
        exec python3 -m uvicorn api.main:app \
            --host 0.0.0.0 \
            --port "$PORT_API" \
            --log-level info
        ;;

    all)
        echo "Starting API on port $PORT_API (background)..."
        python3 -m uvicorn api.main:app \
            --host 0.0.0.0 \
            --port "$PORT_API" \
            --log-level warning &
        API_PID=$!

        echo "Starting Dashboard on port $PORT_DASHBOARD..."
        streamlit run dashboard.py \
            --server.port="$PORT_DASHBOARD" \
            --server.address=0.0.0.0 \
            --server.headless=true \
            --browser.serverAddress=0.0.0.0 &
        DASH_PID=$!

        echo "Both services started. API PID=$API_PID, Dashboard PID=$DASH_PID"
        echo "Dashboard: http://0.0.0.0:$PORT_DASHBOARD"
        echo "API:       http://0.0.0.0:$PORT_API/docs"
        wait
        ;;

    cli)
        echo "Starting interactive CLI..."
        exec python3 main.py
        ;;

    *)
        echo "Unknown mode: $MODE"
        echo "Valid modes: dashboard, api, all, cli"
        exit 1
        ;;
esac
