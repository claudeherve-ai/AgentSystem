"""Shared Durable Task orchestration and activity definitions."""

from __future__ import annotations

import asyncio
from typing import Any


def run_orchestration(ctx, payload: dict[str, str]):
    """Deterministic orchestration: delegate side effects to one activity."""
    result = yield ctx.call_activity(execute_run_activity, input=payload)
    return result


def execute_run_activity(_ctx, payload: dict[str, str]) -> dict[str, Any]:
    """Execute the persisted run workflow inside the worker process."""

    async def _run() -> dict[str, Any]:
        from api.dependencies import get_run_service

        service = get_run_service()
        await service.run_persisted_workflow(
            payload["tenant_id"], payload["run_id"]
        )
        run = await service.get_run(payload["tenant_id"], payload["run_id"])
        return {"run_id": run.id, "status": run.status}

    return asyncio.run(_run())


__all__ = ["execute_run_activity", "run_orchestration"]
