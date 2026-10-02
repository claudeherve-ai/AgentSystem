"""AgentSystem production backend foundation.

This package provides the durable, multi-tenant backend for AgentSystem:

* :mod:`agentsystem.context` — the immutable :class:`RunContext` that carries
  ``tenant_id``, ``user_id``, ``workspace_id``, ``project_id``, ``session_id``,
  ``run_id``, ``request_id`` and ``roles`` through every request and run.
* :mod:`agentsystem.errors` — a single structured error envelope that never
  leaks raw provider exceptions.
* :mod:`agentsystem.settings` — explicit, fail-closed backend configuration.
* :mod:`agentsystem.db` — SQLAlchemy 2 async models, engine, and session
  management (PostgreSQL in production, SQLite for dev/test).
* :mod:`agentsystem.repositories` — tenant/workspace-scoped repositories with
  exactly-once approval semantics.
* :mod:`agentsystem.services` — run service, identity extraction, rate limiting,
  and artifact storage.
* :mod:`agentsystem.durable` — Durable Task Scheduler adapter with a
  deterministic local executor for dev/test.
* :mod:`agentsystem.sandbox` — the Dynamic Sessions code-interpreter adapter that
  fails closed instead of falling back to a host subprocess.

Existing agent, tool, routing, and enforcement modules remain reusable; this
package layers durability and multi-tenant isolation around them without
rewriting them.
"""

from agentsystem.context import Principal, RunContext, new_id
from agentsystem.errors import (
    AgentSystemError,
    ConflictError,
    ErrorEnvelope,
    NotFoundError,
    ProviderError,
    UnauthorizedError,
    ValidationError,
    error_envelope,
    sanitize_exception,
)

__all__ = [
    "AgentSystemError",
    "ConflictError",
    "ErrorEnvelope",
    "NotFoundError",
    "Principal",
    "ProviderError",
    "RunContext",
    "UnauthorizedError",
    "ValidationError",
    "error_envelope",
    "new_id",
    "sanitize_exception",
]
