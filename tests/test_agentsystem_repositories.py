"""Repository isolation, idempotency, and exactly-once approval race tests."""

from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agentsystem.db.session import session_scope
from agentsystem.errors import NotFoundError
from agentsystem.repositories import (
    ApprovalRepository,
    IdentityRepository,
    IdempotencyRepository,
    MemoryRepository,
    RunRepository,
    SessionRepository,
)


# ── Cross-tenant repository scope isolation ─────────────────────────────────
async def test_run_scope_isolation(db, principal_factory, provision_ctx):
    ctx1 = await provision_ctx(principal_factory("tenantA", "userA"), session_id="s1", run_id="r1")
    ctx2 = await provision_ctx(principal_factory("tenantB", "userB"), session_id="s2", run_id="r2")

    async with session_scope() as s:
        await RunRepository(s).create(ctx1, input_text="a")
    # tenantB cannot read tenantA's run — it 404s, never leaks.
    async with session_scope() as s:
        with pytest.raises(NotFoundError):
            await RunRepository(s).get(ctx2.tenant_id, "r1")
        # get_or_none returns None cross-tenant (no leak).
        assert await RunRepository(s).get_or_none(ctx2.tenant_id, "r1") is None


async def test_memory_scoped_per_user(db, principal_factory, provision_ctx):
    ctx1 = await provision_ctx(principal_factory("T", "userA"))
    ctx2 = await provision_ctx(principal_factory("T", "userB"))
    async with session_scope() as s:
        await MemoryRepository(s).upsert(ctx1, key="fav", value="green")
    async with session_scope() as s:
        # userB in the SAME tenant does not see userA's memory.
        assert await MemoryRepository(s).get(ctx2, "fav") is None
        got = await MemoryRepository(s).get(ctx1, "fav")
        assert got is not None and got.value == "green"


async def test_session_id_honored_but_not_hijackable(db, principal_factory, provision_ctx):
    ctx1 = await provision_ctx(principal_factory("T", "userA"), session_id="shared-id")
    ctx2 = await provision_ctx(principal_factory("T", "userB"), session_id="shared-id")
    async with session_scope() as s:
        sess1 = await SessionRepository(s).ensure_for_context(ctx1)
    async with session_scope() as s:
        # Opaque foreign ids are rejected instead of silently re-attached.
        with pytest.raises(NotFoundError):
            await SessionRepository(s).ensure_for_context(ctx2)


async def test_concurrent_first_use_provisioning_is_unique(
    tmp_path, principal_factory
):
    from sqlalchemy import func, select
    from sqlalchemy.ext.asyncio import create_async_engine

    from agentsystem.db.models import Membership, Project, Tenant, User, Workspace
    from agentsystem.db.session import configure_engine, init_models, reset_engine

    database = tmp_path / "provisioning.db"
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{database}",
        connect_args={"timeout": 10},
    )
    configure_engine(engine)
    await init_models()
    principal = principal_factory("concurrent-tenant", "concurrent-user")

    async def provision_once():
        async with session_scope() as session:
            return await IdentityRepository(session).provision_context(principal)

    try:
        contexts = await asyncio.gather(*[provision_once() for _ in range(8)])
        assert len({context.tenant_id for context in contexts}) == 1
        assert len({context.user_id for context in contexts}) == 1
        assert len({context.workspace_id for context in contexts}) == 1
        assert len({context.project_id for context in contexts}) == 1

        async with session_scope() as session:
            for model in (Tenant, User, Workspace, Membership, Project):
                count = await session.scalar(select(func.count()).select_from(model))
                assert count == 1
    finally:
        await reset_engine()


# ── Idempotency ─────────────────────────────────────────────────────────────
async def test_idempotency_first_writer_wins(db, principal_factory, provision_ctx):
    await provision_ctx(principal_factory("T", "U"))
    async with session_scope() as s:
        claimed, ref = await IdempotencyRepository(s).claim("T", "run", "k1", result_ref="run-1")
        assert claimed is True and ref is None
    async with session_scope() as s:
        claimed, ref = await IdempotencyRepository(s).claim("T", "run", "k1")
        assert claimed is False and ref == "run-1"


