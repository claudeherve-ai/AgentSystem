"""AgentSystem — Golden-task evaluation harness (PR3).

A small, dependency-light harness that runs two suites of "golden tasks":

* **offline** — deterministic checks (catalog integrity, router fallback,
  agent registration, guardrails) that need no LLM credentials and no network.
  This is the CI gate and must always pass.
* **online** — LLM-quality checks via the optional `deepeval` package. Each
  online task structurally self-skips when credentials or `deepeval` are
  missing, so the suite degrades gracefully instead of failing.

Public surface::

    from evals import run_suite, EvalReport, EvalResult

The CLI lives in :mod:`evals.run` (``python -m evals.run``).
"""

from evals.harness import (
    EvalReport,
    EvalResult,
    load_tasks,
    run_offline,
    run_online,
    run_suite,
)

__all__ = [
    "EvalReport",
    "EvalResult",
    "load_tasks",
    "run_offline",
    "run_online",
    "run_suite",
]
