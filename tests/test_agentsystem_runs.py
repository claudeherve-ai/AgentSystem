"""Durable run lifecycle, resumable SSE, concurrency isolation, and restart."""

from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agentsystem.db.session import session_scope
from agentsystem.durable import LocalDurableExecutor
from agentsystem.repositories import RunRepository, SessionRepository
from agentsystem.services.run_service import (
    EVENT_MESSAGE_COMPLETED,
    EVENT_MESSAGE_DELTA,
    EVENT_RUN_CANCELLED,
    EVENT_RUN_COMPLETED,
    EVENT_RUN_FAILED,
    EVENT_RUN_STARTED,
    RunService,
    _context_from_run,
)


async def _drain(service, tenant_id, run_id, **kw):
    events = []
    async for ev in service.stream_events(tenant_id, run_id, idle_timeout=2, **kw):
        events.append(ev)
    return events


async def test_run_completes_with_real_attribution(db, run_service, fake_orchestrator, principal_factory, provision_ctx):
    ctx = await provision_ctx(principal_factory("T", "U"), session_id="s", run_id="r")
    run = await run_service.create_and_execute(ctx, input_text="hello world")
    assert run.status == "completed"
    assert run.output_text.endswith("hello world")
    assert run.selected_agent == "FinanceAgent"
    assert run.prompt_tokens == 3 and run.completion_tokens == 5
    # The orchestrator was called with an ISOLATED session matching the run.
    assert fake_orchestrator.calls[0][1] == ctx.session_id


async def test_conversation_state_survives_sequential_worker_runs(
    db, run_service, principal_factory, provision_ctx
):
    first = await provision_ctx(
        principal_factory("T", "U"), session_id="session-a", run_id="run-a"
    )
    await run_service.create_and_execute(first, input_text="first turn")

    second = await provision_ctx(
        principal_factory("T", "U"), session_id="session-a", run_id="run-b"
    )
    await run_service.create_and_execute(second, input_text="second turn")

    async with session_scope() as session:
        state = await SessionRepository(session).load_agent_state(second)
    assert state["turns"] == ["first turn", "second turn"]


async def test_conversation_state_is_isolated_between_sessions(
    db, run_service, principal_factory, provision_ctx
):
    session_a = await provision_ctx(
        principal_factory("T", "U"), session_id="session-a", run_id="run-a"
    )
    session_b = await provision_ctx(
        principal_factory("T", "U"), session_id="session-b", run_id="run-b"
    )
    await run_service.create_and_execute(session_a, input_text="private a")
    await run_service.create_and_execute(session_b, input_text="private b")

    async with session_scope() as session:
        state_a = await SessionRepository(session).load_agent_state(session_a)
        state_b = await SessionRepository(session).load_agent_state(session_b)
    assert state_a["turns"] == ["private a"]
    assert state_b["turns"] == ["private b"]


async def test_event_stream_is_ordered_and_terminal(db, run_service, principal_factory, provision_ctx):
    ctx = await provision_ctx(principal_factory("T", "U"), run_id="r")
    run = await run_service.create_and_execute(ctx, input_text="x")
    events = await _drain(run_service, ctx.tenant_id, run.id)
    types = [e["event"] for e in events]
    ids = [e["id"] for e in events]
    assert types[0] == EVENT_RUN_STARTED
    assert types[-1] == EVENT_RUN_COMPLETED
    assert EVENT_MESSAGE_DELTA in types and EVENT_MESSAGE_COMPLETED in types
    assert ids == sorted(ids) and len(set(ids)) == len(ids)  # monotonic, unique


async def test_sse_resumes_from_last_event_id(db, run_service, principal_factory, provision_ctx):
    ctx = await provision_ctx(principal_factory("T", "U"), run_id="r")
    run = await run_service.create_and_execute(ctx, input_text="x")
    full = await _drain(run_service, ctx.tenant_id, run.id)
    # Resume after the 3rd event; must return only events with id > 3.
    resumed = await _drain(run_service, ctx.tenant_id, run.id, last_event_id=3)
    assert [e["id"] for e in resumed] == [e["id"] for e in full if e["id"] > 3]
    assert all(e["id"] > 3 for e in resumed)


