"""Base repository with tenant/workspace scope enforcement."""

from __future__ import annotations

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from agentsystem.errors import NotFoundError


class BaseRepository:
    """Common repository plumbing.

    Every concrete repository takes an :class:`AsyncSession`. Scope helpers make
    the tenant/workspace boundary explicit at every read so a caller can never
    accidentally return another tenant's row.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def _check_scope(
        obj,
        *,
        tenant_id: str,
        workspace_id: Optional[str] = None,
        kind: str = "resource",
    ):
        """Return ``obj`` only if it matches the required scope, else 404.

        Returning 404 (never 403) avoids leaking the existence of a resource in
        another tenant.
        """
        if obj is None:
            raise NotFoundError(f"{kind} not found")
        if getattr(obj, "tenant_id", None) != tenant_id:
            raise NotFoundError(f"{kind} not found")
        if workspace_id is not None and getattr(obj, "workspace_id", None) != workspace_id:
            raise NotFoundError(f"{kind} not found")
        return obj


__all__ = ["BaseRepository"]
