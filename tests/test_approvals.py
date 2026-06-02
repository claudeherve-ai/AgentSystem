"""
Tests for the durable human-in-the-loop (HITL) approval feature (PR4):
  * tools/approvals_store.py    — durable SQLite store (CRUD + atomic decide).
  * guardrails/approval.py      — APPROVAL_MODE dispatch (auto/interactive/durable).
  * api/routes/approvals.py     — REST decide surface (404 vs 409).
  * tools/azure_search.py       — optional Azure backend stays disabled offline.

All tests run with NO LLM credentials, NO network, and NO live Azure service.
Every store call targets a temporary database (via ``db_path=`` or by
monkeypatching ``approvals_store.APPROVALS_DB``) so the repo's ``memory/`` is
never touched and tests cannot collide.
"""

import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import ApprovalConfig, get_approval_config, get_azure_search_config
from guardrails.approval import HumanApproval
from tools import approvals_store
from tools import azure_search
from tools import rag_store

try:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
except Exception:  # pragma: no cover - httpx missing
    FastAPI = None  # type: ignore[assignment]
    TestClient = None  # type: ignore[assignment]


# ── fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture()
def tmp_db(tmp_path: Path) -> Path:
    """A throwaway approvals DB path inside the test's temp dir."""
    return tmp_path / "approvals_test.db"


@pytest.fixture()
def patched_db(tmp_db: Path, monkeypatch) -> Path:
    """Point the store's default DB at a temp file (for db_path-less callers)."""
    monkeypatch.setattr(approvals_store, "APPROVALS_DB", tmp_db)
    return tmp_db


# ── store: CRUD ──────────────────────────────────────────────────────────────


def test_create_and_get_roundtrip(tmp_db: Path):
    row = approvals_store.create_approval(
        agent_name="finance_agent",
        action="send_invoice",
        details="Invoice #42 to ACME",
        db_path=tmp_db,
    )
    assert row is not None
    assert row.status == "pending"
    assert row.agent_name == "finance_agent"
    assert row.action == "send_invoice"

    fetched = approvals_store.get_approval(row.id, db_path=tmp_db)
    assert fetched is not None
    assert fetched.id == row.id
    assert fetched.details == "Invoice #42 to ACME"

    # create emits a 'created' audit event.
    events = approvals_store.list_events(row.id, db_path=tmp_db)
    assert any(e["kind"] == "created" for e in events)
    print("✅ create/get roundtrip with audit event")


def test_get_unknown_returns_none(tmp_db: Path):
    assert approvals_store.get_approval("appr_does_not_exist", db_path=tmp_db) is None


def test_details_are_capped(tmp_db: Path):
    huge = "x" * (approvals_store._MAX_DETAILS_CHARS + 500)
    row = approvals_store.create_approval(
        agent_name="a", action="b", details=huge, db_path=tmp_db
    )
    assert row is not None
    assert len(row.details) == approvals_store._MAX_DETAILS_CHARS
    print("✅ details capped to _MAX_DETAILS_CHARS")


def test_list_filters_by_status(tmp_db: Path):
    a = approvals_store.create_approval("a", "x", db_path=tmp_db)
    b = approvals_store.create_approval("b", "y", db_path=tmp_db)
    assert a and b
    approvals_store.decide_approval(a.id, approved=True, db_path=tmp_db)

    pending = approvals_store.list_approvals(status="pending", db_path=tmp_db)
    approved = approvals_store.list_approvals(status="approved", db_path=tmp_db)
    everything = approvals_store.list_approvals(db_path=tmp_db)

    assert [r.id for r in pending] == [b.id]
    assert [r.id for r in approved] == [a.id]
    assert {r.id for r in everything} == {a.id, b.id}
    print("✅ list_approvals filters by status")


# ── store: atomic decide ─────────────────────────────────────────────────────


