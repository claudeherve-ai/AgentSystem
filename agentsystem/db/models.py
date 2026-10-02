"""Durable, tenant-scoped SQLAlchemy 2 ORM models.

Every user-owned record carries a ``tenant_id`` (and, where meaningful, a
``workspace_id``) so repository methods and database constraints can enforce the
multi-tenant boundary. Identifiers are string UUIDs for DB portability between
SQLite (dev/test) and PostgreSQL (production).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from agentsystem.db.base import Base, TimestampMixin, UUIDPkMixin

# ── Status vocabularies ─────────────────────────────────────────────────────
RUN_STATUSES = (
    "pending",
    "running",
    "awaiting_approval",
    "completed",
    "failed",
    "cancelled",
)
RUN_TERMINAL_STATUSES = frozenset({"completed", "failed", "cancelled"})

APPROVAL_STATUSES = ("pending", "approved", "rejected", "expired", "cancelled")
APPROVAL_TERMINAL_STATUSES = frozenset(
    {"approved", "rejected", "expired", "cancelled"}
)

PLAN_STATUSES = ("pending", "running", "completed", "failed", "cancelled")
STEP_STATUSES = ("pending", "running", "completed", "failed", "skipped")


# ── Identity & org structure ────────────────────────────────────────────────
class Tenant(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "tenants"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    external_id: Mapped[Optional[str]] = mapped_column(String(200), unique=True)


class User(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("tenant_id", "external_id", name="users_tenant_external"),
    )

    tenant_id: Mapped[str] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    external_id: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(320))
    display_name: Mapped[Optional[str]] = mapped_column(String(200))


class Workspace(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "workspaces"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="workspaces_tenant_name"),
    )

    tenant_id: Mapped[str] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)


class Membership(UUIDPkMixin, TimestampMixin, Base):
    """A user's role within a workspace (tenant-scoped)."""

    __tablename__ = "memberships"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id", "user_id", name="memberships_workspace_user"
        ),
    )

    tenant_id: Mapped[str] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(50), nullable=False, default="member")


class Project(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "projects"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "workspace_id", "name", name="projects_workspace_name"
        ),
    )

    tenant_id: Mapped[str] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)


