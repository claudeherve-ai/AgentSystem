"""Approval repository with exactly-once, atomic-decide semantics.

A decision is applied via a conditional ``UPDATE ... WHERE status='pending'``
(also honoring ``expires_at``), so concurrent approve/reject/expire callers can
never double-decide, and a late decision landing after the deadline can never
sneak a sensitive action through (fail closed). The result of a decision is an
explicit :class:`ApprovalDecision` distinguishing *decided* from *not found*
and *conflict* (already terminal / expired).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select, update

from agentsystem.context import RunContext
from agentsystem.db.models import Approval, ApprovalEvent
from agentsystem.repositories.base import BaseRepository

_MAX_DETAILS_CHARS = 4000


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True)
class ApprovalDecision:
    """Outcome of an atomic decide attempt.

    ``outcome`` is one of ``"decided"``, ``"not_found"``, ``"conflict"``.
    """

    outcome: str
    approval: Optional[Approval] = None

    @property
    def decided(self) -> bool:
        return self.outcome == "decided"


class ApprovalRepository(BaseRepository):
    """Durable human-in-the-loop approvals."""

    async def create(
        self,
        ctx: RunContext,
        *,
        agent_name: str,
        action: str,
        details: str = "",
        ttl_seconds: Optional[int] = None,
        idempotency_key: str = "",
        run_id: Optional[str] = None,
    ) -> Approval:
        """Persist a PENDING approval under the caller's scope.

        When ``idempotency_key`` is supplied and one already exists for this
        tenant, the existing approval is returned (idempotent create).
        """
        if idempotency_key:
            existing = await self._by_idempotency(ctx.tenant_id, idempotency_key)
            if existing is not None:
                return existing
        expires_at: Optional[datetime] = None
        if ttl_seconds and ttl_seconds > 0:
            expires_at = _utcnow() + timedelta(seconds=ttl_seconds)
        approval = Approval(
            tenant_id=ctx.tenant_id,
            workspace_id=ctx.workspace_id,
            run_id=run_id,
            agent_name=agent_name,
            action=action,
            details=(details or "")[:_MAX_DETAILS_CHARS],
            status="pending",
            expires_at=expires_at,
            idempotency_key=idempotency_key or None,
        )
        self.session.add(approval)
        await self.session.flush()
        await self._emit(
            ctx.tenant_id,
            approval.id,
            "created",
            {"agent_name": agent_name, "action": action},
        )
        return approval

    async def _by_idempotency(
        self, tenant_id: str, idempotency_key: str
    ) -> Optional[Approval]:
        result = await self.session.execute(
            select(Approval).where(
                Approval.tenant_id == tenant_id,
                Approval.idempotency_key == idempotency_key,
            )
        )
        return result.scalar_one_or_none()

    async def get(
        self,
        tenant_id: str,
        approval_id: str,
        *,
        workspace_id: Optional[str] = None,
    ) -> Approval:
        obj = await self.session.get(Approval, approval_id)
        approval = self._check_scope(obj, tenant_id=tenant_id, kind="approval")
        if workspace_id and approval.workspace_id != workspace_id:
            from agentsystem.errors import NotFoundError

            raise NotFoundError("approval not found")
        return approval

    async def _reload(self, tenant_id: str, approval_id: str) -> Approval:
        """Re-read a row bypassing the identity-map cache after a bulk UPDATE."""
        obj = await self.session.get(
            Approval, approval_id, populate_existing=True
        )
        return self._check_scope(obj, tenant_id=tenant_id, kind="approval")

    async def get_or_none(
        self, tenant_id: str, approval_id: str
    ) -> Optional[Approval]:
        obj = await self.session.get(Approval, approval_id)
        if obj is None or obj.tenant_id != tenant_id:
            return None
        return obj

    async def list(
        self,
        tenant_id: str,
        *,
        workspace_id: Optional[str] = None,
        status: str = "",
        limit: int = 100,
    ) -> list[Approval]:
        query = select(Approval).where(Approval.tenant_id == tenant_id)
        if workspace_id:
            query = query.where(Approval.workspace_id == workspace_id)
        if status:
            query = query.where(Approval.status == status)
        query = query.order_by(Approval.created_at.desc()).limit(limit)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def decide(
        self,
        tenant_id: str,
        approval_id: str,
        *,
        approved: bool,
        feedback: str = "",
        decided_by: str = "",
    ) -> ApprovalDecision:
        """Atomically decide a PENDING, unexpired approval.

        Returns a decision whose ``outcome`` is:

        * ``decided``   — the update applied; ``approval`` is the terminal row.
        * ``not_found`` — no such approval for this tenant.
        * ``conflict``  — already terminal or expired (no change applied).
        """
        # Existence/scope check first so we can distinguish 404 from 409.
        existing = await self.get_or_none(tenant_id, approval_id)
        if existing is None:
            return ApprovalDecision("not_found")

        now = _utcnow()
        new_status = "approved" if approved else "rejected"
        stmt = (
            update(Approval)
            .where(
                Approval.id == approval_id,
                Approval.tenant_id == tenant_id,
                Approval.status == "pending",
                (Approval.expires_at.is_(None)) | (Approval.expires_at > now),
            )
            .values(
                status=new_status,
                feedback=feedback or "",
                decided_at=now,
                decided_by=decided_by or "",
            )
            .execution_options(synchronize_session=False)
        )
        result = await self.session.execute(stmt)
        if result.rowcount == 0:
            return ApprovalDecision("conflict")
        await self._emit(
            tenant_id,
            approval_id,
            "decided",
            {"status": new_status, "decided_by": decided_by},
        )
        await self.session.flush()
        row = await self._reload(tenant_id, approval_id)
        return ApprovalDecision("decided", row)

    async def expire_if_due(
        self, tenant_id: str, approval_id: str
    ) -> Approval:
        """Atomically expire a still-PENDING approval past its deadline.

        A concurrent decision wins: if the row was just approved/rejected the
        conditional update matches nothing and the (terminal) row is returned.
        """
        now = _utcnow()
        stmt = (
            update(Approval)
            .where(
                Approval.id == approval_id,
                Approval.tenant_id == tenant_id,
                Approval.status == "pending",
                Approval.expires_at.is_not(None),
                Approval.expires_at <= now,
            )
            .values(status="expired", decided_at=now)
            .execution_options(synchronize_session=False)
        )
        result = await self.session.execute(stmt)
        if result.rowcount:
            await self._emit(tenant_id, approval_id, "expired", {})
        await self.session.flush()
        return await self._reload(tenant_id, approval_id)

    async def cancel(
        self, tenant_id: str, approval_id: str, reason: str = ""
    ) -> ApprovalDecision:
        now = _utcnow()
        existing = await self.get_or_none(tenant_id, approval_id)
        if existing is None:
            return ApprovalDecision("not_found")
        stmt = (
            update(Approval)
            .where(
                Approval.id == approval_id,
                Approval.tenant_id == tenant_id,
                Approval.status == "pending",
            )
            .values(status="cancelled", feedback=reason or "", decided_at=now)
            .execution_options(synchronize_session=False)
        )
        result = await self.session.execute(stmt)
        if result.rowcount == 0:
            return ApprovalDecision("conflict")
        await self._emit(tenant_id, approval_id, "cancelled", {"reason": reason})
        await self.session.flush()
        return ApprovalDecision("decided", await self._reload(tenant_id, approval_id))

    async def list_events(
        self, tenant_id: str, approval_id: str
    ) -> list[ApprovalEvent]:
        await self.get(tenant_id, approval_id)  # scope check
        result = await self.session.execute(
            select(ApprovalEvent)
            .where(
                ApprovalEvent.tenant_id == tenant_id,
                ApprovalEvent.approval_id == approval_id,
            )
            .order_by(ApprovalEvent.created_at.asc())
        )
        return list(result.scalars().all())

    async def _emit(
        self, tenant_id: str, approval_id: str, kind: str, payload: dict
    ) -> None:
        self.session.add(
            ApprovalEvent(
                tenant_id=tenant_id,
                approval_id=approval_id,
                kind=kind,
                payload=payload,
            )
        )
        await self.session.flush()


__all__ = ["ApprovalDecision", "ApprovalRepository"]
