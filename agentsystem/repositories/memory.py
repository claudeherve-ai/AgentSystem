"""Memory and memory-provenance repositories (per-user, tenant-scoped)."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import select

from agentsystem.context import RunContext
from agentsystem.db.models import Memory, MemoryProvenance
from agentsystem.repositories.base import BaseRepository


class MemoryRepository(BaseRepository):
    """Durable per-user memory with provenance tracking."""

    async def upsert(
        self,
        ctx: RunContext,
        *,
        key: str,
        value: str,
        category: str = "",
        source: str = "explicit",
    ) -> Memory:
        result = await self.session.execute(
            select(Memory).where(
                Memory.tenant_id == ctx.tenant_id,
                Memory.workspace_id == ctx.workspace_id,
                Memory.user_id == ctx.user_id,
                Memory.key == key,
            )
        )
        memory = result.scalar_one_or_none()
        if memory is None:
            memory = Memory(
                tenant_id=ctx.tenant_id,
                workspace_id=ctx.workspace_id,
                user_id=ctx.user_id,
                key=key,
                value=value,
                category=category or None,
            )
            self.session.add(memory)
        else:
            memory.value = value
            if category:
                memory.category = category
        await self.session.flush()
        await self.add_provenance(ctx, memory.id, source=source)
        return memory

    async def add_provenance(
        self, ctx: RunContext, memory_id: str, *, source: str, note: str = ""
    ) -> MemoryProvenance:
        prov = MemoryProvenance(
            tenant_id=ctx.tenant_id,
            memory_id=memory_id,
            source=source,
            run_id=ctx.run_id,
            note=note or None,
        )
        self.session.add(prov)
        await self.session.flush()
        return prov

    async def get(
        self, ctx: RunContext, key: str
    ) -> Optional[Memory]:
        result = await self.session.execute(
            select(Memory).where(
                Memory.tenant_id == ctx.tenant_id,
                Memory.workspace_id == ctx.workspace_id,
                Memory.user_id == ctx.user_id,
                Memory.key == key,
            )
        )
        return result.scalar_one_or_none()

    async def list_for_user(
        self, ctx: RunContext, limit: int = 200
    ) -> list[Memory]:
        result = await self.session.execute(
            select(Memory)
            .where(
                Memory.tenant_id == ctx.tenant_id,
                Memory.workspace_id == ctx.workspace_id,
                Memory.user_id == ctx.user_id,
            )
            .order_by(Memory.updated_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def delete(self, ctx: RunContext, key: str) -> bool:
        memory = await self.get(ctx, key)
        if memory is None:
            return False
        await self.session.delete(memory)
        await self.session.flush()
        return True

    async def provenance_for(
        self, tenant_id: str, memory_id: str
    ) -> list[MemoryProvenance]:
        result = await self.session.execute(
            select(MemoryProvenance)
            .where(
                MemoryProvenance.tenant_id == tenant_id,
                MemoryProvenance.memory_id == memory_id,
            )
            .order_by(MemoryProvenance.created_at.asc())
        )
        return list(result.scalars().all())


__all__ = ["MemoryRepository"]