# ── Conversation state ──────────────────────────────────────────────────────
class Session(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "sessions"

    tenant_id: Mapped[str] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"), index=True
    )
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[Optional[str]] = mapped_column(String(300))
    agent_state: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class Message(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "messages"
    __table_args__ = (
        Index("ix_messages_session_seq", "session_id", "seq"),
    )

    tenant_id: Mapped[str] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    session_id: Mapped[str] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    run_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("runs.id", ondelete="SET NULL"), index=True
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    role: Mapped[str] = mapped_column(String(30), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    agent_name: Mapped[Optional[str]] = mapped_column(String(120))


# ── Runs & events ───────────────────────────────────────────────────────────
class Run(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "runs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "idempotency_key", name="runs_tenant_idem"),
    )

    tenant_id: Mapped[str] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"), index=True
    )
    session_id: Mapped[str] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="pending", index=True
    )
    input_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    preferred_agent: Mapped[Optional[str]] = mapped_column(String(120))
    selected_agent: Mapped[Optional[str]] = mapped_column(String(120))
    route: Mapped[Optional[str]] = mapped_column(String(60))
    output_text: Mapped[Optional[str]] = mapped_column(Text)
    error_code: Mapped[Optional[str]] = mapped_column(String(60))
    # Monotonic per-run event counter (source of truth for SSE event ids).
    event_seq: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Optimistic-concurrency guard for status transitions.
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    cancel_requested: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    execution_lease_until: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )
    execution_token: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completion_tokens: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(200))

    events: Mapped[list["RunEvent"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class RunEvent(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "run_events"
    __table_args__ = (
        UniqueConstraint("run_id", "event_id", name="run_events_run_event"),
        Index("ix_run_events_run_event", "run_id", "event_id"),
    )

    tenant_id: Mapped[str] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    run_id: Mapped[str] = mapped_column(
        ForeignKey("runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Monotonic, gap-free per-run id used by SSE Last-Event-ID resumption.
    event_id: Mapped[int] = mapped_column(Integer, nullable=False)
    type: Mapped[str] = mapped_column(String(60), nullable=False)
    data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    run: Mapped["Run"] = relationship(back_populates="events")


# ── Plans ───────────────────────────────────────────────────────────────────
class Plan(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "plans"

    tenant_id: Mapped[str] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    run_id: Mapped[str] = mapped_column(
        ForeignKey("runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="pending"
    )
    title: Mapped[Optional[str]] = mapped_column(String(300))

    steps: Mapped[list["PlanStep"]] = relationship(
        back_populates="plan", cascade="all, delete-orphan"
    )


class PlanStep(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "plan_steps"

    tenant_id: Mapped[str] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    plan_id: Mapped[str] = mapped_column(
        ForeignKey("plans.id", ondelete="CASCADE"), nullable=False, index=True
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    title: Mapped[str] = mapped_column(String(400), nullable=False, default="")
    owner_agent: Mapped[Optional[str]] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="pending"
    )

    plan: Mapped["Plan"] = relationship(back_populates="steps")


class PlanEvent(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "plan_events"

    tenant_id: Mapped[str] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    plan_id: Mapped[str] = mapped_column(
        ForeignKey("plans.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(60), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )


# ── Approvals ───────────────────────────────────────────────────────────────
class Approval(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "approvals"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "idempotency_key", name="approvals_tenant_idem"
        ),
        Index("ix_approvals_status", "tenant_id", "status", "created_at"),
    )

    tenant_id: Mapped[str] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    run_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("runs.id", ondelete="SET NULL"), index=True
    )
    agent_name: Mapped[str] = mapped_column(String(120), nullable=False)
    action: Mapped[str] = mapped_column(String(120), nullable=False)
    details: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="pending"
    )
    feedback: Mapped[str] = mapped_column(Text, nullable=False, default="")
    decided_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    decided_by: Mapped[Optional[str]] = mapped_column(String(200))
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(200))


class ApprovalEvent(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "approval_events"

    tenant_id: Mapped[str] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    approval_id: Mapped[str] = mapped_column(
        ForeignKey("approvals.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(60), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )


# ── Artifacts (payload in Blob/local; metadata here) ────────────────────────
class Artifact(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "artifacts"

    tenant_id: Mapped[str] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    run_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("runs.id", ondelete="SET NULL"), index=True
    )
    name: Mapped[str] = mapped_column(String(400), nullable=False)
    content_type: Mapped[str] = mapped_column(
        String(200), nullable=False, default="application/octet-stream"
    )
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Which backend holds the bytes (``local`` | ``blob``) and its opaque key.
    storage_backend: Mapped[str] = mapped_column(String(30), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    sha256: Mapped[Optional[str]] = mapped_column(String(64))


# ── Memory & provenance ─────────────────────────────────────────────────────
class Memory(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "memories"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "workspace_id", "user_id", "key",
            name="memories_scope_key",
        ),
    )

    tenant_id: Mapped[str] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    key: Mapped[str] = mapped_column(String(200), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False, default="")
    category: Mapped[Optional[str]] = mapped_column(String(100))


class MemoryProvenance(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "memory_provenance"

    tenant_id: Mapped[str] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    memory_id: Mapped[str] = mapped_column(
        ForeignKey("memories.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source: Mapped[str] = mapped_column(String(120), nullable=False)
    run_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("runs.id", ondelete="SET NULL"), index=True
    )
    note: Mapped[Optional[str]] = mapped_column(Text)


# ── Evaluations ─────────────────────────────────────────────────────────────
class Evaluation(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "evaluations"

    tenant_id: Mapped[str] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    run_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("runs.id", ondelete="SET NULL"), index=True
    )
    suite: Mapped[str] = mapped_column(String(120), nullable=False)
    metric: Mapped[str] = mapped_column(String(120), nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    detail: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )


# ── Audit ───────────────────────────────────────────────────────────────────
class AuditEvent(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "audit_events"

    tenant_id: Mapped[str] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    workspace_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("workspaces.id", ondelete="SET NULL"), index=True
    )
    user_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    run_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("runs.id", ondelete="SET NULL"), index=True
    )
    action: Mapped[str] = mapped_column(String(120), nullable=False)
    actor: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    target: Mapped[Optional[str]] = mapped_column(String(300))
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )


# ── Idempotency keys ────────────────────────────────────────────────────────
class IdempotencyKey(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "idempotency_keys"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "scope", "key", name="idempotency_tenant_scope_key"
        ),
    )

    tenant_id: Mapped[str] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    scope: Mapped[str] = mapped_column(String(120), nullable=False)
    key: Mapped[str] = mapped_column(String(200), nullable=False)
    result_ref: Mapped[Optional[str]] = mapped_column(String(200))


__all__ = [
    "APPROVAL_STATUSES",
    "APPROVAL_TERMINAL_STATUSES",
    "Approval",
    "ApprovalEvent",
    "Artifact",
    "AuditEvent",
    "Evaluation",
    "IdempotencyKey",
    "Membership",
    "Memory",
    "MemoryProvenance",
    "Message",
    "PLAN_STATUSES",
    "Plan",
    "PlanEvent",
    "PlanStep",
    "Project",
    "RUN_STATUSES",
    "RUN_TERMINAL_STATUSES",
    "STEP_STATUSES",
    "Run",
    "RunEvent",
    "Session",
    "Tenant",
    "User",
    "Workspace",
]
