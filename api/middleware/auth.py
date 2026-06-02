"""
AgentSystem — Auth Middleware

API key-based authentication for the FastAPI layer.
Supports optional OAuth2 bearer tokens (for future Entra ID integration).

Environment variables:
    AGENTSYSTEM_API_KEY  — Required when auth is enabled; clients pass it via X-API-Key
    AGENTSYSTEM_AUTH_ENABLED — Set to 'true'/'false' to enforce API-key auth.
        Defaults to 'true' when AGENTSYSTEM_API_KEY is set, otherwise 'false',
        so configuring a key never silently runs the server unauthenticated.
"""
import os
import logging
import secrets
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger = logging.getLogger("agentsystem.auth")

API_KEY = os.getenv("AGENTSYSTEM_API_KEY", "")
# Default auth ON when a key is configured (so a deployment that sets only the
# key is never left wide open), OFF otherwise (frictionless local dev).
AUTH_ENABLED = os.getenv(
    "AGENTSYSTEM_AUTH_ENABLED", "true" if API_KEY else "false"
).lower() == "true"

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
            logger.error(
                "AGENTSYSTEM_AUTH_ENABLED=true but AGENTSYSTEM_API_KEY is not set — "
                "refusing requests (fail closed)."
            )
            return JSONResponse(
                status_code=503,
                content={"detail": "Authentication is misconfigured on the server."},
            )

        if not secrets.compare_digest(api_key, API_KEY):
            return JSONResponse(
                status_code=403,
                content={"detail": "Invalid API key."},
            )

        return await call_next(request)