def test_decide_approve_then_reject_is_idempotent(tmp_db: Path):
    row = approvals_store.create_approval("a", "x", db_path=tmp_db)
    assert row is not None

    decided = approvals_store.decide_approval(
        row.id, approved=True, feedback="lgtm", decided_by="alice", db_path=tmp_db
    )
    assert decided is not None
    assert decided.status == "approved"
    assert decided.feedback == "lgtm"
    assert decided.decided_by == "alice"

    # A second decision on a now-terminal row is a no-op (returns None).
    again = approvals_store.decide_approval(row.id, approved=False, db_path=tmp_db)
    assert again is None

    # State did not change.
    final = approvals_store.get_approval(row.id, db_path=tmp_db)
    assert final is not None and final.status == "approved"
    print("✅ decide is atomic / single-shot")


def test_decide_unknown_returns_none(tmp_db: Path):
    assert approvals_store.decide_approval(
        "appr_missing", approved=True, db_path=tmp_db
    ) is None


def test_cancel_pending(tmp_db: Path):
    row = approvals_store.create_approval("a", "x", db_path=tmp_db)
    assert row is not None
    cancelled = approvals_store.cancel_approval(
        row.id, reason="abandoned", db_path=tmp_db
    )
    assert cancelled is not None and cancelled.status == "cancelled"
    # Can't decide a cancelled row.
    assert approvals_store.decide_approval(
        row.id, approved=True, db_path=tmp_db
    ) is None
    print("✅ cancel_approval terminalizes a pending row")


# ── store: expiry ────────────────────────────────────────────────────────────


def test_expire_approval_pending(tmp_db: Path):
    row = approvals_store.create_approval("a", "x", db_path=tmp_db)
    assert row is not None
    expired = approvals_store.expire_approval(row.id, db_path=tmp_db)
    assert expired is not None and expired.status == "expired"
    print("✅ expire_approval marks a pending row expired")


def test_expire_approval_respects_existing_decision(tmp_db: Path):
    row = approvals_store.create_approval("a", "x", db_path=tmp_db)
    assert row is not None
    approvals_store.decide_approval(row.id, approved=True, db_path=tmp_db)
    # A last-moment expire must NOT clobber a real decision: returns current row.
    final = approvals_store.expire_approval(row.id, db_path=tmp_db)
    assert final is not None and final.status == "approved"
    print("✅ expire_approval honours a prior decision (race-safe)")


def test_expire_stale_reaps_past_ttl(tmp_db: Path):
    import time

    fresh = approvals_store.create_approval(
        "a", "x", ttl_seconds=300, db_path=tmp_db
    )
    # ttl=1s stamps expires_at; sleeping past it makes the row reapable.
    stale = approvals_store.create_approval(
        "b", "y", ttl_seconds=1, db_path=tmp_db
    )
    assert fresh and stale
    time.sleep(1.2)

    reaped = approvals_store.expire_stale(db_path=tmp_db)
    assert reaped == 1
    assert approvals_store.get_approval(stale.id, db_path=tmp_db).status == "expired"
    assert approvals_store.get_approval(fresh.id, db_path=tmp_db).status == "pending"
    print("✅ expire_stale reaps only rows past their TTL")


# ── guardrails: APPROVAL_MODE dispatch ───────────────────────────────────────


def test_auto_mode_headless_auto_approves(monkeypatch):
    """Default (auto) mode in a headless run must NOT block — auto-approves."""
    monkeypatch.delenv("APPROVAL_MODE", raising=False)
    h = HumanApproval()
    # Force non-interactive regardless of how tests are launched.
    monkeypatch.setattr(h, "_interactive", False)
    approved, feedback = asyncio.run(
        h.request_approval("finance_agent", "send_invoice", "x")
    )
    assert approved is True
    assert feedback is None
    print("✅ auto mode auto-approves headless (no input())")


def test_interactive_mode_headless_fails_closed(monkeypatch):
    """interactive mode with no TTY fails CLOSED and never calls input()."""
    monkeypatch.setenv("APPROVAL_MODE", "interactive")

    def _boom(*a, **k):  # pragma: no cover - must never run
        raise AssertionError("input() must not be called in headless interactive")

    monkeypatch.setattr("builtins.input", _boom)
    h = HumanApproval()
    monkeypatch.setattr(h, "_interactive", False)
    approved, feedback = asyncio.run(h.request_approval("a", "b", "c"))
    assert approved is False
    assert "no terminal" in (feedback or "").lower()
    print("✅ interactive mode fails closed headless without input()")


