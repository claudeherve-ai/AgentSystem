"""
telemetry — lightweight, dependency-free self-observability for AgentSystem.

Provides an in-process tracer that records spans for HTTP requests, orchestrator
routing, agent turns, and tool calls. Spans are redaction-safe by construction
and exposed via the observability API (``/api/v1/observability/...``).

Public surface:
    from telemetry import get_tracer
    async with get_tracer().span("agent.route_task", kind="route", attributes={...}) as span:
        span.set_attribute("agent", name)
"""

from __future__ import annotations

from .span import NoopSpan, Span, sanitize_attributes
from .tracer import Tracer, get_tracer, reset_tracer_for_tests

__all__ = [
    "Span",
    "NoopSpan",
    "sanitize_attributes",
    "Tracer",
    "get_tracer",
    "reset_tracer_for_tests",
]
