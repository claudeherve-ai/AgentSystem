"""
Tests for the golden-task eval harness (PR3): evals/harness.py and evals/run.py.

The offline suite is the CI gate: it must pass with NO credentials and NO
network, and without the optional ``deepeval`` package installed. The online
suite must *structurally self-skip* (never fail) under the same conditions.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evals import (
    EvalReport,
    EvalResult,
    load_tasks,
    run_offline,
    run_online,
    run_suite,
)


# ── task definitions ─────────────────────────────────────────────────────────


def test_golden_tasks_load_with_both_suites():
    suites = load_tasks()
    assert isinstance(suites["offline"], list) and suites["offline"]
    assert isinstance(suites["online"], list)
    # Every task must declare an id and a kind.
    for task in suites["offline"] + suites["online"]:
        assert task.get("id"), f"task missing id: {task}"
        assert task.get("kind"), f"task missing kind: {task}"
    print(f"✅ loaded {len(suites['offline'])} offline / {len(suites['online'])} online tasks")


# ── offline suite (CI gate) ──────────────────────────────────────────────────


def test_offline_suite_all_pass_without_credentials(monkeypatch):
    # Strip any creds that might leak in from the environment.
    monkeypatch.delenv("AZURE_OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    report = run_offline()
    assert isinstance(report, EvalReport)
    counts = report.counts()
    assert report.passed is True
    assert counts["failed"] == 0
    assert counts["passed"] >= 1
    # Offline tasks never skip.
    assert counts["skipped"] == 0
    print(f"✅ offline suite green: {counts}")


def test_offline_report_serializes():
    report = run_offline()
    payload = report.to_dict()
    assert payload["passed"] is True
    assert payload["total"] == len(report.results)
    assert isinstance(payload["results"], list)
    assert all({"id", "kind", "status", "detail"} <= set(r) for r in payload["results"])
    print("✅ EvalReport.to_dict() is well-formed JSON-able output")


# ── online suite (must self-skip, never fail, without creds/deepeval) ─────────


def test_online_suite_skips_without_credentials(monkeypatch):
    monkeypatch.delenv("AZURE_OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    report = run_online()
    counts = report.counts()
    # The run must not FAIL — online tasks structurally skip.
    assert report.passed is True
    assert counts["failed"] == 0
    assert counts["skipped"] >= 1
    print(f"✅ online suite self-skips without creds: {counts}")


def test_run_suite_offline_only_matches_run_offline():
    combined = run_suite(offline_only=True)
    offline = run_offline()
    assert len(combined.results) == len(offline.results)
    assert combined.passed is True
    print("✅ run_suite(offline_only=True) mirrors run_offline()")


def test_run_suite_with_online_appends_online_results(monkeypatch):
    monkeypatch.delenv("AZURE_OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    offline = run_offline()
    full = run_suite(offline_only=False)
    assert len(full.results) > len(offline.results)
    # Still green: online additions skip rather than fail.
    assert full.passed is True
    print("✅ run_suite(offline_only=False) appends self-skipping online results")


# ── unknown kinds fail loudly (defensive) ────────────────────────────────────


def test_unknown_offline_kind_fails_the_run():
    tasks = {"offline": [{"id": "bogus", "kind": "no_such_kind"}], "online": []}
    report = run_offline(tasks)
    assert report.passed is False
    assert report.counts()["failed"] == 1
    assert "unknown kind" in report.results[0].detail
    print("✅ unknown task kinds fail the run with a clear detail")


# ── CLI entry point ──────────────────────────────────────────────────────────


def test_run_cli_main_offline_returns_zero(monkeypatch):
    monkeypatch.delenv("AZURE_OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from evals.run import main

    assert main([]) == 0  # offline-only, exit 0
    print("✅ `python -m evals.run` (offline) exits 0")


def test_run_cli_main_online_returns_zero_when_skipping(monkeypatch):
    monkeypatch.delenv("AZURE_OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from evals.run import main

    # Online tasks skip (no creds) -> still exit 0 because skips don't fail.
    assert main(["--online"]) == 0
    print("✅ `python -m evals.run --online` exits 0 when online tasks skip")


def test_run_cli_main_json_outputs_valid_json(monkeypatch, capsys):
    import json

    monkeypatch.delenv("AZURE_OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from evals.run import main

    rc = main(["--json"])
    captured = capsys.readouterr()
    parsed = json.loads(captured.out)
    assert rc == 0
    assert parsed["passed"] is True
    assert "results" in parsed
    print("✅ `python -m evals.run --json` emits valid JSON")
