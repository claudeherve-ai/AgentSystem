"""
telemetry.tracer — the in-process tracer.

The tracer owns the current-span ``ContextVar``, fans finished spans out to a
set of isolated exporters, and exposes ``recent``/``stats`` for the
observability API. It is intentionally tiny and dependency-free so it can never
break the request path:

- ``get_tracer()`` is a lazy singleton and NEVER raises.
- When telemetry is disabled the tracer hands out :class:`NoopSpan` objects and
  does no work.
- ``span()`` is an async context manager that always resets the contextvar in a
  ``finally`` and ends the span idempotently, recording exception *type* +
  sanitized summary (never a raw traceback).
- Exporter failures are caught per-exporter and never propagate.
"""

from __future__ import annotations

import contextvars
import logging
import threading
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from config import TelemetryConfig, get_telemetry_config

from .exporters import (
    InMemoryExporter,
    JsonlExporter,
    LangfuseExporter,
    OtlpExporter,
)
from .span import NoopSpan, Span

logger = logging.getLogger("agentsystem.telemetry")

# The currently-active span for the running async context.
_current_span: contextvars.ContextVar[Span | None] = contextvars.ContextVar(
    "agentsystem_current_span", default=None
)

# Cap an exception summary so a span never carries a raw traceback.
_MAX_EXC_SUMMARY = 200


class Tracer:
    """Creates spans, tracks context, and exports finished spans."""

    def __init__(self, config: TelemetryConfig) -> None:
        self._config = config
        self._enabled = config.enabled
        self._capture_content = config.capture_content
        self._memory = InMemoryExporter(max_spans=config.max_spans)
        self._exporters: list[Any] = [self._memory]
        self._lock = threading.Lock()

        if config.jsonl_enabled and config.jsonl_path:
            try:
                self._exporters.append(JsonlExporter(config.jsonl_path))
            except Exception as exc:  # noqa: BLE001 - never fatal
                logger.warning("Could not init JSONL exporter: %s", exc)
        if config.otlp_enabled:
            try:
                self._exporters.append(OtlpExporter(config.otlp_endpoint))
            except Exception as exc:  # noqa: BLE001 - never fatal
                logger.warning("Could not init OTLP exporter: %s", exc)
        if config.langfuse_enabled:
            try:
                self._exporters.append(
                    LangfuseExporter(
                        config.langfuse_public_key,
                        config.langfuse_secret_key,
                        config.langfuse_host,
                    )
                )
            except Exception as exc:  # noqa: BLE001 - never fatal
                logger.warning("Could not init Langfuse exporter: %s", exc)

    # -- introspection used by the observability API ----------------------
    @property
    def enabled(self) -> bool:
        return self._enabled

    def recent(self, limit: int = 100) -> list[dict[str, Any]]:
        return self._memory.recent(limit)

    def stats(self) -> dict[str, Any]:
        data = self._memory.stats()
        data["enabled"] = self._enabled
        data["capture_content"] = self._capture_content
        data["exporters"] = [type(e).__name__ for e in self._exporters]
        return data

    # -- span lifecycle ---------------------------------------------------
    def current_span(self) -> Span | None:
        return _current_span.get()

    def start_span(
        self,
        name: str,
        *,
        kind: str = "internal",
        attributes: dict[str, Any] | None = None,
    ) -> Span:
        """Create (but do not enter) a span parented to the current context."""
        parent = _current_span.get()
        span = Span(
            name=name,
            kind=kind,
            trace_id=parent.trace_id if parent else _new_trace_id(),
            parent_id=parent.span_id if parent else None,
        )
        if attributes:
            for key, value in attributes.items():
                span.set_attribute(key, value, capture_content=self._capture_content)
        return span

    def end_span(self, span: Span) -> None:
        """Finish a span exactly once and export it. Never raises."""
        if isinstance(span, NoopSpan):
            return
        import time

        # Idempotent: a span that already ended is not re-exported.
        if span.end_time is not None:
            return
        span.end_time = time.time()
        if span.status == "running":
            span.status = "ok"
        self._export(span)

    def _export(self, span: Span) -> None:
        for exporter in list(self._exporters):
            try:
                exporter.export(span)
            except Exception as exc:  # noqa: BLE001 - isolate every sink
                logger.debug("Exporter %s failed: %s", type(exporter).__name__, exc)

    @asynccontextmanager
    async def span(
        self,
        name: str,
        *,
        kind: str = "internal",
        attributes: dict[str, Any] | None = None,
    ) -> AsyncIterator[Any]:
        """Async context manager that enters/exits a span safely.

        Yields a :class:`NoopSpan` when telemetry is disabled. Always resets the
        contextvar and ends the span in ``finally``; records exception type +
        sanitized summary on error.
        """
        if not self._enabled:
            yield NoopSpan()
            return

        span = self.start_span(name, kind=kind, attributes=attributes)
        token = _current_span.set(span)
        try:
            yield span
        except BaseException as exc:  # noqa: BLE001 - annotate then re-raise
            span.status = "error"
            span.set_attribute("error.type", type(exc).__name__)
            # The exception *message* can contain user content (prompt
            # fragments, values, secrets). Only record it when content capture
            # is explicitly enabled; the type alone is always safe.
            if self._capture_content:
                summary = str(exc).replace("\n", " ")[:_MAX_EXC_SUMMARY]
                span.set_attribute("error.summary", summary)
            raise
        finally:
            _current_span.reset(token)
            self.end_span(span)


def _new_trace_id() -> str:
    from .span import new_id

    return new_id()


# ---------------------------------------------------------------------------
# Lazy singleton
# ---------------------------------------------------------------------------
_tracer: Tracer | None = None
_tracer_lock = threading.Lock()


class _NoopTracer:
    """Fallback tracer used only if construction somehow fails."""

    enabled = False

    def recent(self, limit: int = 100) -> list[dict[str, Any]]:
        return []

    def stats(self) -> dict[str, Any]:
        return {"enabled": False, "buffered_spans": 0}

    def current_span(self) -> None:
        return None

    @asynccontextmanager
    async def span(self, *_args: Any, **_kwargs: Any) -> AsyncIterator[Any]:
        yield NoopSpan()


def get_tracer() -> Any:
    """Return the process-wide tracer. NEVER raises."""
    global _tracer
    if _tracer is not None:
        return _tracer
    with _tracer_lock:
        if _tracer is None:
            try:
                _tracer = Tracer(get_telemetry_config())
            except Exception as exc:  # noqa: BLE001 - degrade to no-op
                logger.warning("Telemetry init failed, using no-op tracer: %s", exc)
                return _NoopTracer()
    return _tracer


def reset_tracer_for_tests() -> None:
    """Drop the cached tracer so the next ``get_tracer`` rebuilds from env."""
    global _tracer
    with _tracer_lock:
        _tracer = None
