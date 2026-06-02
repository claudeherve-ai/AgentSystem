"""
AgentSystem — Observability Routes

Read-only introspection over recent in-process spans. Useful for debugging agent
runs, tool calls, and request latency without an external backend.

Endpoints (mounted under ``/api/v1/observability``):
    GET /traces?limit=N   Recent finished spans (newest first), capped.
    GET /stats            Aggregate counters (buffered spans, status counts, …).

Gated by ``OBSERVABILITY_API_ENABLED`` (telemetry config ``api_enabled``). When
disabled the endpoints return 404 so the surface is invisible. The router sits
behind ``AuthMiddleware`` like every other ``/api/v1`` route. Spans are already
redaction-safe (see ``telemetry.span.sanitize_attributes``).
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from config import get_telemetry_config
from telemetry import get_tracer

router = APIRouter()

# Absolute ceiling regardless of what the caller asks for.
_HARD_MAX = 500


def _require_enabled() -> None:
    cfg = get_telemetry_config()
    if not cfg.api_enabled:
        raise HTTPException(status_code=404, detail="Observability API is disabled.")


@router.get("/traces")
async def list_traces(
    limit: int = Query(default=100, ge=1, le=_HARD_MAX, description="Max spans to return"),
):
    """Return the most recent finished spans (newest first)."""
    _require_enabled()
    tracer = get_tracer()
    spans = tracer.recent(limit)
    return {"count": len(spans), "limit": limit, "spans": spans}


@router.get("/stats")
async def trace_stats():
    """Return aggregate telemetry counters."""
    _require_enabled()
    tracer = get_tracer()
    return tracer.stats()