def test_override_auto_approve_all(monkeypatch):
    monkeypatch.setenv("APPROVAL_MODE", "durable")  # ignored by override
    h = HumanApproval(auto_approve_all=True)
    approved, feedback = asyncio.run(h.request_approval("a", "b"))
    assert approved is True and feedback is None
    print("✅ auto_approve_all override short-circuits all modes")


# ── guardrails: durable mode (end-to-end with the store) ─────────────────────


def _force_durable(monkeypatch, *, wait=5, poll=0.2):
    cfg = ApprovalConfig(
        mode="durable", wait_timeout_seconds=wait, poll_interval_seconds=poll
    )
    monkeypatch.setattr("config.get_approval_config", lambda: cfg)
    return cfg


def test_durable_mode_approved(patched_db, monkeypatch):
    _force_durable(monkeypatch, wait=5, poll=0.2)
    h = HumanApproval()

    async def _scenario():
        task = asyncio.create_task(
            h.request_approval("finance_agent", "send_invoice", "Invoice #7")
        )
        # Wait for the durable row to appear, then approve it out-of-band.
        approval_id = None
        for _ in range(50):
            await asyncio.sleep(0.05)
            pending = approvals_store.list_approvals(
                status="pending", db_path=patched_db
            )
            if pending:
                approval_id = pending[0].id
                break
        assert approval_id is not None, "durable approval row never appeared"
        approvals_store.decide_approval(
            approval_id, approved=True, feedback="ship it",
            decided_by="alice", db_path=patched_db,
        )
        return await task

    approved, feedback = asyncio.run(_scenario())
    assert approved is True
    assert feedback == "ship it"
    print("✅ durable mode unblocks on out-of-band approve")


def test_durable_mode_rejected(patched_db, monkeypatch):
    _force_durable(monkeypatch, wait=5, poll=0.2)
    h = HumanApproval()

    async def _scenario():
        task = asyncio.create_task(h.request_approval("a", "b", "c"))
        approval_id = None
        for _ in range(50):
            await asyncio.sleep(0.05)
            pending = approvals_store.list_approvals(
                status="pending", db_path=patched_db
            )
            if pending:
                approval_id = pending[0].id
                break
        assert approval_id is not None
        approvals_store.decide_approval(
            approval_id, approved=False, feedback="nope", db_path=patched_db
        )
        return await task

    approved, feedback = asyncio.run(_scenario())
    assert approved is False
    assert feedback == "nope"
    print("✅ durable mode unblocks on out-of-band reject")


def test_durable_mode_times_out_fail_closed(patched_db, monkeypatch):
    # Shortest allowed wait; nobody decides -> fail closed.
    _force_durable(monkeypatch, wait=1, poll=0.2)
    h = HumanApproval()
    approved, feedback = asyncio.run(h.request_approval("a", "b", "c"))
    assert approved is False
    assert "timed out" in (feedback or "").lower()
    print("✅ durable mode times out fail-closed")


def test_durable_config_failure_fails_closed(patched_db, monkeypatch):
    """If APPROVAL_MODE=durable but config load explodes, fail CLOSED."""
    monkeypatch.setenv("APPROVAL_MODE", "durable")

    def _explode():
        raise RuntimeError("config boom")

    monkeypatch.setattr("config.get_approval_config", _explode)
    h = HumanApproval()
    approved, feedback = asyncio.run(h.request_approval("a", "b", "c"))
    assert approved is False
    assert "unavailable" in (feedback or "").lower()
    print("✅ durable + broken config fails closed")


# ── api: REST decide surface ─────────────────────────────────────────────────


pytestmark_api = pytest.mark.skipif(
    TestClient is None, reason="fastapi TestClient (httpx) not installed"
)


