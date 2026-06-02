"""AgentSystem — Golden-task evaluation harness (PR3).

Runs two suites defined in ``evals/golden_tasks.yaml``:

* **offline** — deterministic checks that need NO credentials and NO network
  (catalog integrity, router resolution matrix, agent registration, guardrails
  config). This is the CI gate and must always pass.
* **online** — LLM-quality checks (DeepEval) that *self-skip* when credentials or
  the optional ``deepeval`` package are missing.

The module is import-safe and runnable directly (``python -m evals.run``) without
credentials. Skips never fail the report; only ``failed`` results do.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

import yaml

# Allow ``python evals/harness.py`` style execution from the repo root.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from config import (  # noqa: E402  (after sys.path shim)
    MissingModelCredentialsError,
    get_guardrails_config,
)
from routing import ModelRouter, load_catalog  # noqa: E402

_DEFAULT_TASKS = Path(__file__).resolve().parent / "golden_tasks.yaml"

PASSED = "passed"
FAILED = "failed"
SKIPPED = "skipped"


@dataclass(frozen=True)
class EvalResult:
    """Outcome of a single golden task."""

    id: str
    kind: str
    status: str  # passed | failed | skipped
    detail: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "id": self.id,
            "kind": self.kind,
            "status": self.status,
            "detail": self.detail,
        }


@dataclass
class EvalReport:
    """Aggregate of all task results in a run."""

    results: list[EvalResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        """True unless at least one task FAILED (skips do not fail the run)."""
        return not any(r.status == FAILED for r in self.results)

    def counts(self) -> dict[str, int]:
        out = {PASSED: 0, FAILED: 0, SKIPPED: 0}
        for r in self.results:
            out[r.status] = out.get(r.status, 0) + 1
        return out

    def to_dict(self) -> dict[str, Any]:
        c = self.counts()
        return {
            "passed": self.passed,
            "total": len(self.results),
            "counts": c,
            "results": [r.to_dict() for r in self.results],
        }


# ── task loading ─────────────────────────────────────────────────────────────


def load_tasks(path: Optional[Path | str] = None) -> dict[str, list[dict[str, Any]]]:
    """Load the golden-task suites from YAML.

    Returns a mapping with ``offline`` and ``online`` lists (each possibly empty).
    """
    target = Path(path) if path else _DEFAULT_TASKS
    data = yaml.safe_load(target.read_text(encoding="utf-8")) or {}
    return {
        "offline": list(data.get("offline") or []),
        "online": list(data.get("online") or []),
    }


# ── offline handlers ─────────────────────────────────────────────────────────


def _result(task: dict[str, Any], status: str, detail: str = "") -> EvalResult:
    return EvalResult(
        id=str(task.get("id", "<unnamed>")),
        kind=str(task.get("kind", "<unknown>")),
        status=status,
        detail=detail,
    )


def _handle_catalog_integrity(task: dict[str, Any]) -> EvalResult:
    catalog = load_catalog()
    default = catalog.default_profile
    if not default or catalog.get(default) is None:
        return _result(task, FAILED, f"default_profile '{default}' not defined")
    min_profiles = int(task.get("expect_min_profiles", 1))
    if len(catalog.profiles) < min_profiles:
        return _result(
            task, FAILED, f"{len(catalog.profiles)} profiles < {min_profiles}"
        )
    expect_default = task.get("expect_default")
    if expect_default and default != expect_default:
        return _result(task, FAILED, f"default '{default}' != '{expect_default}'")
    return _result(
        task, PASSED, f"{len(catalog.profiles)} profiles, default '{default}'"
    )


def _handle_router_resolution(task: dict[str, Any]) -> EvalResult:
    available = set(task.get("available") or [])
    router = ModelRouter(load_catalog(), availability=lambda p: p in available)
    profile = task.get("profile")

    if task.get("expect_unresolvable"):
        try:
            resolved = router.resolve(profile)
        except MissingModelCredentialsError:
            return _result(task, PASSED, "unresolvable as expected")
        return _result(
            task, FAILED, f"expected unresolvable, got '{resolved.provider}'"
        )

    try:
        resolved = router.resolve(profile)
    except MissingModelCredentialsError as exc:
        return _result(task, FAILED, f"unexpectedly unresolvable: {exc}")

    expect_provider = task.get("expect_provider")
    if expect_provider and resolved.provider != expect_provider:
        return _result(
            task,
            FAILED,
            f"provider '{resolved.provider}' != '{expect_provider}'",
        )
    if "expect_substituted" in task and bool(resolved.substituted) != bool(
        task["expect_substituted"]
    ):
        return _result(
            task,
            FAILED,
            f"substituted={resolved.substituted}, expected {task['expect_substituted']}",
        )
    return _result(
        task,
        PASSED,
        f"{resolved.provider}/{resolved.model} substituted={resolved.substituted}",
    )


def _handle_agent_registration(task: dict[str, Any]) -> EvalResult:
    from agents.factory import build_orchestrator

    orchestrator = build_orchestrator()
    status = orchestrator.status()
    count = int(status.get("agent_count", 0))
    expect_min = int(task.get("expect_min_agents", 1))
    if count < expect_min:
        return _result(task, FAILED, f"{count} agents < {expect_min}")
    return _result(task, PASSED, f"{count} agents registered")


def _handle_guardrails_load(task: dict[str, Any]) -> EvalResult:
    cfg = get_guardrails_config()
    if not cfg:
        return _result(task, FAILED, "guardrails config empty")
    return _result(task, PASSED, f"{len(cfg)} guardrail keys")


_OFFLINE_HANDLERS: dict[str, Callable[[dict[str, Any]], EvalResult]] = {
    "catalog_integrity": _handle_catalog_integrity,
    "router_resolution": _handle_router_resolution,
    "agent_registration": _handle_agent_registration,
    "guardrails_load": _handle_guardrails_load,
}


# ── online handlers ──────────────────────────────────────────────────────────


def _handle_llm_relevancy(task: dict[str, Any]) -> EvalResult:
    # Imported lazily so the offline path never touches deepeval/metrics.
    from evals.metrics import MetricSkipped, answer_relevancy

    try:
        outcome = answer_relevancy(
            profile=str(task.get("profile", "balanced")),
            input_text=str(task.get("input", "")),
            threshold=float(task.get("threshold", 0.5)),
        )
    except MetricSkipped as skip:
        return _result(task, SKIPPED, skip.reason)

    status = PASSED if outcome.get("passed") else FAILED
    return _result(
        task,
        status,
        f"score={outcome.get('score')} threshold={outcome.get('threshold')}",
    )


_ONLINE_HANDLERS: dict[str, Callable[[dict[str, Any]], EvalResult]] = {
    "llm_relevancy": _handle_llm_relevancy,
}


# ── runners ──────────────────────────────────────────────────────────────────


def _run_one(
    task: dict[str, Any],
    handlers: dict[str, Callable[[dict[str, Any]], EvalResult]],
) -> EvalResult:
    kind = str(task.get("kind", ""))
    handler = handlers.get(kind)
    if handler is None:
        return _result(task, FAILED, f"unknown kind '{kind}'")
    try:
        return handler(task)
    except Exception as exc:  # noqa: BLE001 - one bad task must not abort the run
        return _result(task, FAILED, f"{type(exc).__name__}: {exc}")


def run_offline(
    tasks: Optional[dict[str, list[dict[str, Any]]]] = None,
) -> EvalReport:
    suites = tasks if tasks is not None else load_tasks()
    results = [_run_one(t, _OFFLINE_HANDLERS) for t in suites.get("offline", [])]
    return EvalReport(results=results)


def run_online(
    tasks: Optional[dict[str, list[dict[str, Any]]]] = None,
) -> EvalReport:
    suites = tasks if tasks is not None else load_tasks()
    results = [_run_one(t, _ONLINE_HANDLERS) for t in suites.get("online", [])]
    return EvalReport(results=results)


def run_suite(
    *,
    offline_only: bool = True,
    tasks: Optional[dict[str, list[dict[str, Any]]]] = None,
) -> EvalReport:
    """Run the offline suite, plus the online suite when ``offline_only`` is False."""
    suites = tasks if tasks is not None else load_tasks()
    results = [_run_one(t, _OFFLINE_HANDLERS) for t in suites.get("offline", [])]
    if not offline_only:
        results += [_run_one(t, _ONLINE_HANDLERS) for t in suites.get("online", [])]
    return EvalReport(results=results)
