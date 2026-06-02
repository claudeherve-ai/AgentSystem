"""
Tests for the dependency-free self-observability layer (telemetry/).

Covers attribute sanitization, the Span / NoopSpan data models, and the
in-process Tracer (context-manager lifecycle, error annotation, recent/stats,
and the disabled-tracer no-op path). No network, no Docker, no LLM creds.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from telemetry import NoopSpan, Span, get_tracer, reset_tracer_for_tests, sanitize_attributes
from telemetry.span import MAX_ATTR_STR_LEN, MAX_ATTRS


# ─── Attribute sanitization ──────────────────────────────────────────────────
def test_sanitize_redacts_sensitive_keys():
    out = sanitize_attributes(
        {"api_key": "sk-live-xyz", "authorization": "Bearer abc", "password": "hunter2"},
        capture_content=False,
    )
    assert out["api_key"] == "[redacted]"
    assert out["authorization"] == "[redacted]"
    assert out["password"] == "[redacted]"
    print("✅ Sensitive keys redacted")


def test_sanitize_omits_content_unless_captured():
    attrs = {"prompt": "the quick brown fox", "agent": "EmailAgent"}
    omitted = sanitize_attributes(attrs, capture_content=False)
    assert omitted["prompt"] == "[omitted len=19]"
    assert omitted["agent"] == "EmailAgent"  # non-content passes through

    captured = sanitize_attributes(attrs, capture_content=True)
    assert captured["prompt"] == "the quick brown fox"
    print("✅ Content omitted unless capture enabled")


def test_sanitize_caps_long_values_and_count():
    big = "x" * (MAX_ATTR_STR_LEN + 50)
    out = sanitize_attributes({"note": big}, capture_content=False)
    assert len(out["note"]) <= MAX_ATTR_STR_LEN + 20  # cap + suffix marker
    assert out["note"].endswith("]")

    many = {f"k{i}": i for i in range(MAX_ATTRS + 25)}
    capped = sanitize_attributes(many, capture_content=False)
    assert len(capped) <= MAX_ATTRS
    print("✅ Long values + attribute count capped")


# ─── Span model ──────────────────────────────────────────────────────────────
def test_span_status_and_duration():
    span = Span(name="unit.span", kind="internal")
    assert span.status == "running"
    assert span.duration_ms is None  # not ended yet

    span.set_status("ok")
    assert span.status == "ok"
    span.set_status("bogus")  # invalid -> ignored
    assert span.status == "ok"

    span.end_time = span.start_time + 0.01
    assert span.duration_ms is not None and span.duration_ms >= 0.0

    d = span.to_dict()
    for key in ("span_id", "trace_id", "name", "kind", "status", "attributes", "events"):
        assert key in d
    print("✅ Span status/duration/to_dict OK")


def test_noop_span_is_inert():
    span = NoopSpan()
    # None of these should raise or record anything.
    span.set_attribute("k", "v")
    span.set_status("error")
    span.add_event("evt", {"a": 1})
    assert span.attributes == {}
    print("✅ NoopSpan inert")


# ─── Tracer lifecycle ────────────────────────────────────────────────────────
def test_tracer_records_span_and_stats(monkeypatch):
    monkeypatch.delenv("TELEMETRY_ENABLED", raising=False)
    monkeypatch.setenv("OBSERVABILITY_API_ENABLED", "true")
    reset_tracer_for_tests()
    tracer = get_tracer()
    assert tracer.enabled is True

    async def _emit():
        async with tracer.span("agent.route_task", kind="route", attributes={"agent": "X"}) as span:
            span.set_attribute("count", 3)

    asyncio.run(_emit())

    recent = tracer.recent(10)
    assert any(s["name"] == "agent.route_task" for s in recent)
    finished = next(s for s in recent if s["name"] == "agent.route_task")
    assert finished["status"] == "ok"
    assert finished["attributes"].get("agent") == "X"

    stats = tracer.stats()
    assert stats["enabled"] is True
    assert stats["buffered_spans"] >= 1
    reset_tracer_for_tests()
    print("✅ Tracer records spans + stats")


def test_tracer_annotates_errors(monkeypatch):
    # With content capture ON, the exception summary is recorded.
    monkeypatch.delenv("TELEMETRY_ENABLED", raising=False)
    monkeypatch.setenv("TELEMETRY_CAPTURE_CONTENT", "true")
    reset_tracer_for_tests()
    tracer = get_tracer()

    async def _boom():
        async with tracer.span("tool.run", kind="tool"):
            raise ValueError("kaboom")

    try:
        asyncio.run(_boom())
    except ValueError:
        pass  # exception must propagate

    recent = tracer.recent(10)
    failed = next(s for s in recent if s["name"] == "tool.run")
    assert failed["status"] == "error"
    assert failed["attributes"].get("error.type") == "ValueError"
    assert "kaboom" in failed["attributes"].get("error.summary", "")
    reset_tracer_for_tests()
    print("✅ Tracer annotates errors with type + summary")


def test_tracer_redacts_error_summary_by_default(monkeypatch):
    # With content capture OFF (the default), the exception *type* is recorded
    # but the message — which may contain user content/secrets — is NOT.
    monkeypatch.delenv("TELEMETRY_ENABLED", raising=False)
    monkeypatch.delenv("TELEMETRY_CAPTURE_CONTENT", raising=False)
    reset_tracer_for_tests()
    tracer = get_tracer()

    async def _boom():
        async with tracer.span("tool.run", kind="tool"):
            raise ValueError("super-secret-token-abc123")

    try:
        asyncio.run(_boom())
    except ValueError:
        pass

    recent = tracer.recent(10)
    failed = next(s for s in recent if s["name"] == "tool.run")
    assert failed["status"] == "error"
    assert failed["attributes"].get("error.type") == "ValueError"
    assert "error.summary" not in failed["attributes"]
    reset_tracer_for_tests()
    print("✅ Tracer redacts error summary when content capture is off")


def test_tracer_disabled_yields_noop(monkeypatch):
    monkeypatch.setenv("TELEMETRY_ENABLED", "false")
    reset_tracer_for_tests()
    tracer = get_tracer()
    assert tracer.enabled is False

    async def _emit():
        async with tracer.span("ignored", kind="internal") as span:
            assert isinstance(span, NoopSpan)

    asyncio.run(_emit())
    assert tracer.recent(10) == []
    reset_tracer_for_tests()
    print("✅ Disabled tracer yields NoopSpan + records nothing")
