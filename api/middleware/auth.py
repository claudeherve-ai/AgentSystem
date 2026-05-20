"""
AgentSystem — Auth Middleware

API key-based authentication for the FastAPI layer.
Supports optional OAuth2 bearer tokens (for future Entra ID integration).

Environment variables:
    AGENTSYSTEM_API_KEY  — Required for production; set to 'dev' for local dev
    AGENTSYSTEM_AUTH_ENABLED — Set to 'false' to disable (dev only)
"""
import os
import logging
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger = logging.getLogger("agentsystem.auth")

AUTH_ENABLED = os.getenv("AGENTSYSTEM_AUTH_ENABLED", "true").lower() != "false"
API_KEY = os.getenv("AGENTSYSTEM_API_KEY", "")

# Public paths that don't require authentication
PUBLIC_PATHS = {
    "/health",
    "/readiness",
    "/live",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/api/v1/health",
    "/",  # Root returns status
}


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Skip auth for public paths
        if request.url.path in PUBLIC_PATHS or request.url.path.startswith("/health"):
            return await call_next(request)

        # Skip auth if disabled (dev mode)
        if not AUTH_ENABLED:
            return await call_next(request)

        # API key auth
        api_key = request.headers.get("X-API-Key") or request.headers.get("Authorization", "").replace("Bearer ", "")
        if not api_key:
            return JSONResponse(
                status_code=401,
                content={"detail": "Missing API key. Pass X-API-Key header."},
            )

        if not API_KEY:
            logger.warning("AGENTSYSTEM_API_KEY not set — auth is effectively disabled")
            return await call_next(request)

        if api_key != API_KEY:
            return JSONResponse(
                status_code=403,
                content={"detail": "Invalid API key."},
            )

        return await call_next(request)
