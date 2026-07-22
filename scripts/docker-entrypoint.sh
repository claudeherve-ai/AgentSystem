#!/usr/bin/env bash
# AgentSystem container launcher — runs Streamlit dashboard (8501) and the
# FastAPI backend (8080, real /health /readiness /live probes) side by side.
set -euo pipefail

python -m uvicorn api.main:app --host 0.0.0.0 --port 8080 &
API_PID=$!

streamlit run dashboard.py \
  --server.port=8501 \
  --server.address=0.0.0.0 \
  --server.headless=true \
  --browser.serverAddress=0.0.0.0 &
DASH_PID=$!

# If either process dies, exit non-zero so ACA restarts the replica.
wait -n "$API_PID" "$DASH_PID"
exit $?
