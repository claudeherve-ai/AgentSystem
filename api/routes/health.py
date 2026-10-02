"""AgentSystem — Health Routes.

Truthful liveness / readiness / startup with real dependency status.

* ``/health/live``    — process liveness (always 200 if the process is up).
* ``/health/ready``   — readiness: database, Redis (when enabled), Durable Task
  (when selected), Blob (when enabled), and cached model config. Returns 503
  when a required dependency is unhealthy so ACA/K8s can pull the replica.
* ``/health/startup`` — cold-start gate (database + model config).

Compatibility aliases ``/health``, ``/readiness``, ``/live`` are preserved.
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from agentsystem.services.health import (
    build_readiness_report,
    build_startup_report,
)
from agentsystem.settings import get_settings
from api.dependencies import get_orchestrator

router = APIRouter()


def _liveness_body() -> dict:
    settings = get_settings()
    return {
        "alive": True,
        "status": "alive",
        "version": settings.app_version,
        "revision": settings.revision,
        "environment": settings.environment,
    }


@router.get("/health/live")
async def health_live():
    """Process liveness — no dependency checks."""
    return _liveness_body()


@router.get("/health/ready")
async def health_ready():
    """Readiness — reflects the ACTUAL state of every required dependency."""
    report = await build_readiness_report()
    status_code = 200 if report.ready else 503
    return JSONResponse(status_code=status_code, content=report.to_dict())


@router.get("/health/startup")
async def health_startup():
    """Startup gate — database reachable and model configured."""
    report = await build_startup_report()
    status_code = 200 if report.ready else 503
    return JSONResponse(status_code=status_code, content=report.to_dict())


# ── Compatibility aliases (existing clients/tests) ──────────────────────────
@router.get("/health", include_in_schema=True)
async def health_check():
    """Legacy combined health endpoint (kept for backward compatibility)."""
    live = _liveness_body()
    try:
        orch = get_orchestrator()
        live["agents_registered"] = len(orch.agent_names)
        live["agents"] = orch.agent_names
    except Exception:  # noqa: BLE001 - liveness must not depend on agents
        live["agents_registered"] = 0
    live["status"] = "healthy"
    return live


@router.get("/readiness")
async def readiness():
    """Legacy readiness alias → truthful dependency report."""
    report = await build_readiness_report()
    status_code = 200 if report.ready else 503
    return JSONResponse(status_code=status_code, content=report.to_dict())


@router.get("/live")
async def liveness():
    """Legacy liveness alias."""
    return {"alive": True}


__all__ = ["router"]
