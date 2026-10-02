"""Evaluation, audit, and idempotency repositories."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from agentsystem.context import RunContext
from agentsystem.db.models import AuditEvent, Evaluation, IdempotencyKey
from agentsystem.repositories.base import BaseRepository


class EvaluationRepository(BaseRepository):
    """Durable evaluation results attached to runs."""

    async def record(
        self,
        ctx: RunContext,
        *,
        suite: str,
        metric: str,
        score: float,
        passed: bool,
        detail: Optional[dict] = None,
        run_id: Optional[str] = None,
    ) -> Evaluation:
        evaluation = Evaluation(
            tenant_id=ctx.tenant_id,
            run_id=run_id or ctx.run_id,
            suite=suite,
            metric=metric,
            score=score,
            passed=passed,
            detail=detail or {},
        )
        self.session.add(evaluation)
        await self.session.flush()
        return evaluation

    async def list_for_run(
        self, tenant_id: str, run_id: str
    ) -> list[Evaluation]:
        result = await self.session.execute(
            select(Evaluation)
            .where(Evaluation.tenant_id == tenant_id, Evaluation.run_id == run_id)
            .order_by(Evaluation.created_at.asc())
        )
        return list(result.scalars().all())


class AuditRepository(BaseRepository):
    """Append-only audit trail."""

    async def record(
        self,
        ctx: RunContext,
        *,
        action: str,
        actor: str = "",
        target: str = "",
        payload: Optional[dict] = None,
    ) -> AuditEvent:
        event = AuditEvent(
            tenant_id=ctx.tenant_id,
            workspace_id=ctx.workspace_id,
            user_id=ctx.user_id,
            run_id=ctx.run_id,
            action=action,
            actor=actor or ctx.user_id,
            target=target or None,
            payload=payload or {},
        )
        self.session.add(event)
        await self.session.flush()
        return event

    async def list_for_tenant(
        self, tenant_id: str, *, limit: int = 100
    ) -> list[AuditEvent]:
        result = await self.session.execute(
            select(AuditEvent)
            .where(AuditEvent.tenant_id == tenant_id)
            .order_by(AuditEvent.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())


class IdempotencyRepository(BaseRepository):
    """Tenant-scoped idempotency keys with a first-writer-wins guarantee."""

    async def claim(
        self,
        tenant_id: str,
        scope: str,
        key: str,
        *,
        result_ref: str = "",
    ) -> tuple[bool, Optional[str]]:
        """Attempt to claim ``(tenant_id, scope, key)``.

        Returns ``(claimed, existing_result_ref)``. ``claimed`` is ``True`` when
        this caller is the first writer, ``False`` when the key already exists
        (its stored ``result_ref`` is returned so the caller can reuse the prior
        result).
        """
        existing = await self.session.execute(
            select(IdempotencyKey).where(
                IdempotencyKey.tenant_id == tenant_id,
                IdempotencyKey.scope == scope,
                IdempotencyKey.key == key,
            )
        )
        row = existing.scalar_one_or_none()
        if row is not None:
            return False, row.result_ref

        record = IdempotencyKey(
            tenant_id=tenant_id,
            scope=scope,
            key=key,
            result_ref=result_ref or None,
        )
        self.session.add(record)
        try:
            async with self.session.begin_nested():
                await self.session.flush()
        except IntegrityError:
            # Lost the race — return the winner's ref.
            winner = await self.session.execute(
                select(IdempotencyKey).where(
                    IdempotencyKey.tenant_id == tenant_id,
                    IdempotencyKey.scope == scope,
                    IdempotencyKey.key == key,
                )
            )
            existing_row = winner.scalar_one_or_none()
            return False, existing_row.result_ref if existing_row else None
        return True, None


__all__ = [
    "AuditRepository",
    "EvaluationRepository",
    "IdempotencyRepository",
]
