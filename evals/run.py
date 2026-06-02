"""AgentSystem — Eval CLI (PR3).

Run the golden-task suites and exit non-zero on any FAILED task (skips do not
fail). Offline-only by default so it is safe in CI without credentials.

Examples::

    python -m evals.run                 # offline gate
    python -m evals.run --online        # also run LLM-quality checks
    python -m evals.run --json          # machine-readable report
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional, Sequence

# Allow direct execution from the repo root.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from evals.harness import load_tasks, run_suite  # noqa: E402


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="evals.run",
        description="Run AgentSystem golden-task evaluations.",
    )
    parser.add_argument(
        "--online",
        action="store_true",
        help="Also run the online LLM-quality suite (self-skips without creds).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit a machine-readable JSON report instead of text.",
    )
    parser.add_argument(
        "--tasks",
        default=None,
        help="Path to an alternate golden_tasks.yaml.",
    )
    args = parser.parse_args(argv)

    tasks = load_tasks(args.tasks) if args.tasks else None
    report = run_suite(offline_only=not args.online, tasks=tasks)

    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        for r in report.results:
            print(f"[{r.status.upper():>7}] {r.id:<36} {r.detail}")
        c = report.counts()
        print(
            f"\n{c['passed']} passed, {c['failed']} failed, "
            f"{c['skipped']} skipped"
        )

    return 0 if report.passed else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
