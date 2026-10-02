"""Request correlation, structured errors, identity, and shared rate limiting.

Middleware ordering (outer → inner), configured in ``api.main``:

    RequestContext (correlation + error envelope)
      → Telemetry
        → SharedRateLimit
          → Identity
            → PrincipalRateLimit
              → route

* :class:`RequestContextMiddleware` assigns a ``request_id`` and converts ANY
  unhandled error into the single structured envelope (never a raw provider
  exception or stack trace).
* :class:`SharedRateLimitMiddleware` is a coarse pre-authentication source
   shield. Its deliberately larger bucket limits abusive ingress sources without
   treating a trusted proxy address as the caller's identity.
* :class:`IdentityMiddleware` extracts + validates the caller and attaches the
  :class:`~agentsystem.context.Principal` to ``request.state.principal``.
* :class:`PrincipalRateLimitMiddleware` applies the product quota to the
   verified tenant/user identity. A limiter outage fails closed (503).
"""

from __future__ import annotations

import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from agentsystem.context import new_id
from agentsystem.errors import (
    AgentSystemError,
    DependencyUnavailableError,
    RateLimitedError,
    UnauthorizedError,
    error_envelope,
)
from agentsystem.services.identity import IdentityExtractor
from agentsystem.services.rate_limit import get_rate_limiter
from agentsystem.settings import get_settings

logger = logging.getLogger("agentsystem.api.mw")

# A source may legitimately multiplex many users through Front Door, Nginx, or
# Container Apps ingress. Keep this only as a coarse abuse shield; the verified
# principal bucket below is the actual caller quota.
SOURCE_LIMIT_MULTIPLIER = 20

# Paths that never require auth / rate limiting.
PUBLIC_PREFIXES = (
    "/health",
    "/readiness",
    "/live",
    "/docs",
    "/redoc",
    "/openapi.json",
)


def _is_public(path: str) -> bool:
    if path == "/":
        return True
    return any(path == p or path.startswith(p) for p in PUBLIC_PREFIXES)


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", None) or new_id("req")


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Assign a correlation id and render all errors as a safe envelope."""

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("x-request-id") or new_id("req")
        request.state.request_id = request_id
        try:
            response = await call_next(request)
        except AgentSystemError as exc:
            envelope = error_envelope(exc, request_id)
            logger.info(
                "Handled error %s (%s) request_id=%s",
                exc.code, type(exc).__name__, request_id,
            )
            response = JSONResponse(
                status_code=envelope.status_code, content=envelope.to_dict()
            )
        except Exception as exc:  # noqa: BLE001 - never leak raw exceptions
            envelope = error_envelope(exc, request_id)
            logger.error(
                "Unhandled %s request_id=%s", type(exc).__name__, request_id
            )
            response = JSONResponse(
                status_code=500, content=envelope.to_dict()
            )
        response.headers["X-Request-ID"] = request_id
        return response


class SharedRateLimitMiddleware(BaseHTTPMiddleware):
    """Coarse distributed pre-authentication source throttling."""

    async def dispatch(self, request: Request, call_next):
        settings = get_settings()
        if not settings.rate_limit_enabled or _is_public(request.url.path):
            return await call_next(request)
        client_ip = request.client.host if request.client else "unknown"
        try:
            decision = await get_rate_limiter().allow(
                f"source:{client_ip}",
                max_requests=settings.rate_limit_requests
                * SOURCE_LIMIT_MULTIPLIER,
            )
        except DependencyUnavailableError as exc:
            # Limiter outage → fail closed (503), never allow the flood through.
            envelope = error_envelope(exc, _request_id(request))
            return JSONResponse(
                status_code=envelope.status_code, content=envelope.to_dict()
            )
        if not decision.allowed:
            envelope = error_envelope(
                RateLimitedError(details={"retry_after": decision.retry_after}),
                _request_id(request),
            )
            return JSONResponse(
                status_code=429,
                content=envelope.to_dict(),
                headers={"Retry-After": str(decision.retry_after)},
            )
        return await call_next(request)


class IdentityMiddleware(BaseHTTPMiddleware):
    """Extract + validate the caller and attach the principal to request state."""

    async def dispatch(self, request: Request, call_next):
        if _is_public(request.url.path):
            return await call_next(request)
        try:
            principal = await IdentityExtractor().extract(request.headers)
        except UnauthorizedError as exc:
            envelope = error_envelope(exc, _request_id(request))
            return JSONResponse(
                status_code=401, content=envelope.to_dict()
            )
        request.state.principal = principal
        return await call_next(request)


class PrincipalRateLimitMiddleware(BaseHTTPMiddleware):
    """Enforce the product quota against the verified tenant/user identity."""

    async def dispatch(self, request: Request, call_next):
        settings = get_settings()
        if not settings.rate_limit_enabled or _is_public(request.url.path):
            return await call_next(request)

        principal = request.state.principal
        key = f"principal:{principal.tenant_id}:{principal.user_id}"
        try:
            decision = await get_rate_limiter().allow(key)
        except DependencyUnavailableError as exc:
            envelope = error_envelope(exc, _request_id(request))
            return JSONResponse(
                status_code=envelope.status_code, content=envelope.to_dict()
            )
        if not decision.allowed:
            envelope = error_envelope(
                RateLimitedError(details={"retry_after": decision.retry_after}),
                _request_id(request),
            )
            return JSONResponse(
                status_code=429,
                content=envelope.to_dict(),
                headers={"Retry-After": str(decision.retry_after)},
            )
        return await call_next(request)


__all__ = [
    "IdentityMiddleware",
    "PrincipalRateLimitMiddleware",
    "RequestContextMiddleware",
    "SharedRateLimitMiddleware",
]
