"""Run, run-event, and plan repositories.

This module owns the durable run lifecycle:

* Monotonic, gap-free per-run event ids (the source of truth for resumable SSE).
* Optimistic-concurrency status transitions via a ``version`` guard.
* Idempotent run creation keyed by ``(tenant_id, idempotency_key)``.
* Plan / plan-step / plan-event persistence for plan-execute-review workflows.

All methods are tenant-scoped; a run is only ever returned to its owning tenant.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import uuid4

from sqlalchemy import case, or_, select, update
from sqlalchemy.exc import IntegrityError

from agentsystem.context import RunContext
from agentsystem.db.models import (
    RUN_TERMINAL_STATUSES,
    Plan,
    PlanEvent,
    PlanStep,
    Run,
    RunEvent,
)
from agentsystem.errors import ConflictError
from agentsystem.repositories.base import BaseRepository


class RunRepository(BaseRepository):
    """Durable agent runs."""

    async def create(
        self,
        ctx: RunContext,
        *,
        input_text: str,
        preferred_agent: str = "",
        idempotency_key: str = "",
    ) -> Run:
        run, _ = await self.create_with_status(
            ctx,
            input_text=input_text,
            preferred_agent=preferred_agent,
            idempotency_key=idempotency_key,
        )
        return run

    async def create_with_status(
        self,
        ctx: RunContext,
        *,
        input_text: str,
        preferred_agent: str = "",
        idempotency_key: str = "",
    ) -> tuple[Run, bool]:
        """Create a run under the caller's scope.

        When ``idempotency_key`` is supplied and a run with the same
        ``(tenant_id, idempotency_key)`` already exists, that run is returned
        unchanged (idempotent create).
        """
        if idempotency_key:
            existing = await self._by_idempotency(ctx.tenant_id, idempotency_key)
            if existing is not None:
                self._validate_idempotent_reuse(
                    existing, ctx, input_text, preferred_agent
                )
                return existing, False
        run = Run(
            id=ctx.run_id,
            tenant_id=ctx.tenant_id,
            workspace_id=ctx.workspace_id,
            project_id=ctx.project_id,
            session_id=ctx.session_id,
            user_id=ctx.user_id,
            status="pending",
            input_text=input_text,
            preferred_agent=preferred_agent or None,
            idempotency_key=idempotency_key or None,
        )
        if not idempotency_key:
            self.session.add(run)
            await self.session.flush()
            return run, True
        try:
            async with self.session.begin_nested():
                self.session.add(run)
                await self.session.flush()
        except IntegrityError:
            # The savepoint absorbs the unique-key race without poisoning the
            # outer request transaction.
            existing = await self._by_idempotency(ctx.tenant_id, idempotency_key)
            if existing is None:
                raise
            self._validate_idempotent_reuse(
                existing, ctx, input_text, preferred_agent
            )
            return existing, False
        return run, True

    async def _by_idempotency(
        self, tenant_id: str, idempotency_key: str
    ) -> Optional[Run]:
        result = await self.session.execute(
            select(Run).where(
                Run.tenant_id == tenant_id,
                Run.idempotency_key == idempotency_key,
            )
        )
        return result.scalar_one_or_none()

    async def by_idempotency(
        self, tenant_id: str, idempotency_key: str
    ) -> Optional[Run]:
        return await self._by_idempotency(tenant_id, idempotency_key)

    @staticmethod
    def _validate_idempotent_reuse(
        existing: Run,
        ctx: RunContext,
        input_text: str,
        preferred_agent: str,
    ) -> None:
        if (
            existing.user_id != ctx.user_id
            or existing.workspace_id != ctx.workspace_id
            or existing.input_text != input_text
            or (existing.preferred_agent or "") != (preferred_agent or "")
        ):
            raise ConflictError("idempotency key was already used for another request")

    async def get(
        self,
        tenant_id: str,
        run_id: str,
        *,
        workspace_id: Optional[str] = None,
    ) -> Run:
        obj = await self.session.get(Run, run_id)
        run = self._check_scope(obj, tenant_id=tenant_id, kind="run")
        if workspace_id and run.workspace_id != workspace_id:
            from agentsystem.errors import NotFoundError

            raise NotFoundError("run not found")
        return run

    async def get_or_none(
        self, tenant_id: str, run_id: str
    ) -> Optional[Run]:
        obj = await self.session.get(Run, run_id)
        if obj is None or obj.tenant_id != tenant_id:
            return None
        return obj

    async def list(
        self,
        tenant_id: str,
        *,
        workspace_id: Optional[str] = None,
        session_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> list[Run]:
        query = select(Run).where(Run.tenant_id == tenant_id)
        if workspace_id:
            query = query.where(Run.workspace_id == workspace_id)
        if session_id:
            query = query.where(Run.session_id == session_id)
        if status:
            query = query.where(Run.status == status)
        query = query.order_by(Run.created_at.desc()).limit(limit)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def transition_status(
        self,
        tenant_id: str,
        run_id: str,
        new_status: str,
        *,
        expected_version: Optional[int] = None,
        selected_agent: Optional[str] = None,
        route: Optional[str] = None,
        output_text: Optional[str] = None,
        error_code: Optional[str] = None,
    ) -> Run:
        """Transition a run's status with an optimistic-concurrency guard.

        When ``expected_version`` is provided and does not match the current
        row version, a :class:`ConflictError` is raised (a competing writer
        already advanced the run). The version is bumped on every successful
        transition.
        """
        run = await self.get(tenant_id, run_id)
        if expected_version is not None and run.version != expected_version:
            raise ConflictError("run was modified concurrently")
        run.status = new_status
        run.version += 1
        if selected_agent is not None:
            run.selected_agent = selected_agent
        if route is not None:
            run.route = route
        if output_text is not None:
            run.output_text = output_text
        if error_code is not None:
            run.error_code = error_code
        if new_status in RUN_TERMINAL_STATUSES:
            run.execution_lease_until = None
            run.execution_token = None
        await self.session.flush()
        return run

    async def record_usage(
        self,
        tenant_id: str,
        run_id: str,
        *,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        latency_ms: int = 0,
        cost_usd: float = 0.0,
    ) -> Run:
        run = await self.get(tenant_id, run_id)
        run.prompt_tokens += max(0, prompt_tokens)
        run.completion_tokens += max(0, completion_tokens)
        run.latency_ms = max(run.latency_ms, latency_ms)
        run.cost_usd += max(0.0, cost_usd)
        await self.session.flush()
        return run

    async def request_cancel(self, tenant_id: str, run_id: str) -> Run:
        """Mark a run for cancellation.

        Pending work is terminal immediately because no side effect has started.
        Running work remains non-terminal until the worker acknowledges the
        cancellation at its next durable checkpoint.
        """
        run, _ = await self.request_cancel_once(tenant_id, run_id)
        return run

    async def request_cancel_once(
        self,
        tenant_id: str,
        run_id: str,
    ) -> tuple[Run, bool]:
        """Atomically request cancellation and report whether this call won."""
        stmt = (
            update(Run)
            .where(
                Run.id == run_id,
                Run.tenant_id == tenant_id,
                Run.cancel_requested.is_(False),
                Run.status.in_(("pending", "running")),
            )
            .values(
                cancel_requested=True,
                status=case(
                    (Run.status == "pending", "cancelled"),
                    else_=Run.status,
                ),
                version=case(
                    (Run.status == "pending", Run.version + 1),
                    else_=Run.version,
                ),
                execution_lease_until=case(
                    (Run.status == "pending", None),
                    else_=Run.execution_lease_until,
                ),
            )
            .returning(Run.id)
            .execution_options(synchronize_session=False)
        )
        updated_id = (await self.session.execute(stmt)).scalar_one_or_none()
        self.session.expire_all()
        run = await self.get(tenant_id, run_id)
        return run, updated_id is not None

    async def claim_for_execution(
        self,
        tenant_id: str,
        run_id: str,
        *,
        lease_seconds: int = 1800,
    ) -> Optional[Run]:
        """Atomically claim pending or abandoned work for one fenced worker."""
        now = _utcnow()
        lease_until = now + timedelta(seconds=max(30, lease_seconds))
        execution_token = uuid4().hex
        stmt = (
            update(Run)
            .where(
                Run.id == run_id,
                Run.tenant_id == tenant_id,
                or_(
                    (
                        (Run.status == "pending")
                        & Run.cancel_requested.is_(False)
                    ),
                    (
                        (Run.status == "running")
                        & or_(
                            Run.execution_lease_until.is_(None),
                            Run.execution_lease_until <= now,
                        )
                    ),
                ),
            )
            .values(
                status="running",
                execution_lease_until=lease_until,
                execution_token=execution_token,
                version=Run.version + 1,
            )
            .returning(Run.id)
            .execution_options(synchronize_session=False)
        )
        claimed_id = (await self.session.execute(stmt)).scalar_one_or_none()
        if claimed_id is None:
            return None
        self.session.expire_all()
        return await self.get(tenant_id, claimed_id)

    async def renew_execution_lease(
        self,
        tenant_id: str,
        run_id: str,
        execution_token: str,
        *,
        lease_seconds: int = 1800,
    ) -> bool:
        """Extend an active run lease so healthy long-running work is not reclaimed."""
        lease_until = _utcnow() + timedelta(seconds=max(30, lease_seconds))
        stmt = (
            update(Run)
            .where(
                Run.id == run_id,
                Run.tenant_id == tenant_id,
                Run.status == "running",
                Run.execution_token == execution_token,
            )
            .values(execution_lease_until=lease_until)
            .execution_options(synchronize_session=False)
        )
        result = await self.session.execute(stmt)
        return bool(result.rowcount)

    async def complete_execution(
        self,
        tenant_id: str,
        run_id: str,
        execution_token: str,
        *,
        selected_agent: str,
        route: str,
        output_text: str,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        latency_ms: int = 0,
        cost_usd: float = 0.0,
    ) -> Optional[Run]:
        """Atomically complete only the currently owned, non-cancelled execution."""
        stmt = (
            update(Run)
            .where(
                Run.id == run_id,
                Run.tenant_id == tenant_id,
                Run.status == "running",
                Run.cancel_requested.is_(False),
                Run.execution_token == execution_token,
            )
            .values(
                status="completed",
                selected_agent=selected_agent,
                route=route,
                output_text=output_text,
                prompt_tokens=Run.prompt_tokens + max(0, prompt_tokens),
                completion_tokens=Run.completion_tokens
                + max(0, completion_tokens),
                latency_ms=case(
                    (Run.latency_ms < max(0, latency_ms), max(0, latency_ms)),
                    else_=Run.latency_ms,
                ),
                cost_usd=Run.cost_usd + max(0.0, cost_usd),
                execution_lease_until=None,
                execution_token=None,
                version=Run.version + 1,
            )
            .returning(Run.id)
            .execution_options(synchronize_session=False)
        )
        completed_id = (await self.session.execute(stmt)).scalar_one_or_none()
        if completed_id is None:
            return None
        self.session.expire_all()
        return await self.get(tenant_id, completed_id)

    async def fail_execution(
        self,
        tenant_id: str,
        run_id: str,
        execution_token: str,
        *,
        error_code: str,
    ) -> Optional[Run]:
        """Atomically fail only the currently owned, non-cancelled execution."""
        stmt = (
            update(Run)
            .where(
                Run.id == run_id,
                Run.tenant_id == tenant_id,
                Run.status == "running",
                Run.cancel_requested.is_(False),
                Run.execution_token == execution_token,
            )
            .values(
                status="failed",
                error_code=error_code,
                execution_lease_until=None,
                execution_token=None,
                version=Run.version + 1,
            )
            .returning(Run.id)
            .execution_options(synchronize_session=False)
        )
        failed_id = (await self.session.execute(stmt)).scalar_one_or_none()
        if failed_id is None:
            return None
        self.session.expire_all()
        return await self.get(tenant_id, failed_id)

    async def acknowledge_cancellation(
        self,
        tenant_id: str,
        run_id: str,
        execution_token: str,
    ) -> Optional[Run]:
        """Terminalize cancellation only for the current execution owner."""
        stmt = (
            update(Run)
            .where(
                Run.id == run_id,
                Run.tenant_id == tenant_id,
                Run.status == "running",
                Run.cancel_requested.is_(True),
                Run.execution_token == execution_token,
            )
            .values(
                status="cancelled",
                execution_lease_until=None,
                execution_token=None,
                version=Run.version + 1,
            )
            .returning(Run.id)
            .execution_options(synchronize_session=False)
        )
        cancelled_id = (await self.session.execute(stmt)).scalar_one_or_none()
        if cancelled_id is None:
            return None
        self.session.expire_all()
        return await self.get(tenant_id, cancelled_id)

    async def is_cancelled(self, tenant_id: str, run_id: str) -> bool:
        run = await self.get_or_none(tenant_id, run_id)
        if run is None:
            return False
        return run.cancel_requested or run.status == "cancelled"

    # ── Events (monotonic per-run ids) ──────────────────────────────────────
    async def append_event(
        self,
        tenant_id: str,
        run_id: str,
        event_type: str,
        data: Optional[dict] = None,
        *,
        execution_token: Optional[str] = None,
    ) -> RunEvent:
        """Append an event with the next monotonic per-run ``event_id``.

        The ``run.event_seq`` counter is the id source; a unique
        ``(run_id, event_id)`` constraint plus a savepoint retry makes this safe
        even if two writers race for the same run.
        """
        ownership_predicates = (
            (
                Run.status == "running",
                Run.execution_token == execution_token,
            )
            if execution_token is not None
            else ()
        )
        next_id = (
            await self.session.execute(
                update(Run)
                .where(
                    Run.id == run_id,
                    Run.tenant_id == tenant_id,
                    *ownership_predicates,
                )
                .values(event_seq=Run.event_seq + 1)
                .returning(Run.event_seq)
            )
        ).scalar_one_or_none()
        if next_id is None:
            if execution_token is not None:
                raise ConflictError("run execution ownership was lost")
            from agentsystem.errors import NotFoundError

            raise NotFoundError("run not found")
        event = RunEvent(
            tenant_id=tenant_id,
            run_id=run_id,
            event_id=next_id,
            type=event_type,
            data=data or {},
        )
        self.session.add(event)
        await self.session.flush()
        return event

    async def list_events(
        self,
        tenant_id: str,
        run_id: str,
        *,
        after_event_id: int = 0,
        limit: int = 1000,
    ) -> list[RunEvent]:
        """Return run events with ``event_id > after_event_id`` in order.

        ``after_event_id`` powers SSE resumption via ``Last-Event-ID``.
        """
        # Scope check first: raises 404 if the run is not the caller's.
        await self.get(tenant_id, run_id)
        result = await self.session.execute(
            select(RunEvent)
            .where(
                RunEvent.run_id == run_id,
                RunEvent.event_id > after_event_id,
            )
            .order_by(RunEvent.event_id.asc())
            .limit(limit)
        )
        return list(result.scalars().all())


class PlanRepository(BaseRepository):
    """Plans, steps, and plan events for plan-execute-review workflows."""

    async def create_plan(
        self, ctx: RunContext, *, title: str = ""
    ) -> Plan:
        plan = Plan(
            tenant_id=ctx.tenant_id,
            workspace_id=ctx.workspace_id,
            run_id=ctx.run_id,
            status="pending",
            title=title or None,
        )
        self.session.add(plan)
        await self.session.flush()
        return plan

    async def add_step(
        self,
        tenant_id: str,
        plan_id: str,
        *,
        seq: int,
        title: str,
        owner_agent: str = "",
    ) -> PlanStep:
        plan = await self.session.get(Plan, plan_id)
        self._check_scope(plan, tenant_id=tenant_id, kind="plan")
        step = PlanStep(
            tenant_id=tenant_id,
            plan_id=plan_id,
            seq=seq,
            title=title,
            owner_agent=owner_agent or None,
            status="pending",
        )
        self.session.add(step)
        await self.session.flush()
        return step

    async def set_step_status(
        self, tenant_id: str, step_id: str, status: str
    ) -> PlanStep:
        step = await self.session.get(PlanStep, step_id)
        if step is None or step.tenant_id != tenant_id:
            from agentsystem.errors import NotFoundError

            raise NotFoundError("plan step not found")
        step.status = status
        await self.session.flush()
        return step

    async def set_plan_status(
        self, tenant_id: str, plan_id: str, status: str
    ) -> Plan:
        plan = await self.session.get(Plan, plan_id)
        self._check_scope(plan, tenant_id=tenant_id, kind="plan")
        plan.status = status
        await self.session.flush()
        return plan

    async def add_event(
        self, tenant_id: str, plan_id: str, kind: str, payload: Optional[dict] = None
    ) -> PlanEvent:
        plan = await self.session.get(Plan, plan_id)
        self._check_scope(plan, tenant_id=tenant_id, kind="plan")
        event = PlanEvent(
            tenant_id=tenant_id,
            plan_id=plan_id,
            kind=kind,
            payload=payload or {},
        )
        self.session.add(event)
        await self.session.flush()
        return event

    async def get_plan_for_run(
        self, tenant_id: str, run_id: str
    ) -> Optional[Plan]:
        result = await self.session.execute(
            select(Plan).where(
                Plan.tenant_id == tenant_id, Plan.run_id == run_id
            )
        )
        return result.scalar_one_or_none()

    async def list_steps(self, tenant_id: str, plan_id: str) -> list[PlanStep]:
        result = await self.session.execute(
            select(PlanStep)
            .where(PlanStep.tenant_id == tenant_id, PlanStep.plan_id == plan_id)
            .order_by(PlanStep.seq.asc())
        )
        return list(result.scalars().all())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


__all__ = ["PlanRepository", "RunRepository"]