async def test_delta_is_not_fake_chunked(db, run_service, principal_factory, provision_ctx):
    ctx = await provision_ctx(principal_factory("T", "U"), run_id="r")
    run = await run_service.create_and_execute(ctx, input_text="a multi word answer")
    events = await _drain(run_service, ctx.tenant_id, run.id)
    deltas = [e for e in events if e["event"] == EVENT_MESSAGE_DELTA]
    # One delta carrying the full text — not many fabricated word chunks.
    assert len(deltas) == 1
    assert deltas[0]["data"]["text"] == run.output_text


async def test_concurrent_runs_isolated_across_tenants_and_sessions(db, principal_factory, provision_ctx):
    from tests.conftest import FakeOrchestrator

    orch = FakeOrchestrator(answer="reply")
    service = RunService(
        orchestrator_provider=lambda: orch, durable_executor=LocalDurableExecutor()
    )

    # 50 runs across 2 tenants, each with its own session + unique input.
    contexts = []
    for i in range(50):
        tenant = "TA" if i % 2 == 0 else "TB"
        ctx = await provision_ctx(
            principal_factory(tenant, f"user{i}"),
            session_id=f"sess-{i}",
            run_id=f"run-{i}",
        )
        contexts.append((i, ctx))

    async def do(i, ctx):
        return await service.create_and_execute(ctx, input_text=f"input-{i}")

    runs = await asyncio.gather(*[do(i, ctx) for i, ctx in contexts])

    # Every run carries ONLY its own input/tenant/session — zero cross-talk.
    for (i, ctx), run in zip(contexts, runs):
        assert run.status == "completed"
        assert run.output_text == f"reply: input-{i}"
        assert run.tenant_id == ctx.tenant_id
        assert run.session_id == ctx.session_id


async def test_run_failure_is_sanitized(db, principal_factory, provision_ctx):
    from agentsystem.errors import ProviderError
    from tests.conftest import FakeOrchestrator

    boom = FakeOrchestrator(raise_exc=RuntimeError("provider key sk-SECRET leaked"))
    service = RunService(
        orchestrator_provider=lambda: boom, durable_executor=LocalDurableExecutor()
    )
    ctx = await provision_ctx(principal_factory("T", "U"), run_id="r")
    with pytest.raises(ProviderError) as exc:
        await service.create_and_execute(ctx, input_text="x")
    assert "sk-SECRET" not in str(exc.value)
    # Run is durably marked failed with a safe code + a run.failed event.
    async with session_scope() as s:
        run = await RunRepository(s).get(ctx.tenant_id, "r")
    assert run.status == "failed"
    assert run.error_code == "internal_error"
    events = await _drain(service, ctx.tenant_id, "r")
    assert events[-1]["event"] == EVENT_RUN_FAILED


async def test_cancel_marks_run_cancelled(db, run_service, principal_factory, provision_ctx):
    ctx = await provision_ctx(principal_factory("T", "U"), run_id="r")
    await run_service.create_run(ctx, input_text="x")
    run = await run_service.cancel_run(ctx.tenant_id, "r")
    assert run.status == "cancelled"
    # Re-executing a cancelled run is a no-op (durable idempotent restart).
    run2 = await run_service.execute(ctx)
    assert run2.status == "cancelled"


async def test_cancel_is_idempotent_and_emits_one_terminal_event(
    db, run_service, principal_factory, provision_ctx
):
    ctx = await provision_ctx(principal_factory("T", "U"), run_id="r")
    await run_service.create_run(ctx, input_text="x")

    first = await run_service.cancel_run(ctx.tenant_id, "r")
    second = await run_service.cancel_run(ctx.tenant_id, "r")

    assert first.status == second.status == "cancelled"
    events = await run_service.list_events(ctx.tenant_id, "r")
    assert [event.type for event in events].count(EVENT_RUN_CANCELLED) == 1
    async with session_scope() as session:
        claimed = await RunRepository(session).claim_for_execution(ctx.tenant_id, "r")
    assert claimed is None


