"""
telemetry.exporters — pluggable span sinks.

Every exporter is best-effort and fully isolated: an exporter raising must never
disrupt the request path or other exporters. Network exporters (OTLP, Langfuse)
are *fire-and-forget* — they spawn a background thread and never block the
caller. The in-memory exporter backs the observability API; the JSONL exporter
provides a cheap durable trail.
"""

from __future__ import annotations

import json
import logging
import threading
from collections import deque
from pathlib import Path
from typing import Any, Protocol

from .span import Span

logger = logging.getLogger("agentsystem.telemetry")


class SpanExporter(Protocol):
    """Anything that can receive finished spans."""

    def export(self, span: Span) -> None:  # pragma: no cover - protocol
        ...


class InMemoryExporter:
    """Thread-safe ring buffer of recent spans backing the observability API."""

    def __init__(self, max_spans: int = 500) -> None:
        self._buf: deque[dict[str, Any]] = deque(maxlen=max(1, int(max_spans)))
        self._lock = threading.Lock()
        self._counts: dict[str, int] = {}

    def export(self, span: Span) -> None:
        record = span.to_dict()
        with self._lock:
            self._buf.append(record)
            self._counts[span.status] = self._counts.get(span.status, 0) + 1

    def recent(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._lock:
            items = list(self._buf)
        if limit and limit > 0:
            items = items[-limit:]
        # Newest first for API ergonomics.
        return list(reversed(items))

    def stats(self) -> dict[str, Any]:
        with self._lock:
            items = list(self._buf)
            counts = dict(self._counts)
        durations = [
            i["duration_ms"] for i in items if i.get("duration_ms") is not None
        ]
        kinds: dict[str, int] = {}
        for i in items:
            kinds[i["kind"]] = kinds.get(i["kind"], 0) + 1
        avg = round(sum(durations) / len(durations), 3) if durations else 0.0
        return {
            "buffered_spans": len(items),
            "capacity": self._buf.maxlen,
            "lifetime_status_counts": counts,
            "buffered_kind_counts": kinds,
            "avg_duration_ms": avg,
            "max_duration_ms": max(durations) if durations else 0.0,
        }


class JsonlExporter:
    """Append each finished span as one JSON line. Guarded + best-effort."""

    def __init__(self, path: str) -> None:
        self._path = Path(path)
        self._lock = threading.Lock()
        self._broken = False
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:  # pragma: no cover - filesystem edge
            logger.warning("JSONL telemetry disabled (mkdir failed): %s", exc)
            self._broken = True

    def export(self, span: Span) -> None:
        if self._broken:
            return
        line = json.dumps(span.to_dict(), default=str, ensure_ascii=False)
        try:
            with self._lock:
                with self._path.open("a", encoding="utf-8") as fh:
                    fh.write(line + "\n")
        except OSError as exc:  # pragma: no cover - filesystem edge
            logger.warning("JSONL telemetry write failed (disabling): %s", exc)
            self._broken = True


class OtlpExporter:
    """Fire-and-forget OTLP/HTTP JSON exporter (optional, dependency-free).

    Posts a minimal OTLP-shaped payload using ``urllib`` on a daemon thread so
    the request path is never blocked. If the collector is down the failure is
    swallowed with a debug log.
    """

    def __init__(self, endpoint: str) -> None:
        self._endpoint = endpoint.rstrip("/")
        # OTLP/HTTP traces are conventionally posted to /v1/traces.
        if not self._endpoint.endswith("/v1/traces"):
            self._endpoint = self._endpoint + "/v1/traces"

    def export(self, span: Span) -> None:
        thread = threading.Thread(
            target=self._post, args=(span.to_dict(),), daemon=True
        )
        thread.start()

    def _post(self, record: dict[str, Any]) -> None:
        import urllib.error
        import urllib.request

        payload = json.dumps(
            {"agentsystem.span": record}, default=str
        ).encode("utf-8")
        req = urllib.request.Request(
            self._endpoint,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=2.0):  # nosec B310 - configured endpoint
                pass
        except (urllib.error.URLError, OSError, ValueError) as exc:
            logger.debug("OTLP export failed: %s", exc)


class LangfuseExporter:
    """Fire-and-forget Langfuse exporter using the official SDK if installed.

    Import is lazy so the SDK is a pure optional extra. If unavailable or
    misconfigured the exporter disables itself silently (debug log only).
    """

    def __init__(self, public_key: str, secret_key: str, host: str) -> None:
        self._broken = False
        self._client = None
        try:
            from langfuse import Langfuse  # type: ignore

            self._client = Langfuse(
                public_key=public_key, secret_key=secret_key, host=host
            )
        except Exception as exc:  # noqa: BLE001 - optional dep, never fatal
            logger.debug("Langfuse exporter disabled: %s", exc)
            self._broken = True

    def export(self, span: Span) -> None:
        if self._broken or self._client is None:
            return
        thread = threading.Thread(target=self._send, args=(span,), daemon=True)
        thread.start()

    def _send(self, span: Span) -> None:
        try:
            self._client.trace(  # type: ignore[attr-defined]
                id=span.trace_id,
                name=span.name,
                metadata={"kind": span.kind, **span.attributes},
            )
        except Exception as exc:  # noqa: BLE001 - optional dep, never fatal
            logger.debug("Langfuse export failed: %s", exc)