async def test_run_idempotent_create(db, principal_factory, provision_ctx):
    ctx = await provision_ctx(principal_factory("T", "U"), run_id="r1")
    async with session_scope() as s:
        r1 = await RunRepository(s).create(ctx, input_text="x", idempotency_key="idem-1")
    ctx2 = ctx.with_run("r2")
    async with session_scope() as s:
        r2 = await RunRepository(s).create(ctx2, input_text="x", idempotency_key="idem-1")
    assert r1.id == r2.id  # second create returned the first run


async def test_run_idempotency_rejects_different_payload(
    db, principal_factory, provision_ctx
):
    from agentsystem.errors import ConflictError

    ctx = await provision_ctx(principal_factory("T", "U"), run_id="r1")
    async with session_scope() as s:
        await RunRepository(s).create(
            ctx, input_text="first", idempotency_key="idem-1"
        )
    async with session_scope() as s:
        with pytest.raises(ConflictError):
            await RunRepository(s).create(
                ctx.with_run("r2"),
                input_text="different",
                idempotency_key="idem-1",
            )


# ── Exactly-once approval decision (race) ───────────────────────────────────
async def test_approval_decided_exactly_once(db, principal_factory, provision_ctx):
    ctx = await provision_ctx(principal_factory("T", "U"))
    async with session_scope() as s:
        appr = await ApprovalRepository(s).create(
            ctx, agent_name="EmailAgent", action="send_email", ttl_seconds=300
        )
        approval_id = appr.id

    async def decide(approved: bool):
        async with session_scope() as s:
            return await ApprovalRepository(s).decide(
                ctx.tenant_id, approval_id, approved=approved
            )

    # Fire many concurrent contradictory decisions.
    results = await asyncio.gather(
        *[decide(i % 2 == 0) for i in range(12)]
    )
    decided = [r for r in results if r.outcome == "decided"]
    conflicts = [r for r in results if r.outcome == "conflict"]
    assert len(decided) == 1, "exactly one decision must win"
    assert len(conflicts) == len(results) - 1
    # The persisted row is terminal and matches the winner.
    async with session_scope() as s:
        final = await ApprovalRepository(s).get(ctx.tenant_id, approval_id)
    assert final.status in ("approved", "rejected")


async def test_expired_approval_cannot_be_decided(db, principal_factory, provision_ctx):
    ctx = await provision_ctx(principal_factory("T", "U"))
    async with session_scope() as s:
        appr = await ApprovalRepository(s).create(
            ctx, agent_name="A", action="x", ttl_seconds=1
        )
        appr.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        aid = appr.id
    async with session_scope() as s:
        expired = await ApprovalRepository(s).expire_if_due(ctx.tenant_id, aid)
    assert expired.status == "expired"
    async with session_scope() as s:
        decision = await ApprovalRepository(s).decide(ctx.tenant_id, aid, approved=True)
    assert decision.outcome == "conflict"


async def test_future_approval_is_not_expired(
    db, principal_factory, provision_ctx
):
    ctx = await provision_ctx(principal_factory("T", "U"))
    async with session_scope() as s:
        appr = await ApprovalRepository(s).create(
            ctx, agent_name="A", action="x", ttl_seconds=3600
        )
        aid = appr.id
    async with session_scope() as s:
        current = await ApprovalRepository(s).expire_if_due(ctx.tenant_id, aid)
    assert current.status == "pending"


async def test_approval_cross_tenant_not_found(db, principal_factory, provision_ctx):
    ctx1 = await provision_ctx(principal_factory("T1", "U1"))
    ctx2 = await provision_ctx(principal_factory("T2", "U2"))
    async with session_scope() as s:
        appr = await ApprovalRepository(s).create(ctx1, agent_name="A", action="x")
        aid = appr.id
    async with session_scope() as s:
        decision = await ApprovalRepository(s).decide(ctx2.tenant_id, aid, approved=True)
    assert decision.outcome == "not_found"
