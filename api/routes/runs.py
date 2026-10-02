"""AgentSystem — Durable Run Routes (/api/v1/runs).

Additive, versioned surface over the durable run service:

    POST   /api/v1/runs                 Create + execute a run.
    GET    /api/v1/runs                  List runs (filter by session/status).
    GET    /api/v1/runs/{run_id}         Run detail + recent events.
    POST   /api/v1/runs/{run_id}/cancel  Request cancellation.
    GET    /api/v1/runs/{run_id}/events   Resumable SSE event stream.

The SSE stream emits ONLY real, persisted events with monotonic ids and honors
``Last-Event-ID`` (or ``?last_event_id=``) for resumption after a disconnect.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from agentsystem.db.models import Run, RunEvent
from api.context import resolve_context
from api.dependencies import get_run_service

logger = logging.getLogger("agentsystem.api.runs")
router = APIRouter()


class CreateRunRequest(BaseModel):
    message: str = Field(..., description="The task/prompt to execute")
    session_id: Optional[str] = Field(None, description="Continue an existing session")
    preferred_agent: Optional[str] = Field(None, description="Route to a specific agent")
    idempotency_key: Optional[str] = Field(None, description="Idempotent create key")


def _run_dict(run: Run) -> dict[str, Any]:
    return {
        "id": run.id,
        "status": run.status,
        "session_id": run.session_id,
        "workspace_id": run.workspace_id,
        "project_id": run.project_id,
        "input": run.input_text,
        "output": run.output_text,
        "selected_agent": run.selected_agent,
        "route": run.route,
        "error_code": run.error_code,
        "usage": {
            "prompt_tokens": run.prompt_tokens,
            "completion_tokens": run.completion_tokens,
            "latency_ms": run.latency_ms,
            "cost_usd": run.cost_usd,
        },
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "updated_at": run.updated_at.isoformat() if run.updated_at else None,
    }


def _event_dict(event: RunEvent) -> dict[str, Any]:
    return {"id": event.event_id, "type": event.type, "data": event.data}


@router.post("")
async def create_run(request: Request, body: CreateRunRequest):
    """Create and durably execute a run; returns the terminal run state."""
    ctx = await resolve_context(request, session_id=body.session_id)
    service = get_run_service()
    run = await service.create_and_execute(
        ctx,
        input_text=body.message,
        preferred_agent=body.preferred_agent or "",
        idempotency_key=body.idempotency_key or "",
    )
    return _run_dict(run)


@router.get("")
async def list_runs(
    request: Request,
    session_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
):
    ctx = await resolve_context(request)
    service = get_run_service()
    runs = await service.list_runs(
        ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        session_id=session_id,
        status=status,
        limit=max(1, min(limit, 200)),
    )
    return {"runs": [_run_dict(r) for r in runs], "count": len(runs)}


@router.get("/{run_id}")
async def get_run(request: Request, run_id: str):
    ctx = await resolve_context(request)
    service = get_run_service()
    run = await service.get_run(
        ctx.tenant_id, run_id, workspace_id=ctx.workspace_id
    )
    events = await service.list_events(ctx.tenant_id, run_id)
    detail = _run_dict(run)
    detail["events"] = [_event_dict(e) for e in events]
    return detail


@router.post("/{run_id}/cancel")
async def cancel_run(request: Request, run_id: str):
    ctx = await resolve_context(request)
    service = get_run_service()
    run = await service.cancel_run(
        ctx.tenant_id, run_id, workspace_id=ctx.workspace_id
    )
    return _run_dict(run)


@router.get("/{run_id}/events")
async def stream_run_events(
    request: Request, run_id: str, last_event_id: int = 0
):
    """Resumable SSE stream of real run events (honors Last-Event-ID)."""
    ctx = await resolve_context(request)
    service = get_run_service()
    # Scope check up-front so an unknown/foreign run 404s before streaming.
    await service.get_run(
        ctx.tenant_id, run_id, workspace_id=ctx.workspace_id
    )

    header_last = request.headers.get("last-event-id")
    resume_from = last_event_id
    if header_last:
        try:
            resume_from = max(resume_from, int(header_last))
        except (TypeError, ValueError):
            pass

    async def event_source():
        async for event in service.stream_events(
            ctx.tenant_id, run_id, last_event_id=resume_from
        ):
            payload = json.dumps(event["data"], default=str)
            yield (
                f"id: {event['id']}\n"
                f"event: {event['event']}\n"
                f"data: {payload}\n\n"
            )

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


__all__ = ["router"]
