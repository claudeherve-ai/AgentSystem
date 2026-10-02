"""Shared fixtures for the durable-backend (Workstream B/C) test suite.

All fixtures are opt-in (never autouse) so the pre-existing tests are unaffected.
The ``db`` fixture wires an isolated in-memory SQLite database into the process
engine so repositories, services, and the API run against a fresh schema per
test with no external services.
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass, field
from typing import Any, Optional

import pytest

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool


@pytest.fixture
async def db():
    """Fresh in-memory SQLite engine wired into the process, per test."""
    from agentsystem.db.session import configure_engine, init_models, reset_engine

    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    configure_engine(engine)
    await init_models()
    try:
        yield engine
    finally:
        await reset_engine()


@pytest.fixture
def clean_settings(monkeypatch):
    """Reset the settings cache and provide a helper to set env + reload."""
    from agentsystem.settings import get_settings, reset_settings_cache

    reset_settings_cache()

    def _apply(**env: str):
        for key, value in env.items():
            monkeypatch.setenv(key, value)
        reset_settings_cache()
        return get_settings()

    yield _apply
    reset_settings_cache()


# ── Fake orchestrator (no model credentials required) ───────────────────────
@dataclass
class FakeSessionState:
    session_id: str
    case_context: dict = field(default_factory=dict)
    turns: list[str] = field(default_factory=list)


@dataclass
class FakeTurnResult:
    text: str
    agents_used: list = field(default_factory=list)
    selected_agent: Optional[str] = None
    prompt_tokens: int = 0
    completion_tokens: int = 0


class FakeOrchestrator:
    """Deterministic stand-in for the real orchestrator.

    Records the (task, session_id) it saw so tests can assert isolation, and
    can be configured to raise to exercise the sanitized error path.
    """

    agent_names: list[str] = []

    def __init__(self, *, answer: str = "ok", agents=None, raise_exc: Exception = None):
        self._answer = answer
        self._agents = agents or ["FinanceAgent"]
        self._raise = raise_exc
        self.calls: list[tuple[str, str]] = []

    def new_session_state(
        self,
        session_id: Optional[str] = None,
        persisted_state: Optional[dict[str, Any]] = None,
    ) -> FakeSessionState:
        persisted_state = persisted_state or {}
        return FakeSessionState(
            session_id=session_id or "fake",
            case_context=dict(persisted_state.get("case_context", {})),
            turns=list(persisted_state.get("turns", [])),
        )

    def serialize_session_state(self, state: FakeSessionState) -> dict[str, Any]:
        return {
            "case_context": dict(state.case_context),
            "turns": list(state.turns),
        }

    async def run_turn(self, task, *, session_state=None, context=None) -> FakeTurnResult:
        self.calls.append((task, getattr(session_state, "session_id", None)))
        if self._raise is not None:
            raise self._raise
        session_state.turns.append(task)
        return FakeTurnResult(
            text=f"{self._answer}: {task}",
            agents_used=list(self._agents),
            selected_agent=self._agents[0] if self._agents else None,
            prompt_tokens=3,
            completion_tokens=5,
        )


@pytest.fixture
def fake_orchestrator():
    return FakeOrchestrator()


@pytest.fixture
def run_service(fake_orchestrator):
    """RunService bound to the fake orchestrator + local durable executor."""
    from agentsystem.durable import LocalDurableExecutor
    from agentsystem.services.run_service import RunService

    return RunService(
        orchestrator_provider=lambda: fake_orchestrator,
        durable_executor=LocalDurableExecutor(),
    )


# ── Helpers ─────────────────────────────────────────────────────────────────
def make_principal(tenant: str = "t1", user: str = "u1", roles=("owner",)):
    from agentsystem.context import Principal

    return Principal(
        tenant_id=tenant, user_id=user, roles=tuple(roles), auth_method="api_key"
    )


async def provision(principal, *, session_id=None, run_id=None):
    from agentsystem.db.session import session_scope
    from agentsystem.repositories import IdentityRepository

    async with session_scope() as session:
        return await IdentityRepository(session).provision_context(
            principal, session_id=session_id, run_id=run_id
        )


def easy_auth_header(*, oid: str, tid: str, roles=(), name: str = "user") -> str:
    """Build a base64 X-MS-CLIENT-PRINCIPAL payload like the Easy Auth sidecar."""
    claims = [
        {"typ": "http://schemas.microsoft.com/identity/claims/objectidentifier", "val": oid},
        {"typ": "http://schemas.microsoft.com/identity/claims/tenantid", "val": tid},
        {"typ": "name", "val": name},
    ]
    for role in roles:
        claims.append({"typ": "roles", "val": role})
    payload = {"auth_typ": "aad", "claims": claims}
    return base64.b64encode(json.dumps(payload).encode("utf-8")).decode("ascii")


@pytest.fixture
def principal_factory():
    return make_principal


@pytest.fixture
def provision_ctx():
    return provision


@pytest.fixture
def easy_auth():
    return easy_auth_header
