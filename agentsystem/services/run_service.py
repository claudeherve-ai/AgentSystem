"""Durable run service: create/execute/cancel runs and stream real events.

The run service is the single durable entry point for agent execution. It:

* Creates runs and persists the user message under the caller's scope.
* Executes a resume-safe plan → execute → review workflow via the configured
  durable executor (local inline for dev/test; Durable Task Scheduler in prod).
* Emits **real** run events as work happens (``run.started``, ``agent.selected``,
  ``tool.*``, ``message.delta``, ``message.completed``, ``run.completed`` …).
  It never fabricates token-by-token chunks of an already-finished answer.
* Streams those persisted events over SSE with monotonic ids so a client can
  resume from ``Last-Event-ID`` after a disconnect.
* Bridges to the existing orchestrator with a per-run **isolated** session state
  so no orchestration state is shared across users.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, AsyncIterator, Callable, Optional, Protocol

from agentsystem.context import RunContext, new_id
from agentsystem.db.models import Run, RunEvent
from agentsystem.db.session import session_scope
from agentsystem.durable import DurableExecutor, get_durable_executor
from agentsystem.errors import ProviderError, sanitize_exception
from agentsystem.repositories import (
    ApprovalRepository,
    ArtifactRepository,
    AuditRepository,
    MessageRepository,
    PlanRepository,
    RunRepository,
    SessionRepository,
)
from agentsystem.services.artifacts import get_artifact_store

logger = logging.getLogger("agentsystem.runs")
EXECUTION_LEASE_SECONDS = 1800
EXECUTION_CLAIM_POLL_SECONDS = 0.1

# ── Canonical run-event vocabulary ──────────────────────────────────────────
EVENT_RUN_STARTED = "run.started"
EVENT_PLAN_UPDATED = "plan.updated"
EVENT_AGENT_SELECTED = "agent.selected"
EVENT_TOOL_STARTED = "tool.started"
EVENT_TOOL_COMPLETED = "tool.completed"
EVENT_APPROVAL_REQUESTED = "approval.requested"
EVENT_APPROVAL_DECIDED = "approval.decided"
EVENT_ARTIFACT_CREATED = "artifact.created"
EVENT_MESSAGE_DELTA = "message.delta"
EVENT_MESSAGE_COMPLETED = "message.completed"
EVENT_RUN_COMPLETED = "run.completed"
EVENT_RUN_FAILED = "run.failed"
EVENT_RUN_CANCELLED = "run.cancelled"

_TERMINAL_EVENTS = {EVENT_RUN_COMPLETED, EVENT_RUN_FAILED, EVENT_RUN_CANCELLED}


class OrchestratorLike(Protocol):
    """The minimal orchestrator surface the run service depends on."""

    def new_session_state(
        self,
        session_id: Optional[str] = None,
        persisted_state: Optional[dict[str, Any]] = None,
    ) -> Any: ...

    def serialize_session_state(self, session_state: Any) -> dict[str, Any]: ...

    async def run_turn(
        self, task: str, *, session_state: Any = None, context: Any = None
    ) -> Any: ...


def _default_orchestrator_provider() -> OrchestratorLike:
    """Lazily build the real orchestrator (avoids import cost at module load)."""
    from api.dependencies import get_orchestrator

    return get_orchestrator()


class RunService:
    """Durable run lifecycle and event streaming."""

    def __init__(
        self,
        *,
        orchestrator_provider: Optional[Callable[[], OrchestratorLike]] = None,
        durable_executor: Optional[DurableExecutor] = None,
        max_retries: int = 1,
    ) -> None:
        self._orchestrator_provider = (
            orchestrator_provider or _default_orchestrator_provider
        )
        self._executor = durable_executor
        self._max_retries = max(0, max_retries)

    def _durable(self) -> DurableExecutor:
        return self._executor or get_durable_executor()

    @property
    def execution_mode(self) -> str:
        """Configured dispatch mode (``local`` or ``dts``)."""
        return self._durable().mode

    # ── Create / read ───────────────────────────────────────────────────────
    async def create_run(
        self,
        ctx: RunContext,
        *,
        input_text: str,
        preferred_agent: str = "",
        idempotency_key: str = "",
    ) -> Run:
        """Persist a run + its user message under the caller's isolated scope."""
        async with session_scope() as session:
            runs = RunRepository(session)
            if idempotency_key:
                existing = await runs.by_idempotency(
                    ctx.tenant_id, idempotency_key
                )
                if existing is not None:
                    runs._validate_idempotent_reuse(
                        existing, ctx, input_text, preferred_agent
                    )
                    return existing
            sessions = SessionRepository(session)
            await sessions.ensure_for_context(ctx, title=input_text[:80])
            run, created = await runs.create_with_status(
                ctx,
                input_text=input_text,
                preferred_agent=preferred_agent,
                idempotency_key=idempotency_key,
            )
            if not created:
                return run
            messages = MessageRepository(session)
            await messages.add(ctx, "user", input_text, run_id=run.id)
            audit = AuditRepository(session)
            await audit.record(
                ctx, action="run.created", target=run.id,
                payload={"preferred_agent": preferred_agent},
            )
            return run

    async def get_run(
        self,
        tenant_id: str,
        run_id: str,
        *,
        workspace_id: Optional[str] = None,
    ) -> Run:
        async with session_scope() as session:
            return await RunRepository(session).get(
                tenant_id, run_id, workspace_id=workspace_id
            )

    async def list_runs(
        self,
        tenant_id: str,
        *,
        workspace_id: Optional[str] = None,
        session_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> list[Run]:
        async with session_scope() as session:
            return await RunRepository(session).list(
                tenant_id,
                workspace_id=workspace_id,
                session_id=session_id,
                status=status,
                limit=limit,
            )

    async def cancel_run(
        self,
        tenant_id: str,
        run_id: str,
        *,
        workspace_id: Optional[str] = None,
    ) -> Run:
        async with session_scope() as session:
            runs = RunRepository(session)
            await runs.get(
                tenant_id, run_id, workspace_id=workspace_id
            )
            run, changed = await runs.request_cancel_once(tenant_id, run_id)
            if run.status == "cancelled" and changed:
                await runs.append_event(tenant_id, run_id, EVENT_RUN_CANCELLED, {})
            return run

    async def list_events(
        self, tenant_id: str, run_id: str, *, after_event_id: int = 0
    ) -> list[RunEvent]:
        async with session_scope() as session:
            return await RunRepository(session).list_events(
                tenant_id, run_id, after_event_id=after_event_id
            )

    # ── Execution ───────────────────────────────────────────────────────────
    async def execute(self, ctx: RunContext) -> Run:
        """Dispatch the run through the durable executor and return the run."""
        await self._durable().execute(ctx.tenant_id, ctx.run_id, self._workflow)
        return await self.get_run(ctx.tenant_id, ctx.run_id)

    async def run_persisted_workflow(self, tenant_id: str, run_id: str) -> None:
        """Execute the persisted workflow directly inside a worker activity."""
        await self._workflow(tenant_id, run_id)

    async def create_and_execute(
        self,
        ctx: RunContext,
        *,
        input_text: str,
        preferred_agent: str = "",
        idempotency_key: str = "",
    ) -> Run:
        """Create then execute a run (the synchronous ``/chat`` compat path)."""
        run = await self.create_run(
            ctx,
            input_text=input_text,
            preferred_agent=preferred_agent,
            idempotency_key=idempotency_key,
        )
        # Bind the (possibly idempotent-reused) run id back onto the context.
        exec_ctx = ctx.with_run(run.id)
        return await self.execute(exec_ctx)

    async def _renew_lease_until_stopped(
        self,
        tenant_id: str,
        run_id: str,
        execution_token: str,
        stop: asyncio.Event,
    ) -> None:
        """Keep the execution claim alive while a long-running agent turn is active."""
        interval = EXECUTION_LEASE_SECONDS / 3
        while True:
            try:
                await asyncio.wait_for(stop.wait(), timeout=interval)
                return
            except TimeoutError:
                try:
                    async with session_scope() as session:
                        renewed = await RunRepository(session).renew_execution_lease(
                            tenant_id,
                            run_id,
                            execution_token,
                            lease_seconds=EXECUTION_LEASE_SECONDS,
                        )
                except Exception:  # noqa: BLE001 - execution continues; expiry enables recovery
                    logger.exception("Execution lease renewal failed for run %s", run_id)
                    return
                if not renewed:
                    logger.warning("Execution lease was lost for run %s", run_id)
                    return

    async def _workflow(self, tenant_id: str, run_id: str) -> None:
        """Resume-safe plan → execute → review workflow.

        Progress is persisted as durable run events (no filesystem checkpoints),
        so a restart re-invokes this method and completed runs are skipped.
        """
        # Redelivered activities wait for the active owner to finish or for its
        # lease to expire. Returning early would incorrectly tell Durable Task
        # that an unexecuted activity completed successfully.
        run = await self._claim_or_wait(tenant_id, run_id)
        if run is None:
            return
        execution_token = run.execution_token
        if not execution_token:  # pragma: no cover - repository invariant
            raise RuntimeError("claimed run has no execution token")

        async with session_scope() as session:
            runs = RunRepository(session)
            if run.cancel_requested:
                cancelled = await runs.acknowledge_cancellation(
                    tenant_id, run_id, execution_token
                )
                if cancelled is not None:
                    await runs.append_event(
                        tenant_id, run_id, EVENT_RUN_CANCELLED, {}
                    )
                return
            ctx = _context_from_run(run)
            input_text = run.input_text
            preferred_agent = run.preferred_agent or ""
            persisted_state = await SessionRepository(session).load_agent_state(ctx)
            await runs.append_event(
                tenant_id,
                run_id,
                EVENT_RUN_STARTED,
                {},
                execution_token=execution_token,
            )
            await runs.append_event(
                tenant_id, run_id, EVENT_PLAN_UPDATED,
                {"phase": "execute", "steps": ["execute", "review"]},
                execution_token=execution_token,
            )

        # Execute phase (bridges to the orchestrator with isolated state).
        lease_stop = asyncio.Event()
        lease_task = asyncio.create_task(
            self._renew_lease_until_stopped(
                tenant_id, run_id, execution_token, lease_stop
            )
        )
        try:
            turn, agent_state = await self._run_agent(
                ctx,
                input_text,
                preferred_agent,
                persisted_state,
            )
        except ProviderError as exc:
            outcome = await self._fail(
                tenant_id, run_id, execution_token, "provider_unavailable"
            )
            if outcome == "failed":
                raise exc
            return
        except Exception as exc:  # noqa: BLE001 - sanitize + fail closed
            outcome = await self._fail(
                tenant_id, run_id, execution_token, "internal_error"
            )
            if outcome == "failed":
                raise sanitize_exception(exc) from exc
            return
        finally:
            lease_stop.set()
            await lease_task

        # Persist the answer + terminal events.
        async with session_scope() as session:
            runs = RunRepository(session)
            selected = turn.selected_agent or preferred_agent or "orchestrator"
            completed = await runs.complete_execution(
                tenant_id,
                run_id,
                execution_token,
                selected_agent=selected,
                route="orchestrator",
                output_text=turn.text,
                prompt_tokens=turn.prompt_tokens,
                completion_tokens=turn.completion_tokens,
            )
            if completed is None:
                cancelled = await runs.acknowledge_cancellation(
                    tenant_id, run_id, execution_token
                )
                if cancelled is not None:
                    await runs.append_event(
                        tenant_id, run_id, EVENT_RUN_CANCELLED, {}
                    )
                return
            await SessionRepository(session).save_agent_state(ctx, agent_state)
            await runs.append_event(
                tenant_id, run_id, EVENT_AGENT_SELECTED,
                {"agent": selected, "agents_used": turn.agents_used},
            )
            for agent_name in turn.agents_used:
                await runs.append_event(
                    tenant_id, run_id, EVENT_TOOL_STARTED, {"agent": agent_name}
                )
                await runs.append_event(
                    tenant_id, run_id, EVENT_TOOL_COMPLETED, {"agent": agent_name}
                )
            await runs.append_event(
                tenant_id, run_id, EVENT_MESSAGE_DELTA, {"text": turn.text}
            )
            await runs.append_event(
                tenant_id, run_id, EVENT_MESSAGE_COMPLETED, {"length": len(turn.text)}
            )
            messages = MessageRepository(session)
            await messages.add(
                ctx, "assistant", turn.text,
                agent_name=selected, run_id=run_id,
            )
            await runs.append_event(
                tenant_id, run_id, EVENT_RUN_COMPLETED,
                {"agent": selected, "length": len(turn.text)},
            )

    async def _run_agent(
        self,
        ctx: RunContext,
        input_text: str,
        preferred_agent: str,
        persisted_state: dict[str, Any],
    ):
        """Call the orchestrator with an isolated session state + light retry."""
        orchestrator = self._orchestrator_provider()
        task = input_text
        if preferred_agent:
            task = f"[Direct to {preferred_agent}]: {input_text}"
        attempts = self._max_retries + 1
        last_exc: Optional[Exception] = None
        for attempt in range(attempts):
            state = orchestrator.new_session_state(
                session_id=ctx.session_id,
                persisted_state=persisted_state,
            )
            try:
                turn = await orchestrator.run_turn(
                    task, session_state=state, context=ctx
                )
                return turn, orchestrator.serialize_session_state(state)
            except ProviderError as exc:
                last_exc = exc
                if attempt + 1 < attempts:
                    await asyncio.sleep(0.05 * (attempt + 1))
                    continue
                raise
            except Exception:
                raise
        if last_exc:  # pragma: no cover - defensive
            raise last_exc

    async def _claim_or_wait(
        self, tenant_id: str, run_id: str
    ) -> Optional[Run]:
        """Claim work, waiting through an active duplicate delivery if needed."""
        while True:
            async with session_scope() as session:
                runs = RunRepository(session)
                run = await runs.get(tenant_id, run_id)
                if run.status in ("completed", "failed", "cancelled"):
                    return None
                claimed = await runs.claim_for_execution(
                    tenant_id,
                    run_id,
                    lease_seconds=EXECUTION_LEASE_SECONDS,
                )
                if claimed is not None:
                    return claimed
            await asyncio.sleep(EXECUTION_CLAIM_POLL_SECONDS)

    async def _fail(
        self,
        tenant_id: str,
        run_id: str,
        execution_token: str,
        error_code: str,
    ) -> Optional[str]:
        async with session_scope() as session:
            runs = RunRepository(session)
            failed = await runs.fail_execution(
                tenant_id,
                run_id,
                execution_token,
                error_code=error_code,
            )
            if failed is not None:
                await runs.append_event(
                    tenant_id,
                    run_id,
                    EVENT_RUN_FAILED,
                    {"error_code": error_code},
                )
                return "failed"
            cancelled = await runs.acknowledge_cancellation(
                tenant_id, run_id, execution_token
            )
            if cancelled is not None:
                await runs.append_event(
                    tenant_id, run_id, EVENT_RUN_CANCELLED, {}
                )
                return "cancelled"
            return None

    # ── Durable approval hooks (exactly-once, event-emitting) ───────────────
    async def request_run_approval(
        self,
        ctx: RunContext,
        *,
        agent_name: str,
        action: str,
        details: str = "",
        ttl_seconds: int = 300,
        idempotency_key: str = "",
    ):
        async with session_scope() as session:
            approvals = ApprovalRepository(session)
            approval = await approvals.create(
                ctx,
                agent_name=agent_name,
                action=action,
                details=details,
                ttl_seconds=ttl_seconds,
                idempotency_key=idempotency_key,
                run_id=ctx.run_id,
            )
            await RunRepository(session).append_event(
                ctx.tenant_id, ctx.run_id, EVENT_APPROVAL_REQUESTED,
                {"approval_id": approval.id, "action": action},
            )
            return approval

    async def decide_run_approval(
        self,
        tenant_id: str,
        run_id: str,
        approval_id: str,
        *,
        approved: bool,
        feedback: str = "",
        decided_by: str = "",
    ):
        async with session_scope() as session:
            approvals = ApprovalRepository(session)
            decision = await approvals.decide(
                tenant_id, approval_id,
                approved=approved, feedback=feedback, decided_by=decided_by,
            )
            if decision.decided:
                await RunRepository(session).append_event(
                    tenant_id, run_id, EVENT_APPROVAL_DECIDED,
                    {"approval_id": approval_id, "approved": approved},
                )
            return decision

    # ── Artifact creation (bytes → store, metadata → SQL, event) ────────────
    async def create_artifact(
        self,
        ctx: RunContext,
        *,
        name: str,
        content_type: str,
        data: bytes,
    ):
        store = get_artifact_store()
        key = f"{ctx.tenant_id}/{ctx.run_id}/{new_id('art')}/{name}"
        stored = await store.put(key, data)
        async with session_scope() as session:
            artifacts = ArtifactRepository(session)
            artifact = await artifacts.create(
                ctx,
                name=name,
                content_type=content_type,
                size_bytes=stored.size_bytes,
                storage_backend=stored.backend,
                storage_key=stored.key,
                sha256=stored.sha256,
                run_id=ctx.run_id,
            )
            await RunRepository(session).append_event(
                ctx.tenant_id, ctx.run_id, EVENT_ARTIFACT_CREATED,
                {"artifact_id": artifact.id, "name": name},
            )
            return artifact

    # ── SSE streaming ───────────────────────────────────────────────────────
    async def stream_events(
        self,
        tenant_id: str,
        run_id: str,
        *,
        last_event_id: int = 0,
        poll_interval: float = 0.25,
        idle_timeout: float = 30.0,
    ) -> AsyncIterator[dict[str, Any]]:
        """Yield persisted events after ``last_event_id`` until the run ends.

        Real events only — never fabricated chunks. Resumes from
        ``last_event_id`` (the SSE ``Last-Event-ID``). Stops after a terminal
        event or when the run is already terminal and drained.
        """
        cursor = last_event_id
        waited = 0.0
        while True:
            events = await self.list_events(
                tenant_id, run_id, after_event_id=cursor
            )
            if events:
                waited = 0.0
                for event in events:
                    cursor = event.event_id
                    yield {
                        "id": event.event_id,
                        "event": event.type,
                        "data": event.data,
                    }
                    if event.type in _TERMINAL_EVENTS:
                        return
                continue
            # No new events: stop if the run is already terminal + fully drained.
            run = await self.get_run(tenant_id, run_id)
            if run.status in ("completed", "failed", "cancelled"):
                # Drain any final events that landed between checks.
                tail = await self.list_events(
                    tenant_id, run_id, after_event_id=cursor
                )
                for event in tail:
                    cursor = event.event_id
                    yield {
                        "id": event.event_id,
                        "event": event.type,
                        "data": event.data,
                    }
                return
            await asyncio.sleep(poll_interval)
            waited += poll_interval
            if waited >= idle_timeout:
                return


def _context_from_run(run: Run) -> RunContext:
    """Reconstruct an execution context from a persisted run row."""
    return RunContext(
        tenant_id=run.tenant_id,
        user_id=run.user_id,
        workspace_id=run.workspace_id,
        project_id=run.project_id or "",
        session_id=run.session_id,
        run_id=run.id,
        request_id=new_id("req"),
    )


__all__ = [
    "EVENT_AGENT_SELECTED",
    "EVENT_APPROVAL_DECIDED",
    "EVENT_APPROVAL_REQUESTED",
    "EVENT_ARTIFACT_CREATED",
    "EVENT_MESSAGE_COMPLETED",
    "EVENT_MESSAGE_DELTA",
    "EVENT_PLAN_UPDATED",
    "EVENT_RUN_CANCELLED",
    "EVENT_RUN_COMPLETED",
    "EVENT_RUN_FAILED",
    "EVENT_RUN_STARTED",
    "EVENT_TOOL_COMPLETED",
    "EVENT_TOOL_STARTED",
    "OrchestratorLike",
    "RunService",
]
