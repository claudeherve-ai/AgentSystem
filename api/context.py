"""Request-scoped identity → RunContext resolution for API routes.

The identity middleware attaches an authenticated
:class:`agentsystem.context.Principal` to ``request.state.principal``. Route
handlers call :func:`resolve_context` to provision that principal into durable
rows and obtain an ISOLATED :class:`~agentsystem.context.RunContext` for the
request (honoring an explicit ``session_id`` for conversation continuity).
"""

from __future__ import annotations

from typing import Optional

from fastapi import Request

from agentsystem.context import Principal
from agentsystem.db.session import session_scope
from agentsystem.errors import UnauthorizedError
from agentsystem.repositories import IdentityRepository


def get_principal(request: Request) -> Principal:
    principal = getattr(request.state, "principal", None)
    if principal is None:
        raise UnauthorizedError("authentication is required")
    return principal


async def resolve_context(
    request: Request,
    *,
    session_id: Optional[str] = None,
    workspace: str = "default",
    project: str = "default",
):
    """Provision the request principal into a durable, isolated RunContext."""
    principal = get_principal(request)
    request_id = getattr(request.state, "request_id", None)
    async with session_scope() as session:
        identity = IdentityRepository(session)
        return await identity.provision_context(
            principal,
            workspace_name=workspace,
            project_name=project,
            session_id=session_id,
            request_id=request_id,
        )


__all__ = ["get_principal", "resolve_context"]
