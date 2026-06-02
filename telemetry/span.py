"""
telemetry.span — span data model + attribute sanitization.

A ``Span`` is a single timed unit of work (an HTTP request, an orchestrator
route, an agent turn, a tool call). Spans form a tree via ``parent_id`` and
share a ``trace_id`` for the whole request.

Security note: spans are designed to be safe to persist and expose over the
observability API. ``sanitize_attributes`` enforces a redaction allowlist —
sensitive-looking keys are dropped, free-form content is omitted unless content
capture is explicitly enabled, and every value is length-capped. Callers should
still prefer to pass *derived* metadata (lengths, counts, hashes, booleans, ids)
rather than raw prompts/responses.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any

# Hard caps so a single span can never balloon memory or leak large blobs.
MAX_ATTR_STR_LEN = 512
MAX_ATTRS = 64
MAX_EVENTS = 64

# Substrings that mark a key as sensitive; such values are always redacted.
_SENSITIVE_KEY_MARKERS = (
    "key",
    "secret",
    "token",
    "password",
    "passwd",
    "authorization",
    "auth_header",
    "credential",
    "cookie",
    "session_token",
)

# Keys treated as free-form "content"; omitted unless content capture is on.
_CONTENT_KEYS = {
    "prompt",
    "response",
    "input",
    "output",
    "task",
    "code",
    "message",
    "content",
    "text",
    "query",
    "answer",
}


def new_id() -> str:
    """Short, collision-resistant id for spans/traces."""
    return uuid.uuid4().hex


def _is_sensitive_key(key: str) -> bool:
    low = key.lower()
    return any(marker in low for marker in _SENSITIVE_KEY_MARKERS)


def _is_content_key(key: str) -> bool:
    low = key.lower()
    if low in _CONTENT_KEYS:
        return True
    return low.startswith("content.")


def _sanitize_value(value: Any) -> Any:
    """Coerce a value to a safe, length-bounded scalar."""
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        if len(value) > MAX_ATTR_STR_LEN:
            return value[:MAX_ATTR_STR_LEN] + f"...[+{len(value) - MAX_ATTR_STR_LEN}]"
        return value
    # Anything else: stringify defensively and cap.
    text = repr(value)
    if len(text) > MAX_ATTR_STR_LEN:
        text = text[:MAX_ATTR_STR_LEN] + "...[truncated]"
    return text


def sanitize_attributes(
    attributes: dict[str, Any] | None, *, capture_content: bool
) -> dict[str, Any]:
    """Apply the redaction allowlist to a dict of attributes.

    - Sensitive keys -> ``"[redacted]"``.
    - Content keys -> ``"[omitted len=N]"`` unless ``capture_content`` is True.
    - Every value coerced to a length-capped scalar.
    - Total attribute count capped at :data:`MAX_ATTRS`.
    """
    out: dict[str, Any] = {}
    if not attributes:
        return out
    for key, value in attributes.items():
        if len(out) >= MAX_ATTRS:
            break
        skey = str(key)[:MAX_ATTR_STR_LEN]
        if _is_sensitive_key(skey):
            out[skey] = "[redacted]"
            continue
        if _is_content_key(skey) and not capture_content:
            if isinstance(value, str):
                out[skey] = f"[omitted len={len(value)}]"
            elif value is None:
                out[skey] = None
            else:
                out[skey] = "[omitted]"
            continue
        out[skey] = _sanitize_value(value)
    return out


@dataclass
class Span:
    """A single timed unit of work within a trace."""

    name: str
    kind: str = "internal"
    span_id: str = field(default_factory=new_id)
    trace_id: str = field(default_factory=new_id)
    parent_id: str | None = None
    start_time: float = field(default_factory=time.time)
    end_time: float | None = None
    status: str = "running"  # running | ok | error
    attributes: dict[str, Any] = field(default_factory=dict)
    events: list[dict[str, Any]] = field(default_factory=list)

    @property
    def duration_ms(self) -> float | None:
        if self.end_time is None:
            return None
        return round((self.end_time - self.start_time) * 1000.0, 3)

    def set_attribute(self, key: str, value: Any, *, capture_content: bool = False) -> None:
        """Add one sanitized attribute (no-op once span is full)."""
        if len(self.attributes) >= MAX_ATTRS:
            return
        merged = sanitize_attributes({key: value}, capture_content=capture_content)
        self.attributes.update(merged)

    def set_status(self, status: str) -> None:
        """Set span status (``running`` | ``ok`` | ``error``)."""
        if status in ("running", "ok", "error"):
            self.status = status

    def add_event(
        self,
        name: str,
        attributes: dict[str, Any] | None = None,
        *,
        capture_content: bool = False,
    ) -> None:
        if len(self.events) >= MAX_EVENTS:
            return
        self.events.append(
            {
                "name": str(name)[:MAX_ATTR_STR_LEN],
                "ts": time.time(),
                "attributes": sanitize_attributes(
                    attributes, capture_content=capture_content
                ),
            }
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "span_id": self.span_id,
            "trace_id": self.trace_id,
            "parent_id": self.parent_id,
            "name": self.name,
            "kind": self.kind,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_ms": self.duration_ms,
            "status": self.status,
            "attributes": dict(self.attributes),
            "events": list(self.events),
        }


class NoopSpan:
    """A do-nothing span returned when telemetry is disabled."""

    __slots__ = ("attributes",)

    def __init__(self) -> None:
        self.attributes: dict[str, Any] = {}

    def set_attribute(self, *_args: Any, **_kwargs: Any) -> None:  # noqa: D401
        return None

    def set_status(self, *_args: Any, **_kwargs: Any) -> None:
        return None

    def add_event(self, *_args: Any, **_kwargs: Any) -> None:
        return None
