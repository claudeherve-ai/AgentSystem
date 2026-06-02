"""
AgentSystem — Durable Workflow Routes (PR5, OPTIONAL / FAIL-CLOSED).

REST surface over the optional MS Agent Framework Workflows engine
(:mod:`workflows`). The built-in ``demo-v1`` pipeline is a pure, deterministic
4-stage chain that persists one checkpoint per superstep, so a run can be
listed and resumed with byte-identical output — no model or credentials needed.

Endpoints (mounted under ``/api/v1/workflows``):
    GET  /status                         Engine availability + config snapshot.
    POST /runs                           Start a durable run.
    GET  /runs/{run_id}/checkpoints      List persisted checkpoints for a run.
    POST /runs/{run_id}/resume           Resume a run from a checkpoint id.

The engine raises a small error hierarchy that maps cleanly onto HTTP status:
    WorkflowUnavailableError       -> 503  (SDK missing or feature disabled)
    WorkflowInputError             -> 400  (bad id / oversized input)
    WorkflowNotFoundError          -> 404  (unknown run / no checkpoints)
    WorkflowCheckpointNotFoundError-> 404  (checkpoint id not in run)
    WorkflowResumeError            -> 409  (framework refused the resume)

Sits behind ``AuthMiddleware`` like every other ``/api/v1`` route and degrades
to a clean status code rather than a raw 500.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from workflows import (
    WorkflowCheckpointNotFoundError,
    WorkflowInputError,
    WorkflowNotFoundError,
    WorkflowResumeError,
    WorkflowUnavailableError,
    get_workflow_engine,
)

router = APIRouter()


class RunRequest(BaseModel):
    """Body for starting a run."""

    input: str = ""
    run_id: str | None = None


class ResumeRequest(BaseModel):
    """Body for resuming a run from a persisted checkpoint."""

    checkpoint_id: str


@router.get("/status")
async def workflow_status():
    """Return engine availability + a non-secret config snapshot."""
    return get_workflow_engine().status()


@router.post("/runs")
async def start_run(request: RunRequest):
    """Start a durable workflow run over the built-in demo pipeline."""
    engine = get_workflow_engine()
    try:
        record = await engine.run(request.input, run_id=request.run_id)
    except WorkflowUnavailableError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except WorkflowInputError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return record.to_dict()


@router.get("/runs/{run_id}/checkpoints")
async def list_run_checkpoints(run_id: str):
    """List persisted checkpoints for a prior run, oldest first."""
    engine = get_workflow_engine()
    try:
        infos = await engine.list_checkpoints(run_id)
    except WorkflowUnavailableError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except WorkflowInputError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except WorkflowNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"run_id": run_id, "checkpoints": [i.to_dict() for i in infos], "count": len(infos)}


@router.post("/runs/{run_id}/resume")
async def resume_run(run_id: str, request: ResumeRequest):
    """Resume a prior run from a persisted checkpoint id."""
    engine = get_workflow_engine()
    try:
        record = await engine.resume(run_id, request.checkpoint_id)
    except WorkflowUnavailableError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except WorkflowInputError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except (WorkflowNotFoundError, WorkflowCheckpointNotFoundError) as e:
        raise HTTPException(status_code=404, detail=str(e))
    except WorkflowResumeError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return record.to_dict()