def _make_app() -> "FastAPI":
    from api.routes.approvals import router as approvals_router

    app = FastAPI()
    app.include_router(approvals_router, prefix="/api/v1/approvals")
    return app


@pytestmark_api
def test_api_list_and_get(patched_db):
    row = approvals_store.create_approval("a", "x", db_path=patched_db)
    assert row is not None
    client = TestClient(_make_app())

    resp = client.get("/api/v1/approvals")
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 1
    assert body["approvals"][0]["id"] == row.id

    resp = client.get(f"/api/v1/approvals/{row.id}")
    assert resp.status_code == 200
    assert resp.json()["status"] == "pending"
    print("✅ GET list + GET by id")


@pytestmark_api
def test_api_get_unknown_404(patched_db):
    client = TestClient(_make_app())
    resp = client.get("/api/v1/approvals/appr_missing")
    assert resp.status_code == 404
    print("✅ GET unknown -> 404")


@pytestmark_api
def test_api_approve_then_409(patched_db):
    row = approvals_store.create_approval("a", "x", db_path=patched_db)
    assert row is not None
    client = TestClient(_make_app())

    resp = client.post(
        f"/api/v1/approvals/{row.id}/approve",
        json={"feedback": "go", "decided_by": "bob"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"

    # Second decision -> 409 (already terminal).
    resp = client.post(f"/api/v1/approvals/{row.id}/reject")
    assert resp.status_code == 409
    print("✅ approve then second decide -> 409")


@pytestmark_api
def test_api_reject_unknown_404(patched_db):
    client = TestClient(_make_app())
    resp = client.post("/api/v1/approvals/appr_missing/reject")
    assert resp.status_code == 404
    print("✅ reject unknown -> 404")


@pytestmark_api
def test_api_invalid_status_filter_400(patched_db):
    client = TestClient(_make_app())
    resp = client.get("/api/v1/approvals?status=bogus")
    assert resp.status_code == 400
    print("✅ invalid ?status -> 400")


# ── azure search: stays disabled offline ─────────────────────────────────────


def test_azure_search_disabled_offline(monkeypatch):
    """With no creds, the optional Azure backend reports disabled and never
    raises — local case search is unaffected."""
    monkeypatch.delenv("AZURE_SEARCH_ENDPOINT", raising=False)
    monkeypatch.delenv("AZURE_SEARCH_KEY", raising=False)
    assert azure_search.azure_search_enabled() is False

    cfg = get_azure_search_config()
    assert cfg.enabled is False

    status = azure_search.azure_search_status()
    assert status["enabled"] is False
    assert "sdk_available" in status
    print("✅ azure search disabled offline (no creds)")


def test_azure_semantic_search_returns_none_when_disabled(monkeypatch):
    monkeypatch.delenv("AZURE_SEARCH_ENDPOINT", raising=False)
    monkeypatch.delenv("AZURE_SEARCH_KEY", raising=False)
    result = asyncio.run(azure_search.azure_semantic_search("any query"))
    assert result is None
    print("✅ azure_semantic_search returns None when disabled (never raises)")


# ── regression: rubber-duck round-2 fixes ────────────────────────────────────


def test_decide_past_expiry_fails_closed(tmp_db: Path):
    """Fix B: a decision arriving after ``expires_at`` must be refused so a
    late approval can never win the race with the poll-loop's deadline. The row
    stays ``pending`` (a reaper will mark it expired) — it is never silently
    flipped to ``approved``."""
    import time

    row = approvals_store.create_approval("a", "x", ttl_seconds=1, db_path=tmp_db)
    assert row is not None
    time.sleep(1.2)  # walk past expires_at

    decided = approvals_store.decide_approval(
        row.id, approved=True, db_path=tmp_db
    )
    assert decided is None, "expired window must not be decidable"

    still = approvals_store.get_approval(row.id, db_path=tmp_db)
    assert still is not None and still.status == "pending"
    print("✅ decide past expiry is refused (fail-closed, stays pending)")


def test_decide_null_expiry_always_allowed(tmp_db: Path):
    """Fix B corollary: rows created with no TTL have NULL ``expires_at`` and
    remain decidable indefinitely (non-durable / interactive flows)."""
    row = approvals_store.create_approval("a", "x", db_path=tmp_db)  # no ttl
    assert row is not None

    decided = approvals_store.decide_approval(
        row.id, approved=True, feedback="ok", db_path=tmp_db
    )
    assert decided is not None and decided.status == "approved"
    assert decided.feedback == "ok"
    print("✅ NULL-expiry rows stay decidable forever")


def test_expire_stale_counts_multiple(tmp_db: Path):
    """Fix D: ``expire_stale`` returns the count of rows it actually reaped and
    leaves un-expired rows untouched."""
    import time

    s1 = approvals_store.create_approval("a", "x", ttl_seconds=1, db_path=tmp_db)
    s2 = approvals_store.create_approval("b", "y", ttl_seconds=1, db_path=tmp_db)
    fresh = approvals_store.create_approval(
        "c", "z", ttl_seconds=300, db_path=tmp_db
    )
    assert s1 and s2 and fresh
    time.sleep(1.2)

    reaped = approvals_store.expire_stale(db_path=tmp_db)
    assert reaped == 2
    assert (
        approvals_store.get_approval(fresh.id, db_path=tmp_db).status == "pending"
    )
    for s in (s1, s2):
        assert approvals_store.get_approval(s.id, db_path=tmp_db).status == "expired"
    print("✅ expire_stale returns the real reaped count (2 of 3)")


def test_get_approval_config_invalid_mode_fails_closed(monkeypatch):
    """Fix A: an explicitly-set but invalid APPROVAL_MODE must not silently
    become ``auto`` (which would skip human review). It fails CLOSED to
    ``durable``. Unset → ``auto``; a valid value is honoured verbatim."""
    monkeypatch.setenv("APPROVAL_MODE", "durabl")  # typo'd / invalid
    assert get_approval_config().mode == "durable"

    monkeypatch.delenv("APPROVAL_MODE", raising=False)
    assert get_approval_config().mode == "auto"

    monkeypatch.setenv("APPROVAL_MODE", "interactive")
    assert get_approval_config().mode == "interactive"
    print("✅ invalid APPROVAL_MODE fails closed to durable")


def test_durable_unreadable_store_mid_wait_fails_closed(patched_db, monkeypatch):
    """Fix C path: the row is created, but reads return None mid-wait (store
    row vanished / unreadable). The guardrail must fail CLOSED rather than hang
    or auto-approve."""
    _force_durable(monkeypatch, wait=5, poll=0.2)
    monkeypatch.setattr(approvals_store, "get_approval", lambda *a, **k: None)

    h = HumanApproval()
    approved, feedback = asyncio.run(h.request_approval("a", "b", "c"))
    assert approved is False
    assert "unavailable" in (feedback or "").lower()
    print("✅ durable + unreadable store mid-wait fails closed")


def test_search_cases_survives_azure_error(tmp_path: Path, monkeypatch):
    """Azure fan-out is best-effort: if the optional Azure backend is enabled
    but raises, local FTS results must still be returned (Azure errors can
    never break case search)."""
    cases = tmp_path / "cases"
    (cases / "case-1").mkdir(parents=True)
    (cases / "case-1" / "notes.md").write_text(
        "Quarterly revenue report for ACME. Invoice totals and payment terms.",
        encoding="utf-8",
    )
    rag_db = tmp_path / "rag.db"
    asyncio.run(rag_store.index_cases(cases, db_path=rag_db))

    # Force Azure ON but make the semantic call explode.
    monkeypatch.setattr(azure_search, "azure_search_enabled", lambda: True)

    async def _boom(*a, **k):
        raise RuntimeError("azure down")

    monkeypatch.setattr(azure_search, "azure_semantic_search", _boom)

    hits = asyncio.run(rag_store.search_cases("revenue", db_path=rag_db))
    assert hits, "local FTS hits must survive an Azure fan-out error"
    print("✅ search_cases returns local hits despite an Azure error")
