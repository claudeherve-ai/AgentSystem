"""Artifact metadata repository (payload bytes live in the artifact store)."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import select

from agentsystem.context import RunContext
from agentsystem.db.models import Artifact
from agentsystem.repositories.base import BaseRepository


class ArtifactRepository(BaseRepository):
    """Durable artifact metadata. No SAS URLs or secrets are ever stored."""

    async def create(
        self,
        ctx: RunContext,
        *,
        name: str,
        content_type: str,
        size_bytes: int,
        storage_backend: str,
        storage_key: str,
        sha256: str = "",
        run_id: Optional[str] = None,
    ) -> Artifact:
        artifact = Artifact(
            tenant_id=ctx.tenant_id,
            workspace_id=ctx.workspace_id,
            run_id=run_id or ctx.run_id,
            name=name,
            content_type=content_type,
            size_bytes=size_bytes,
            storage_backend=storage_backend,
            storage_key=storage_key,
            sha256=sha256 or None,
        )
        self.session.add(artifact)
        await self.session.flush()
        return artifact

    async def get(self, tenant_id: str, artifact_id: str) -> Artifact:
        obj = await self.session.get(Artifact, artifact_id)
        return self._check_scope(obj, tenant_id=tenant_id, kind="artifact")

    async def list_for_run(
        self, tenant_id: str, run_id: str, limit: int = 100
    ) -> list[Artifact]:
        result = await self.session.execute(
            select(Artifact)
            .where(Artifact.tenant_id == tenant_id, Artifact.run_id == run_id)
            .order_by(Artifact.created_at.asc())
            .limit(limit)
        )
        return list(result.scalars().all())


__all__ = ["ArtifactRepository"]
