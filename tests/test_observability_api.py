"""
Tests for the observability HTTP surface (api/routes/observability.py).

Uses a minimal FastAPI app that mounts only the observability router so the
suite stays fast and avoids booting the full orchestrator. Auth is off by
default in the test environment (no AGENTSYSTEM_API_KEY set).
"""

import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI

try:
    from fastapi.testclient import TestClient
except Exception:  # pragma: no cover - httpx missing
    TestClient = None  # type: ignore[assignment]

from api.routes.observability import router as observability_router
from telemetry import get_tracer, reset_tracer_for_tests

pytestmark = pytest.mark.skipif(
    TestClient is None, reason="fastapi TestClient (httpx) not installed"
)


def _make_app() -> FastAPI:
    app = FastAPI()
    app.include_router(observability_router, prefix="/api/v1/observability")
    return app


def test_stats_endpoint_enabled(monkeypatch):
    monkeypatch.delenv("OBSERVABILITY_API_ENABLED", raising=False)
    monkeypatch.delenv("TELEMETRY_ENABLED", raising=False)
    reset_tracer_for_tests()
    client = TestClient(_make_app())
    resp = client.get("/api/v1/observability/stats")
    assert resp.status_code == 200
    body = resp.json()
    assert "enabled" in body
    assert "buffered_spans" in body
    reset_tracer_for_tests()
    print("✅ /stats returns 200 with telemetry counters")


def test_traces_endpoint_returns_emitted_span(monkeypatch):
    monkeypatch.delenv("OBSERVABILITY_API_ENABLED", raising=False)
    monkeypatch.delenv("TELEMETRY_ENABLED", raising=False)
    reset_tracer_for_tests()
    tracer = get_tracer()

    async def _emit():
        async with tracer.span("test.api.span", kind="internal", attributes={"k": "v"}):
            pass

    asyncio.run(_emit())

    client = TestClient(_make_app())
    resp = client.get("/api/v1/observability/traces?limit=10")
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] >= 1
    assert any(s["name"] == "test.api.span" for s in body["spans"])
    reset_tracer_for_tests()
    print("✅ /traces returns recently emitted spans")


def test_traces_limit_is_validated(monkeypatch):
    monkeypatch.delenv("OBSERVABILITY_API_ENABLED", raising=False)
    reset_tracer_for_tests()
    client = TestClient(_make_app())
    # Above the hard ceiling (500) -> 422 validation error.
    resp = client.get("/api/v1/observability/traces?limit=9999")
    assert resp.status_code == 422
    reset_tracer_for_tests()
    print("✅ /traces rejects out-of-range limit")


def test_endpoints_404_when_disabled(monkeypatch):
    monkeypatch.setenv("OBSERVABILITY_API_ENABLED", "false")
    reset_tracer_for_tests()
    client = TestClient(_make_app())
    assert client.get("/api/v1/observability/stats").status_code == 404
    assert client.get("/api/v1/observability/traces").status_code == 404
    reset_tracer_for_tests()
    print("✅ Endpoints return 404 when observability API disabled")
