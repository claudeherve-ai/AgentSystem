"""
AgentSystem — Telemetry Middleware

Creates one root span per HTTP request and records method, path, status code,
and duration. The span's ``trace_id`` is stored on ``request.state.trace_id`` so
downstream handlers can correlate work with the request.

Notes
-----
* ``contextvars`` set inside ``dispatch`` BEFORE ``call_next`` propagate *down*
  into the handler but changes made *inside* the handler do not propagate back
  up. We therefore set the request-span contextvar here so tool/agent spans
  created during the request become children of the request span when they run
  in the same task. If propagation is broken by a sub-app or task boundary,
  child spans simply become separate roots — still captured, just not nested.
* Never raises. Telemetry must not break request handling.
"""
from __future__ import annotations

import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from telemetry import get_tracer

logger = logging.getLogger("agentsystem.telemetry")

# Paths that should not generate spans (noise / liveness chatter).
_SKIP_PATHS = {"/health", "/readiness", "/live", "/openapi.json", "/favicon.ico"}


class TelemetryMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path in _SKIP_PATHS or path.startswith("/health"):
            return await call_next(request)

        tracer = get_tracer()
        try:
            cm = tracer.span(
                "http.request",
                kind="request",
                attributes={"http.method": request.method, "http.path": path},
            )
        except Exception:  # noqa: BLE001 — tracer must never break requests
            return await call_next(request)

        async with cm as span:
            try:
                request.state.trace_id = getattr(span, "trace_id", None)
            except Exception:  # noqa: BLE001
                pass
            response = await call_next(request)
            try:
                span.set_attribute("http.status_code", response.status_code)
                if response.status_code >= 500:
                    span.set_status("error")
            except Exception:  # noqa: BLE001
                pass
            return response