async def test_running_cancel_waits_for_worker_ack(
    db, principal_factory, provision_ctx
):
    from tests.conftest import FakeOrchestrator

    class BlockingOrchestrator(FakeOrchestrator):
        def __init__(self):
            super().__init__()
            self.started = asyncio.Event()
            self.release = asyncio.Event()

        async def run_turn(self, task, *, session_state=None, context=None):
            self.started.set()
            await self.release.wait()
            return await super().run_turn(
                task, session_state=session_state, context=context
            )

    orchestrator = BlockingOrchestrator()
    service = RunService(
        orchestrator_provider=lambda: orchestrator,
        durable_executor=LocalDurableExecutor(),
    )
    ctx = await provision_ctx(principal_factory("T", "U"), run_id="r")
    await service.create_run(ctx, input_text="x")
    execution = asyncio.create_task(service.execute(ctx))
    await asyncio.wait_for(orchestrator.started.wait(), timeout=2)

    run = await service.cancel_run(ctx.tenant_id, "r")
    assert run.status == "running"
    assert run.cancel_requested is True
    events = await service.list_events(ctx.tenant_id, "r")
    assert EVENT_RUN_CANCELLED not in [event.type for event in events]

    orchestrator.release.set()
    await execution
    final = await service.get_run(ctx.tenant_id, "r")
    assert final.status == "cancelled"


async def test_stale_execution_token_cannot_complete_reclaimed_run(
    db, run_service, principal_factory, provision_ctx
):
    ctx = await provision_ctx(principal_factory("T", "U"), run_id="r")
    await run_service.create_run(ctx, input_text="x")
    async with session_scope() as session:
        runs = RunRepository(session)
        first = await runs.claim_for_execution(ctx.tenant_id, "r")
        assert first is not None and first.execution_token
        stale_token = first.execution_token
        first.execution_lease_until = datetime.now(timezone.utc) - timedelta(seconds=1)

    async with session_scope() as session:
        runs = RunRepository(session)
        second = await runs.claim_for_execution(ctx.tenant_id, "r")
        assert second is not None and second.execution_token != stale_token
        current_token = second.execution_token
        assert await runs.complete_execution(
            ctx.tenant_id,
            "r",
            stale_token,
            selected_agent="stale",
            route="orchestrator",
            output_text="stale output",
        ) is None
        completed = await runs.complete_execution(
            ctx.tenant_id,
            "r",
            current_token,
            selected_agent="current",
            route="orchestrator",
            output_text="current output",
        )
        assert completed is not None

    final = await run_service.get_run(ctx.tenant_id, "r")
    assert final.status == "completed"
    assert final.output_text == "current output"


async def test_cancel_request_wins_over_concurrent_completion(
    db, run_service, principal_factory, provision_ctx
):
    ctx = await provision_ctx(principal_factory("T", "U"), run_id="r")
    await run_service.create_run(ctx, input_text="x")
    async with session_scope() as session:
        runs = RunRepository(session)
        claimed = await runs.claim_for_execution(ctx.tenant_id, "r")
        assert claimed is not None and claimed.execution_token
        token = claimed.execution_token

    await run_service.cancel_run(ctx.tenant_id, "r")
    async with session_scope() as session:
        runs = RunRepository(session)
        assert await runs.complete_execution(
            ctx.tenant_id,
            "r",
            token,
            selected_agent="too-late",
            route="orchestrator",
            output_text="must not persist",
        ) is None
        cancelled = await runs.acknowledge_cancellation(
            ctx.tenant_id, "r", token
        )
        assert cancelled is not None

    final = await run_service.get_run(ctx.tenant_id, "r")
    assert final.status == "cancelled"
    assert final.output_text is None


async def test_duplicate_activity_delivery_invokes_orchestrator_once(
    db, principal_factory, provision_ctx
):
    from tests.conftest import FakeOrchestrator

    class BlockingOrchestrator(FakeOrchestrator):
        def __init__(self):
            super().__init__()
            self.started = asyncio.Event()
            self.release = asyncio.Event()

        async def run_turn(self, task, *, session_state=None, context=None):
            self.started.set()
            await self.release.wait()
            return await super().run_turn(
                task, session_state=session_state, context=context
            )

    orchestrator = BlockingOrchestrator()
    service = RunService(
        orchestrator_provider=lambda: orchestrator,
        durable_executor=LocalDurableExecutor(),
    )
    ctx = await provision_ctx(principal_factory("T", "U"), run_id="r")
    await service.create_run(ctx, input_text="execute once")

    owner = asyncio.create_task(
        service.run_persisted_workflow(ctx.tenant_id, ctx.run_id)
    )
    await asyncio.wait_for(orchestrator.started.wait(), timeout=2)
    duplicate = asyncio.create_task(
        service.run_persisted_workflow(ctx.tenant_id, ctx.run_id)
    )
    await asyncio.sleep(0.15)
    assert len(orchestrator.calls) == 0

    orchestrator.release.set()
    await asyncio.gather(owner, duplicate)
    assert len(orchestrator.calls) == 1
    events = await service.list_events(ctx.tenant_id, ctx.run_id)
    assert [event.type for event in events].count(EVENT_RUN_COMPLETED) == 1


