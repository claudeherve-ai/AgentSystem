"""
AgentSystem — FastAPI Backend
=============================
Enterprise-grade API layer for the multi-agent orchestrator.
Provides REST endpoints for chat, agent management, health, and metrics.

Production entrypoint: uvicorn api.main:app --host 0.0.0.0 --port 8080
"""
from __future__ import annotations

import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.dependencies import get_orchestrator
from api.routes.agents import router as agents_router
from api.routes.approvals import router as approvals_router
from api.routes.chat import router as chat_router
from api.routes.health import router as health_router
from api.routes.models import router as models_router
from api.routes.observability import router as observability_router
from api.routes.runs import router as runs_router
from api.routes.voice import router as voice_router
from api.routes.workflows import router as workflows_router
from api.middleware.context import (
    IdentityMiddleware,
    PrincipalRateLimitMiddleware,
    RequestContextMiddleware,
    SharedRateLimitMiddleware,
)
from api.middleware.telemetry import TelemetryMiddleware

logger = logging.getLogger("agentsystem.api")

# ── Azure Monitor / Application Insights ─────────────────────────────────────
# Activated when APPLICATIONINSIGHTS_CONNECTION_STRING is set (container app
# wires it from ACA secrets). Auto-instruments FastAPI/requests/httpx and
# forwards traces, metrics, and logs to App Insights. Best-effort: any failure
# must never block the API.
try:
    if os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING"):
        from azure.monitor.opentelemetry import configure_azure_monitor

        configure_azure_monitor(
            logger_name="agentsystem",
            instrumentation_options={
                "fastapi": {"enabled": True},
                "requests": {"enabled": True},
                "urllib": {"enabled": True},
                "urllib3": {"enabled": True},
            },
        )
        logger.info("Azure Monitor (App Insights) instrumentation enabled")
except Exception as _ai_exc:  # noqa: BLE001
    logger.debug("Azure Monitor instrumentation skipped: %s", _ai_exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle."""
    # Startup
    logger.info("AgentSystem API starting up...")
    # Bootstrap the local SQLite schema for dev/test; PostgreSQL schema is owned
    # by Alembic migrations and must NOT be auto-created in production.
    try:
        from agentsystem.settings import get_settings
        from agentsystem.db.session import init_models

        settings = get_settings()
        if settings.is_production and not settings.database_config_ready:
            raise RuntimeError(
                "Production requires an explicit PostgreSQL DATABASE_URL."
            )
        if settings.is_sqlite:
            await init_models()
            logger.info("SQLite schema initialized for local development.")
    except Exception as exc:  # noqa: BLE001 - never block startup on bootstrap
        logger.warning("Database bootstrap skipped: %s", type(exc).__name__)
    get_orchestrator()  # Pre-load agents
    # Best-effort cleanup of any sandbox containers leaked by a previous run.
    try:
        from tools.docker_sandbox import reap_stale_sandboxes

        reaped = await reap_stale_sandboxes()
        if reaped:
            logger.info("Reaped %d stale sandbox container(s) at startup.", reaped)
    except Exception as exc:  # noqa: BLE001 — never block startup
        logger.debug("Sandbox reaper skipped: %s", exc)
    yield
    # Shutdown
    logger.info("AgentSystem API shutting down...")
    try:
        from agentsystem.services.rate_limit import get_rate_limiter

        await get_rate_limiter().aclose()
    except Exception:  # noqa: BLE001
        pass


# ── App Factory ─────────────────────────────────────────────────────────────
def create_app() -> FastAPI:
    app = FastAPI(
        title="AgentSystem API",
        description="Multi-Agent Enterprise Orchestrator — REST API",
        version="2.0.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # CORS — allow dashboard and enterprise clients.
    # Browsers reject `allow_credentials=True` together with a wildcard origin,
    # so only enable credentials when an explicit origin allow-list is provided.
    cors_origins = [
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS", "*").split(",")
        if origin.strip()
    ]
    allow_credentials = "*" not in cors_origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Custom middleware. Starlette runs the LAST-added middleware OUTERMOST.
    # Order (outer -> inner): RequestContext -> Telemetry -> SharedRateLimit ->
    # Identity -> PrincipalRateLimit -> route.
    #  - RequestContext is outermost: it stamps request_id and renders EVERY
    #    error as the single structured envelope (never a raw provider trace).
    #  - SharedRateLimit sits OUTSIDE Identity so unauthenticated floods are
    #    throttled before the (more expensive) identity validation runs.
    app.add_middleware(PrincipalRateLimitMiddleware)
    app.add_middleware(IdentityMiddleware)
    app.add_middleware(SharedRateLimitMiddleware)
    app.add_middleware(TelemetryMiddleware)
    app.add_middleware(RequestContextMiddleware)

    # Routes
    app.include_router(health_router, tags=["Health"])
    app.include_router(agents_router, prefix="/api/v1/agents", tags=["Agents"])
    app.include_router(chat_router, prefix="/api/v1/chat", tags=["Chat"])
    app.include_router(runs_router, prefix="/api/v1/runs", tags=["Runs"])
    app.include_router(models_router, prefix="/api/v1/models", tags=["Models"])
    app.include_router(
        approvals_router, prefix="/api/v1/approvals", tags=["Approvals"]
    )
    app.include_router(
        observability_router,
        prefix="/api/v1/observability",
        tags=["Observability"],
    )
    app.include_router(
        workflows_router, prefix="/api/v1/workflows", tags=["Workflows"]
    )
    app.include_router(voice_router, prefix="/api/v1/voice", tags=["Voice"])

    # Root redirect
    @app.get("/")
    async def root():
        orch = get_orchestrator()
        return {
            "name": "AgentSystem API",
            "version": "2.0.0",
            "agents": len(orch.agent_names),
            "agent_list": orch.agent_names,
            "docs": "/docs",
            "health": "/health",
        }

    return app


app = create_app()

# ── CLI entrypoint ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("API_PORT", "8080"))
    uvicorn.run("api.main:app", host="0.0.0.0", port=port, reload=False)
