"""apps.worker — durable agent worker.

Two modes, selected by ``DURABLE_MODE``:

* ``dts``   — register the run orchestration/activity with the Azure Durable
  Task Scheduler worker (managed identity) and process scheduled runs. Fails
  closed if the scheduler is unconfigured.
* ``local`` — a deterministic poll loop that claims ``pending`` runs from the
  database and executes them via the durable :class:`~agentsystem.services.RunService`.
  This makes the worker functional and testable without any external service.

Run with:  python -m apps.worker.main
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from sqlalchemy import and_, or_, select  # noqa: E402

from agentsystem.db.models import Run  # noqa: E402
from agentsystem.db.session import init_models, session_scope  # noqa: E402
from agentsystem.settings import get_settings  # noqa: E402

logger = logging.getLogger("agentsystem.worker")


async def _pending_runs(limit: int = 20) -> list[tuple[str, str]]:
    """Return new work and abandoned runs whose execution lease expired."""
    now = datetime.now(timezone.utc)
    async with session_scope() as session:
        result = await session.execute(
            select(Run.tenant_id, Run.id)
            .where(
                or_(
                    and_(
                        Run.status == "pending",
                        Run.cancel_requested.is_(False),
                    ),
                    and_(
                        Run.status == "running",
                        or_(
                            Run.execution_lease_until.is_(None),
                            Run.execution_lease_until <= now,
                        ),
                    ),
                )
            )
            .order_by(Run.created_at.asc())
            .limit(limit)
        )
        return [(row[0], row[1]) for row in result.all()]


async def process_pending_once(run_service=None) -> int:
    """Execute all currently-pending runs once. Returns the count processed.

    Execution is idempotent: the workflow skips runs that are already terminal,
    so overlapping workers cannot double-run a run.
    """
    from api.dependencies import get_run_service

    service = run_service or get_run_service()
    processed = 0
    for tenant_id, run_id in await _pending_runs():
        try:
            run = await service.get_run(tenant_id, run_id)
            from agentsystem.services.run_service import _context_from_run

            await service.execute(_context_from_run(run))
            processed += 1
        except Exception:  # noqa: BLE001 - one bad run must not stop the loop
            logger.exception("Worker failed run %s", run_id)
    return processed


async def poll_loop(run_service=None, interval: float = 1.0) -> None:
    logger.info("Durable worker (local poll mode) started.")
    while True:
        try:
            count = await process_pending_once(run_service)
            if count:
                logger.info("Worker processed %d run(s).", count)
        except Exception as exc:  # noqa: BLE001
            logger.error("Worker loop error: %s", type(exc).__name__)
        await asyncio.sleep(interval)


def _start_dts_worker() -> None:
    """Register + run the Durable Task Scheduler worker (managed identity).

    Fails closed if the scheduler SDK or endpoint is unavailable — production
    must not silently degrade to in-process execution.
    """
    settings = get_settings()
    if not settings.durable_endpoint:
        raise SystemExit(
            "DURABLE_MODE=dts requires DURABLE_TASK_ENDPOINT — refusing to start."
        )
    try:
        from azure.identity import DefaultAzureCredential
        from durabletask.azuremanaged.worker import (  # type: ignore
            DurableTaskSchedulerWorker,
        )
    except ImportError as exc:  # pragma: no cover - optional SDK
        raise SystemExit(
            "Durable Task Scheduler SDK is not installed — cannot start DTS worker."
        ) from exc

    from agentsystem.durable.workflow import (
        execute_run_activity,
        run_orchestration,
    )

    credential = DefaultAzureCredential()
    worker = DurableTaskSchedulerWorker(
        host_address=settings.durable_endpoint,
        secure_channel=not settings.durable_endpoint.startswith("http://"),
        taskhub=settings.durable_taskhub,
        token_credential=credential,
    )
    worker.add_orchestrator(run_orchestration)
    worker.add_activity(execute_run_activity)
    logger.info("Durable Task Scheduler worker starting (taskhub=%s).", settings.durable_taskhub)
    worker.start()
    try:
        import time

        while True:
            time.sleep(3600)
    finally:
        worker.stop()


def main() -> None:
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
    settings = get_settings()

    async def _bootstrap() -> None:
        if settings.is_sqlite:
            await init_models()

    asyncio.run(_bootstrap())

    if settings.durable_is_dts:
        _start_dts_worker()
    else:
        asyncio.run(poll_loop())


if __name__ == "__main__":
    main()