async def test_stale_execution_token_cannot_renew_fail_or_append_events(
    db, run_service, principal_factory, provision_ctx
):
    from agentsystem.errors import ConflictError

    ctx = await provision_ctx(principal_factory("T", "U"), run_id="r")
    await run_service.create_run(ctx, input_text="x")
    async with session_scope() as session:
        runs = RunRepository(session)
        first = await runs.claim_for_execution(ctx.tenant_id, "r")
        assert first is not None and first.execution_token
        stale_token = first.execution_token
        first.execution_lease_until = datetime.now(timezone.utc) - timedelta(seconds=1)

    async with session_scope() as session:
        runs = RunRepository(session)
        second = await runs.claim_for_execution(ctx.tenant_id, "r")
        assert second is not None and second.execution_token != stale_token
        assert not await runs.renew_execution_lease(
            ctx.tenant_id, "r", stale_token
        )
        assert await runs.fail_execution(
            ctx.tenant_id,
            "r",
            stale_token,
            error_code="stale_failure",
        ) is None
        with pytest.raises(ConflictError):
            await runs.append_event(
                ctx.tenant_id,
                "r",
                EVENT_RUN_FAILED,
                {"error_code": "stale_failure"},
                execution_token=stale_token,
            )


async def test_durable_restart_skips_completed_run(db, run_service, principal_factory, provision_ctx):
    ctx = await provision_ctx(principal_factory("T", "U"), run_id="r")
    run = await run_service.create_and_execute(ctx, input_text="x")
    assert run.status == "completed"
    async with session_scope() as s:
        before = len(await RunRepository(s).list_events(ctx.tenant_id, "r"))
    # Simulate a worker restart re-invoking the workflow for the same run.
    await run_service._workflow(ctx.tenant_id, "r")
    async with session_scope() as s:
        after = len(await RunRepository(s).list_events(ctx.tenant_id, "r"))
    assert before == after  # no duplicate execution / events


async def test_worker_poll_processes_pending(db, run_service, principal_factory, provision_ctx):
    ctx = await provision_ctx(principal_factory("T", "U"), run_id="r")
    await run_service.create_run(ctx, input_text="pending work")
    from apps.worker.main import process_pending_once

    processed = await process_pending_once(run_service)
    assert processed == 1
    async with session_scope() as s:
        run = await RunRepository(s).get(ctx.tenant_id, "r")
    assert run.status == "completed"


async def test_worker_reclaims_expired_execution_lease(
    db, run_service, principal_factory, provision_ctx
):
    ctx = await provision_ctx(principal_factory("T", "U"), run_id="r")
    await run_service.create_run(ctx, input_text="recover abandoned work")
    async with session_scope() as s:
        run = await RunRepository(s).claim_for_execution(ctx.tenant_id, "r")
        assert run is not None
        run.execution_lease_until = datetime.now(timezone.utc) - timedelta(seconds=1)

    from apps.worker.main import process_pending_once

    assert await process_pending_once(run_service) == 1
    final = await run_service.get_run(ctx.tenant_id, "r")
    assert final.status == "completed"


async def test_worker_acknowledges_cancel_after_owner_crash(
    db, run_service, principal_factory, provision_ctx
):
    ctx = await provision_ctx(principal_factory("T", "U"), run_id="r")
    await run_service.create_run(ctx, input_text="cancel abandoned work")
    async with session_scope() as s:
        run = await RunRepository(s).claim_for_execution(ctx.tenant_id, "r")
        assert run is not None
        run.execution_lease_until = datetime.now(timezone.utc) - timedelta(seconds=1)
        await RunRepository(s).request_cancel(ctx.tenant_id, "r")

    from apps.worker.main import process_pending_once

    assert await process_pending_once(run_service) == 1
    final = await run_service.get_run(ctx.tenant_id, "r")
    assert final.status == "cancelled"
