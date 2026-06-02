"""
Tests for the durable workflow feature (PR5):
  * workflows/engine.py        — MS Agent Framework Workflows engine.
  * workflows/__init__.py       — process-wide ``get_workflow_engine`` singleton.
  * api/routes/workflows.py     — REST surface (status / runs / checkpoints / resume).

Everything runs with NO LLM credentials, NO network, and NO external service. The
built-in ``demo-v1`` pipeline is a pure, deterministic 4-stage chain, so a run can
be checkpointed and resumed to a byte-identical output without any model. Every
engine instance is injected with a ``WorkflowConfig`` whose ``checkpoint_dir``
points inside the test's ``tmp_path``, so the repo's ``memory/`` is never touched
and tests cannot collide.
"""

import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import WorkflowConfig
from workflows import (
    WorkflowCheckpointNotFoundError,
    WorkflowEngine,
    WorkflowInputError,
    WorkflowNotFoundError,
    WorkflowUnavailableError,
)

try:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
except Exception:  # pragma: no cover - httpx missing
    FastAPI = None  # type: ignore[assignment]
    TestClient = None  # type: ignore[assignment]


# The fully-rendered output of the demo pipeline for a given input.
def _expected(input_text: str) -> str:
    return f"final::synthesize<plan[intake({input_text.strip()})]>"


# ── fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture()
def tmp_cfg(tmp_path: Path) -> WorkflowConfig:
    """An enabled config whose checkpoints live inside the test's temp dir."""
    return WorkflowConfig(checkpoint_dir=str(tmp_path / "wf"))


@pytest.fixture()
def engine(tmp_cfg: WorkflowConfig) -> WorkflowEngine:
    """An engine pinned to a throwaway checkpoint dir."""
    return WorkflowEngine(config=tmp_cfg)


# ── engine: introspection ────────────────────────────────────────────────────


def test_status_snapshot_is_always_safe(engine: WorkflowEngine, tmp_cfg):
    snap = engine.status()
    assert snap["pipeline_id"] == "demo-v1"
    assert snap["enabled"] is True  # SDK present + enabled config
    assert snap["checkpoint_dir"] == tmp_cfg.checkpoint_dir
    assert snap["steps"] == ["intake", "plan", "synthesize", "finalize"]
    print("✅ status snapshot ok")


def test_disabled_config_reports_disabled(tmp_path: Path):
    cfg = WorkflowConfig(enabled=False, checkpoint_dir=str(tmp_path))
    eng = WorkflowEngine(config=cfg)
    assert eng.enabled() is False
    assert eng.status()["enabled"] is False
    print("✅ disabled config => disabled")


# ── engine: run / determinism ────────────────────────────────────────────────


def test_run_is_deterministic_and_checkpointed(engine: WorkflowEngine):
    rec = asyncio.run(engine.run("Hello", run_id="run-det"))
    assert rec.status == "completed"
    assert rec.output == _expected("Hello")
    assert rec.superstep_count > 0
    assert len(rec.checkpoints) == rec.superstep_count
    # Re-running the same input on a fresh engine yields identical output.
    again = asyncio.run(engine.run("Hello", run_id="run-det-2"))
    assert again.output == rec.output
    print("✅ run deterministic + checkpointed")


def test_run_strips_input(engine: WorkflowEngine):
    rec = asyncio.run(engine.run("  spaced  ", run_id="run-strip"))
    assert rec.output == _expected("spaced")
    print("✅ input stripped")


# ── engine: checkpoint round-trip + resume ───────────────────────────────────


def test_list_checkpoints_matches_run_record(engine: WorkflowEngine):
    rec = asyncio.run(engine.run("payload", run_id="run-list"))
    infos = asyncio.run(engine.list_checkpoints("run-list"))
    assert [i.to_dict() for i in infos] == rec.checkpoints
    # Iterations are 0-indexed and strictly increasing.
    iters = [i.iteration for i in infos]
    assert iters == sorted(iters)
    print("✅ list_checkpoints matches record")


def test_resume_reproduces_byte_identical_output(engine: WorkflowEngine):
    rec = asyncio.run(engine.run("resume-me", run_id="run-res"))
    first_cp = rec.checkpoints[0]["checkpoint_id"]
    resumed = asyncio.run(engine.resume("run-res", first_cp))
    assert resumed.status == "resumed"
    assert resumed.output == rec.output
    print("✅ resume byte-identical")


# ── engine: run isolation ────────────────────────────────────────────────────


def test_runs_are_isolated_per_run_id(engine: WorkflowEngine, tmp_cfg):
    asyncio.run(engine.run("a", run_id="iso-a"))
    asyncio.run(engine.run("b", run_id="iso-b"))
    root = Path(tmp_cfg.checkpoint_dir)
    assert (root / "iso-a").is_dir()
    assert (root / "iso-b").is_dir()
    # Each run only sees its own checkpoints.
    a = asyncio.run(engine.list_checkpoints("iso-a"))
    b = asyncio.run(engine.list_checkpoints("iso-b"))
    assert {c.checkpoint_id for c in a}.isdisjoint({c.checkpoint_id for c in b})
    print("✅ runs isolated")


