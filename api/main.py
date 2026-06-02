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
from api.routes.chat import router as chat_router
from api.routes.health import router as health_router
from api.middleware.auth import AuthMiddleware
from api.middleware.rate_limit import RateLimitMiddleware

logger = logging.getLogger("agentsystem.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle."""
    # Startup
    logger.info("AgentSystem API starting up...")
    get_orchestrator()  # Pre-load agents
    yield
    # Shutdown
    logger.info("AgentSystem API shutting down...")


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

    # Custom middleware
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(AuthMiddleware)

    # Routes
    app.include_router(health_router, tags=["Health"])
    app.include_router(agents_router, prefix="/api/v1/agents", tags=["Agents"])
    app.include_router(chat_router, prefix="/api/v1/chat", tags=["Chat"])

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
