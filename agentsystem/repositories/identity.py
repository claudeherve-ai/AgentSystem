"""Identity & org-structure repositories plus principal provisioning.

These repositories manage tenants, users, workspaces, memberships, and projects,
and provide :meth:`IdentityRepository.provision_context` which turns an
authenticated :class:`~agentsystem.context.Principal` into a durable, isolated
:class:`~agentsystem.context.RunContext` (creating the tenant/user/workspace/
project rows on first use). All lookups are tenant-scoped.
"""

from __future__ import annotations

from typing import Optional, TypeVar

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from agentsystem.context import Principal, RunContext, new_id
from agentsystem.db.models import (
    Membership,
    Project,
    Tenant,
    User,
    Workspace,
)
from agentsystem.repositories.base import BaseRepository

IdentityRow = TypeVar(
    "IdentityRow", Tenant, User, Workspace, Membership, Project
)


class IdentityRepository(BaseRepository):
    """Manage tenants, users, workspaces, memberships, and projects."""

    async def _insert_or_get(self, query, candidate: IdentityRow) -> IdentityRow:
        """Insert through a savepoint, or load the concurrent winner."""
        existing = (await self.session.execute(query)).scalar_one_or_none()
        if existing is not None:
            return existing
        try:
            async with self.session.begin_nested():
                self.session.add(candidate)
                await self.session.flush()
        except IntegrityError:
            existing = (await self.session.execute(query)).scalar_one_or_none()
            if existing is None:
                raise
            return existing
        return candidate

    # ── Tenants ─────────────────────────────────────────────────────────────
    async def get_or_create_tenant(
        self, external_id: str, name: str = ""
    ) -> Tenant:
        return await self._insert_or_get(
            select(Tenant).where(Tenant.external_id == external_id),
            Tenant(external_id=external_id, name=name or external_id),
        )

    # ── Users ───────────────────────────────────────────────────────────────
    async def get_or_create_user(
        self,
        tenant_id: str,
        external_id: str,
        *,
        email: str = "",
        display_name: str = "",
    ) -> User:
        return await self._insert_or_get(
            select(User).where(
                User.tenant_id == tenant_id, User.external_id == external_id
            ),
            User(
                tenant_id=tenant_id,
                external_id=external_id,
                email=email or None,
                display_name=display_name or None,
            ),
        )

    # ── Workspaces ──────────────────────────────────────────────────────────
    async def get_or_create_workspace(
        self, tenant_id: str, name: str
    ) -> Workspace:
        return await self._insert_or_get(
            select(Workspace).where(
                Workspace.tenant_id == tenant_id, Workspace.name == name
            ),
            Workspace(tenant_id=tenant_id, name=name),
        )

    async def get_workspace(
        self, tenant_id: str, workspace_id: str
    ) -> Workspace:
        obj = await self.session.get(Workspace, workspace_id)
        return self._check_scope(obj, tenant_id=tenant_id, kind="workspace")

    # ── Memberships ─────────────────────────────────────────────────────────
    async def ensure_membership(
        self,
        tenant_id: str,
        workspace_id: str,
        user_id: str,
        role: str = "member",
    ) -> Membership:
        return await self._insert_or_get(
            select(Membership).where(
                Membership.workspace_id == workspace_id,
                Membership.user_id == user_id,
            ),
            Membership(
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                user_id=user_id,
                role=role,
            ),
        )

    async def is_member(self, workspace_id: str, user_id: str) -> bool:
        result = await self.session.execute(
            select(Membership.id).where(
                Membership.workspace_id == workspace_id,
                Membership.user_id == user_id,
            )
        )
        return result.scalar_one_or_none() is not None

    # ── Projects ────────────────────────────────────────────────────────────
    async def get_or_create_project(
        self, tenant_id: str, workspace_id: str, name: str
    ) -> Project:
        return await self._insert_or_get(
            select(Project).where(
                Project.tenant_id == tenant_id,
                Project.workspace_id == workspace_id,
                Project.name == name,
            ),
            Project(
                tenant_id=tenant_id, workspace_id=workspace_id, name=name
            ),
        )

    async def get_project(self, tenant_id: str, project_id: str) -> Project:
        obj = await self.session.get(Project, project_id)
        return self._check_scope(obj, tenant_id=tenant_id, kind="project")

    # ── Provisioning ────────────────────────────────────────────────────────
    async def provision_context(
        self,
        principal: Principal,
        *,
        workspace_name: str = "default",
        project_name: str = "default",
        session_id: Optional[str] = None,
        run_id: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> RunContext:
        """Materialize a principal into durable rows and a scoped RunContext.

        Idempotent: tenant/user/workspace/project rows are created on first use
        and reused thereafter. Membership is ensured so authorization checks
        succeed for the caller's own workspace.
        """
        tenant = await self.get_or_create_tenant(
            principal.tenant_id, name=principal.tenant_id
        )
        user = await self.get_or_create_user(
            tenant.id,
            principal.user_id,
            email=str(principal.claims.get("email", "")),
            display_name=principal.display_name,
        )
        workspace = await self.get_or_create_workspace(tenant.id, workspace_name)
        await self.ensure_membership(
            tenant.id,
            workspace.id,
            user.id,
            role="owner" if principal.has_role("owner") else "member",
        )
        project = await self.get_or_create_project(
            tenant.id, workspace.id, project_name
        )
        return RunContext(
            tenant_id=tenant.id,
            user_id=user.id,
            workspace_id=workspace.id,
            project_id=project.id,
            session_id=session_id or new_id("sess"),
            run_id=run_id or new_id("run"),
            request_id=request_id or new_id("req"),
            roles=tuple(principal.roles),
            auth_method=principal.auth_method,
        )


__all__ = ["IdentityRepository"]
