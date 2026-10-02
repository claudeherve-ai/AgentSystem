"""Immutable execution context and authenticated principal.

The :class:`RunContext` is the single object that carries tenant/user/workspace
scope through every HTTP request and every durable run. It is **immutable**
(frozen dataclass) so it can be shared safely across coroutines and never
mutated to leak one user's scope into another user's execution.

A :class:`Principal` is the authenticated identity extracted from the incoming
request (Easy Auth header, verified Entra JWT, or the static service key). It is
converted into a :class:`RunContext` per request/run.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field, replace
from typing import Any, Mapping, Optional

# ── Local / service-mode identity defaults ──────────────────────────────────
# CLI and local callers that are NOT behind an authenticating gateway execute
# under a well-known, ISOLATED local tenant/user. This is never used for API
# requests in production (identity extraction fails closed there instead).
LOCAL_TENANT_ID = "local"
LOCAL_USER_ID = "local-user"
LOCAL_WORKSPACE_ID = "local-workspace"
LOCAL_PROJECT_ID = "local-project"


def new_id(prefix: str = "") -> str:
    """Return a database-safe unique identifier, optionally namespaced.

    Durable identifier columns are ``VARCHAR(32)``. A 96-bit UUID token keeps
    prefixed identifiers within that contract while retaining ample entropy.
    """
    prefix = prefix[:12]
    token_length = 32 if not prefix else 31 - len(prefix)
    token = uuid.uuid4().hex[:token_length]
    return f"{prefix}_{token}" if prefix else token


@dataclass(frozen=True, slots=True)
class Principal:
    """An authenticated caller identity.

    Attributes:
        tenant_id: Tenant boundary the caller belongs to.
        user_id: Stable subject identifier (Entra ``oid``/``sub`` or service id).
        roles: Authorization roles asserted for this caller.
        display_name: Human-friendly name (never used for authorization).
        auth_method: Which extractor produced this principal
            (``easy_auth`` | ``entra_jwt`` | ``api_key`` | ``local``).
        claims: Raw, already-validated claims for audit/debug (never secrets).
    """

    tenant_id: str
    user_id: str
    roles: tuple[str, ...] = ()
    display_name: str = ""
    auth_method: str = "local"
    claims: Mapping[str, Any] = field(default_factory=dict)

    def has_role(self, role: str) -> bool:
        return role in self.roles


@dataclass(frozen=True, slots=True)
class RunContext:
    """Immutable per-request / per-run execution scope.

    Every durable object (session, message, run, event, approval, artifact,
    memory, audit record) is written under this scope, and every repository
    method enforces the ``tenant_id`` / ``workspace_id`` boundary carried here.
    """

    tenant_id: str
    user_id: str
    workspace_id: str
    project_id: str
    session_id: str
    run_id: str
    request_id: str
    roles: tuple[str, ...] = ()
    auth_method: str = "local"

    # ── Construction helpers ────────────────────────────────────────────────
    @classmethod
    def for_local(
        cls,
        *,
        session_id: Optional[str] = None,
        run_id: Optional[str] = None,
        request_id: Optional[str] = None,
        tenant_id: str = LOCAL_TENANT_ID,
        user_id: str = LOCAL_USER_ID,
        workspace_id: str = LOCAL_WORKSPACE_ID,
        project_id: str = LOCAL_PROJECT_ID,
        roles: tuple[str, ...] = ("owner",),
    ) -> "RunContext":
        """Build an ISOLATED local context for CLI / test / offline callers.

        This is the ONLY backward-compatible path for old callers that never
        supplied identity. It is intentionally scoped to a dedicated ``local``
        tenant so it can never collide with a real API tenant.
        """
        return cls(
            tenant_id=tenant_id,
            user_id=user_id,
            workspace_id=workspace_id,
            project_id=project_id,
            session_id=session_id or new_id("sess"),
            run_id=run_id or new_id("run"),
            request_id=request_id or new_id("req"),
            roles=roles,
            auth_method="local",
        )

    @classmethod
    def from_principal(
        cls,
        principal: Principal,
        *,
        workspace_id: str,
        project_id: str,
        session_id: str,
        run_id: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> "RunContext":
        """Derive a run scope from an authenticated principal."""
        return cls(
            tenant_id=principal.tenant_id,
            user_id=principal.user_id,
            workspace_id=workspace_id,
            project_id=project_id,
            session_id=session_id,
            run_id=run_id or new_id("run"),
            request_id=request_id or new_id("req"),
            roles=tuple(principal.roles),
            auth_method=principal.auth_method,
        )

    def with_run(self, run_id: str) -> "RunContext":
        """Return a copy scoped to a specific ``run_id`` (immutably)."""
        return replace(self, run_id=run_id)

    def with_request(self, request_id: str) -> "RunContext":
        """Return a copy carrying a specific ``request_id`` (immutably)."""
        return replace(self, request_id=request_id)

    def has_role(self, role: str) -> bool:
        return role in self.roles

    def as_log_fields(self) -> dict[str, str]:
        """Correlation fields suitable for structured logs / telemetry."""
        return {
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "workspace_id": self.workspace_id,
            "project_id": self.project_id,
            "session_id": self.session_id,
            "run_id": self.run_id,
            "request_id": self.request_id,
        }


__all__ = [
    "LOCAL_PROJECT_ID",
    "LOCAL_TENANT_ID",
    "LOCAL_USER_ID",
    "LOCAL_WORKSPACE_ID",
    "Principal",
    "RunContext",
    "new_id",
]
