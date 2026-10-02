"""AgentSystem — Chat Routes (durable-run compatibility facade).

The historical ``/chat`` surface is preserved, but every request now flows
through the durable :class:`agentsystem.services.RunService`: a run is created
and executed, real events are persisted, and the response carries **real** agent
attribution (which specialists the coordinator actually invoked). ``session_id``
is honored so a client can continue an existing conversation.

Streaming emits the run's real persisted events — it never fabricates
token-by-token chunks of an already-finished answer.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field
from starlette.responses import JSONResponse, StreamingResponse

from agentsystem.context import new_id
from api.context import resolve_context
from api.dependencies import get_run_service

logger = logging.getLogger("agentsystem.api.chat")
router = APIRouter()


class ChatRequest(BaseModel):
    message: str = Field(..., description="The user's message to route to agents")
    session_id: Optional[str] = Field(None, description="Session ID for conversation continuity")
    preferred_agent: Optional[str] = Field(None, description="Route to a specific agent directly")
    stream: bool = Field(False, description="Stream real run events (SSE)")


class ChatResponse(BaseModel):
    response: str
    session_id: str
    run_id: str
    agents_used: list[str] = []
    selected_agent: Optional[str] = None


class ChatAcceptedResponse(BaseModel):
    """Asynchronous durable-run submission accepted by DTS."""

    run_id: str
    session_id: str
    status: str
    status_url: str
    events_url: str


@router.post("/", response_model=ChatResponse | ChatAcceptedResponse)
async def chat(request: Request, body: ChatRequest):
    """Route a message through the durable run service and return the answer.

    Honors ``session_id`` for continuity and returns real agent attribution.
    """
    ctx = await resolve_context(request, session_id=body.session_id)
    service = get_run_service()
    if service.execution_mode == "dts":
        run = await service.create_run(
            ctx,
            input_text=body.message,
            preferred_agent=body.preferred_agent or "",
        )
        await service.execute(ctx.with_run(run.id))
        accepted = ChatAcceptedResponse(
            run_id=run.id,
            session_id=run.session_id,
            status=run.status,
            status_url=f"/api/v1/runs/{run.id}",
            events_url=f"/api/v1/runs/{run.id}/events",
        )
        return JSONResponse(status_code=202, content=accepted.model_dump())

    run = await service.create_and_execute(
        ctx,
        input_text=body.message,
        preferred_agent=body.preferred_agent or "",
    )
    return ChatResponse(
        response=run.output_text or "",
        session_id=run.session_id,
        run_id=run.id,
        agents_used=[run.selected_agent] if run.selected_agent else [],
        selected_agent=run.selected_agent,
    )


@router.post("/stream")
async def chat_stream(request: Request, body: ChatRequest):
    """Stream the run's REAL persisted events as SSE (no fake chunking)."""
    ctx = await resolve_context(request, session_id=body.session_id)
    service = get_run_service()
    run = await service.create_run(
        ctx,
        input_text=body.message,
        preferred_agent=body.preferred_agent or "",
    )
    exec_ctx = ctx.with_run(run.id)

    async def event_source():
        # Kick execution concurrently so events stream as they are persisted.
        task = asyncio.create_task(service.execute(exec_ctx))
        try:
            async for event in service.stream_events(ctx.tenant_id, run.id):
                payload = json.dumps(event["data"], default=str)
                yield (
                    f"id: {event['id']}\n"
                    f"event: {event['event']}\n"
                    f"data: {payload}\n\n"
                )
        finally:
            try:
                await task
            except Exception:  # noqa: BLE001 - terminal run.failed event already emitted
                pass

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/session/new")
async def new_session(request: Request):
    """Start a fresh conversation session id (durable memory preserved)."""
    session_id = new_id("sess")
    return {
        "session_id": session_id,
        "message": "New session started. Durable memory preserved.",
    }


@router.get("/session/{session_id}")
async def get_session(request: Request, session_id: str):
    """Return recent runs for a session (scoped to the caller's tenant)."""
    ctx = await resolve_context(request)
    service = get_run_service()
    runs = await service.list_runs(
        ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        session_id=session_id,
        limit=20,
    )
    return {
        "session_id": session_id,
        "runs": [{"id": r.id, "status": r.status} for r in runs],
        "count": len(runs),
    }


__all__ = ["router"]
