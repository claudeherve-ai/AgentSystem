"""Durable execution: local deterministic executor + Durable Task adapter.

The run *workflow* (plan → execute → review, with cancellation/retry/approval
hooks) is injected as a coroutine ``workflow(tenant_id, run_id)`` that persists
its progress as durable ``run_events`` in PostgreSQL/SQLite — there are NO local
filesystem checkpoints, so a run survives API/worker restarts and can be resumed
by re-invoking the workflow (each phase is resume-safe).

Two executors implement :class:`DurableExecutor`:

* :class:`LocalDurableExecutor` — awaits the workflow inline. Deterministic;
  used for dev, tests, and the synchronous ``/chat`` compatibility path.
* :class:`DurableTaskExecutor` — schedules the workflow through the Azure Durable
  Task Scheduler (managed identity). Selecting DTS without an endpoint raises so
  production startup/readiness fails closed.
"""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Awaitable, Callable, Optional

from agentsystem.errors import DependencyUnavailableError
from agentsystem.settings import Settings, get_settings

logger = logging.getLogger("agentsystem.durable")

# A workflow is: async (tenant_id, run_id) -> None. It owns its own DB session.
WorkflowFn = Callable[[str, str], Awaitable[None]]


class DurableExecutor(ABC):
    """Dispatches a run workflow to a durable backend."""

    mode: str = "abstract"

    @abstractmethod
    async def execute(self, tenant_id: str, run_id: str, workflow: WorkflowFn) -> None:
        """Run (or schedule) the workflow to completion for ``run_id``."""

    @abstractmethod
    async def health(self) -> bool:
        ...


class LocalDurableExecutor(DurableExecutor):
    """Awaits the workflow inline. Deterministic; the source of truth for tests."""

    mode = "local"

    async def execute(self, tenant_id: str, run_id: str, workflow: WorkflowFn) -> None:
        await workflow(tenant_id, run_id)

    async def health(self) -> bool:
        return True


class DurableTaskExecutor(DurableExecutor):
    """Azure Durable Task Scheduler adapter (managed identity).

    The adapter validates configuration eagerly so a misconfigured production
    deployment fails closed. Scheduling submits the run to the task hub; the
    worker process (``apps/worker``) picks it up and executes the same workflow.
    When the ``durabletask`` SDK is unavailable the adapter still fails closed
    rather than silently running work in-process.
    """

    mode = "dts"

    def __init__(self, endpoint: str, taskhub: str) -> None:
        if not endpoint:
            raise DependencyUnavailableError(
                "DURABLE_MODE=dts requires DURABLE_TASK_ENDPOINT"
            )
        self._endpoint = endpoint
        self._taskhub = taskhub
        self._client = None

    def _build_client(self):
        if self._client is not None:
            return self._client
        try:
            from azure.identity import DefaultAzureCredential
            from durabletask.azuremanaged.client import (  # type: ignore
                DurableTaskSchedulerClient,
            )
        except ImportError as exc:  # pragma: no cover - optional SDK
            raise DependencyUnavailableError(
                "Durable Task Scheduler SDK is not installed"
            ) from exc
        credential = DefaultAzureCredential()
        self._client = DurableTaskSchedulerClient(
            host_address=self._endpoint,
            secure_channel=not self._endpoint.startswith("http://"),
            taskhub=self._taskhub,
            token_credential=credential,
        )
        return self._client

    async def execute(self, tenant_id: str, run_id: str, workflow: WorkflowFn) -> None:
        # Scheduling is delegated to the DTS SDK; the worker runs the workflow.
        from agentsystem.durable.workflow import run_orchestration

        client = self._build_client()
        await asyncio.to_thread(
            client.schedule_new_orchestration,
            run_orchestration,
            input={"tenant_id": tenant_id, "run_id": run_id},
            instance_id=run_id,
        )

    async def health(self) -> bool:
        try:
            client = self._build_client()
            await asyncio.wait_for(
                asyncio.to_thread(
                    client.get_orchestration_state,
                    "__agentsystem_health_probe__",
                ),
                timeout=10,
            )
            return True
        except (DependencyUnavailableError, TimeoutError):
            return False
        except Exception as exc:  # noqa: BLE001 - health probe must not raise
            logger.warning("Durable Task health check failed: %s", type(exc).__name__)
            return False


_executor: Optional[DurableExecutor] = None


def build_durable_executor(settings: Optional[Settings] = None) -> DurableExecutor:
    """Construct the configured durable executor.

    ``DURABLE_MODE=dts`` requires a scheduler endpoint; absent it, construction
    raises so production fails closed instead of silently running locally.
    """
    settings = settings or get_settings()
    if settings.durable_is_dts:
        return DurableTaskExecutor(settings.durable_endpoint, settings.durable_taskhub)
    if settings.is_production:
        logger.warning(
            "DURABLE_MODE=local in production — runs execute in-process and are "
            "not scheduled durably. Set DURABLE_MODE=dts."
        )
    return LocalDurableExecutor()


def get_durable_executor() -> DurableExecutor:
    global _executor
    if _executor is None:
        _executor = build_durable_executor()
    return _executor


def set_durable_executor(executor: Optional[DurableExecutor]) -> None:
    """Inject/replace the process durable executor (tests)."""
    global _executor
    _executor = executor


__all__ = [
    "DurableExecutor",
    "DurableTaskExecutor",
    "LocalDurableExecutor",
    "WorkflowFn",
    "build_durable_executor",
    "get_durable_executor",
    "set_durable_executor",
]