# ── engine: validation + preflight (fail-closed) ─────────────────────────────


def test_empty_input_rejected(engine: WorkflowEngine):
    with pytest.raises(WorkflowInputError):
        asyncio.run(engine.run("   ", run_id="bad"))
    print("✅ empty input => 400")


def test_oversized_input_rejected(tmp_path: Path):
    cfg = WorkflowConfig(checkpoint_dir=str(tmp_path), max_input_chars=8)
    eng = WorkflowEngine(config=cfg)
    with pytest.raises(WorkflowInputError):
        asyncio.run(eng.run("this is far too long", run_id="big"))
    print("✅ oversized input => 400")


def test_invalid_run_id_rejected(engine: WorkflowEngine):
    with pytest.raises(WorkflowInputError):
        asyncio.run(engine.run("ok", run_id="bad id with spaces"))
    print("✅ invalid run_id => 400")


def test_list_unknown_run_404(engine: WorkflowEngine):
    with pytest.raises(WorkflowNotFoundError):
        asyncio.run(engine.list_checkpoints("never-ran"))
    print("✅ unknown run list => 404")


def test_resume_unknown_run_404(engine: WorkflowEngine):
    with pytest.raises(WorkflowNotFoundError):
        asyncio.run(engine.resume("never-ran", "cp-1"))
    print("✅ resume unknown run => 404")


def test_resume_unknown_checkpoint_404(engine: WorkflowEngine):
    asyncio.run(engine.run("x", run_id="run-cpx"))
    with pytest.raises(WorkflowCheckpointNotFoundError):
        asyncio.run(engine.resume("run-cpx", "cp-does-not-exist"))
    print("✅ resume unknown checkpoint => 404")


def test_disabled_engine_blocks_run(tmp_path: Path):
    cfg = WorkflowConfig(enabled=False, checkpoint_dir=str(tmp_path))
    eng = WorkflowEngine(config=cfg)
    with pytest.raises(WorkflowUnavailableError):
        asyncio.run(eng.run("x", run_id="nope"))
    print("✅ disabled engine => 503")


# ── api: REST surface ────────────────────────────────────────────────────────


pytestmark_api = pytest.mark.skipif(
    TestClient is None, reason="fastapi TestClient (httpx) not installed"
)


def _make_app(engine_obj: WorkflowEngine, monkeypatch) -> "FastAPI":
    """Mount the workflows router with the engine singleton pinned to ``engine_obj``."""
    from api.routes import workflows as wf_routes

    monkeypatch.setattr(wf_routes, "get_workflow_engine", lambda: engine_obj)
    app = FastAPI()
    app.include_router(wf_routes.router, prefix="/api/v1/workflows")
    return app


@pytestmark_api
def test_api_status_ok(engine: WorkflowEngine, monkeypatch):
    client = TestClient(_make_app(engine, monkeypatch))
    resp = client.get("/api/v1/workflows/status")
    assert resp.status_code == 200
    assert resp.json()["pipeline_id"] == "demo-v1"
    print("✅ GET /status -> 200")


@pytestmark_api
def test_api_run_list_resume_happy_path(engine: WorkflowEngine, monkeypatch):
    client = TestClient(_make_app(engine, monkeypatch))

    run = client.post("/api/v1/workflows/runs", json={"input": "hi", "run_id": "api-1"})
    assert run.status_code == 200
    body = run.json()
    assert body["output"] == _expected("hi")
    assert body["superstep_count"] > 0

    cps = client.get("/api/v1/workflows/runs/api-1/checkpoints")
    assert cps.status_code == 200
    assert cps.json()["count"] == body["superstep_count"]

    first_cp = body["checkpoints"][0]["checkpoint_id"]
    resumed = client.post(
        "/api/v1/workflows/runs/api-1/resume", json={"checkpoint_id": first_cp}
    )
    assert resumed.status_code == 200
    assert resumed.json()["output"] == body["output"]
    print("✅ run -> list -> resume happy path")


@pytestmark_api
def test_api_empty_input_400(engine: WorkflowEngine, monkeypatch):
    client = TestClient(_make_app(engine, monkeypatch))
    resp = client.post("/api/v1/workflows/runs", json={"input": "   "})
    assert resp.status_code == 400
    print("✅ POST empty input -> 400")


@pytestmark_api
def test_api_list_unknown_run_404(engine: WorkflowEngine, monkeypatch):
    client = TestClient(_make_app(engine, monkeypatch))
    resp = client.get("/api/v1/workflows/runs/ghost/checkpoints")
    assert resp.status_code == 404
    print("✅ GET unknown run -> 404")


@pytestmark_api
def test_api_disabled_run_503(tmp_path: Path, monkeypatch):
    cfg = WorkflowConfig(enabled=False, checkpoint_dir=str(tmp_path))
    eng = WorkflowEngine(config=cfg)
    client = TestClient(_make_app(eng, monkeypatch))
    resp = client.post("/api/v1/workflows/runs", json={"input": "hi"})
    assert resp.status_code == 503
    print("✅ disabled POST /runs -> 503")
