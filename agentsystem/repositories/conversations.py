"""Session and message repositories (tenant/workspace-scoped)."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import func, select

from agentsystem.context import RunContext
from agentsystem.db.models import Message, Session
from agentsystem.errors import NotFoundError
from agentsystem.repositories.base import BaseRepository


class SessionRepository(BaseRepository):
    """Durable conversation sessions."""

    async def get(self, tenant_id: str, session_id: str) -> Session:
        obj = await self.session.get(Session, session_id)
        return self._check_scope(obj, tenant_id=tenant_id, kind="session")

    async def get_or_none(
        self, tenant_id: str, session_id: str
    ) -> Optional[Session]:
        obj = await self.session.get(Session, session_id)
        if obj is None or obj.tenant_id != tenant_id:
            return None
        return obj

    async def ensure_for_context(self, ctx: RunContext, title: str = "") -> Session:
        """Return the context's session, creating it under the caller's scope.

        Honors ``ctx.session_id``: if a session with that id already exists it
        MUST belong to the caller's tenant/user (otherwise a fresh row is
        created under the caller — one user can never attach to another user's
        session id).
        """
        existing = await self.session.get(Session, ctx.session_id)
        if existing is not None:
            if existing.tenant_id != ctx.tenant_id or existing.user_id != ctx.user_id:
                # Do not reveal whether the opaque id belongs to another caller.
                raise NotFoundError("session not found")
            return existing
        session = Session(
            id=ctx.session_id,
            tenant_id=ctx.tenant_id,
            workspace_id=ctx.workspace_id,
            project_id=ctx.project_id,
            user_id=ctx.user_id,
            title=title or None,
        )
        self.session.add(session)
        await self.session.flush()
        return session

    async def list_for_user(
        self, tenant_id: str, user_id: str, limit: int = 50
    ) -> list[Session]:
        result = await self.session.execute(
            select(Session)
            .where(Session.tenant_id == tenant_id, Session.user_id == user_id)
            .order_by(Session.updated_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def load_agent_state(self, ctx: RunContext) -> dict:
        """Load framework conversation state under the full caller scope."""
        obj = await self.get(ctx.tenant_id, ctx.session_id)
        if (
            obj.user_id != ctx.user_id
            or obj.workspace_id != ctx.workspace_id
            or obj.project_id != ctx.project_id
        ):
            raise NotFoundError("session not found")
        return dict(obj.agent_state or {})

    async def save_agent_state(self, ctx: RunContext, state: dict) -> None:
        """Persist a JSON-serializable framework conversation snapshot."""
        obj = await self.get(ctx.tenant_id, ctx.session_id)
        if (
            obj.user_id != ctx.user_id
            or obj.workspace_id != ctx.workspace_id
            or obj.project_id != ctx.project_id
        ):
            raise NotFoundError("session not found")
        obj.agent_state = state
        await self.session.flush()


class MessageRepository(BaseRepository):
    """Ordered conversation messages within a session."""

    async def _next_seq(self, session_id: str) -> int:
        result = await self.session.execute(
            select(func.coalesce(func.max(Message.seq), 0)).where(
                Message.session_id == session_id
            )
        )
        return int(result.scalar_one()) + 1

    async def add(
        self,
        ctx: RunContext,
        role: str,
        content: str,
        *,
        agent_name: str = "",
        run_id: Optional[str] = None,
    ) -> Message:
        message = Message(
            tenant_id=ctx.tenant_id,
            workspace_id=ctx.workspace_id,
            session_id=ctx.session_id,
            run_id=run_id,
            seq=await self._next_seq(ctx.session_id),
            role=role,
            content=content,
            agent_name=agent_name or None,
        )
        self.session.add(message)
        await self.session.flush()
        return message

    async def list_for_session(
        self, tenant_id: str, session_id: str, limit: int = 200
    ) -> list[Message]:
        result = await self.session.execute(
            select(Message)
            .where(
                Message.tenant_id == tenant_id,
                Message.session_id == session_id,
            )
            .order_by(Message.seq.asc())
            .limit(limit)
        )
        return list(result.scalars().all())


__all__ = ["MessageRepository", "SessionRepository"]
