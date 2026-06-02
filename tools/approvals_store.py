"""
Durable human-in-the-loop (HITL) approval store.

In ``durable`` approval mode (see :func:`config.get_approval_config`) a sensitive
agent action — ``send_email``, ``post_social_media``, ``send_invoice`` … — is
persisted here as a PENDING request and the calling agent BLOCKS until a human
decides it via the ``/api/v1/approvals`` API. This replaces the historical
server-side fail-OPEN behaviour (auto-approve when there is no TTY) with an
explicit, auditable, fail-CLOSED gate.

Mirrors the conventions of :mod:`tools.plans_store`:
  * SQLite at ``memory/approvals.db`` (WAL, foreign_keys, busy_timeout).
  * Every public function takes ``db_path: Path | None = None`` so tests can
    target a temporary database.
  * Nothing here raises on a normal control path — callers get a clear value
    (``None`` / empty list) and the audit log captures the failure. Durable
    callers treat a ``None`` create/get as "fail closed".

Schema:
  approvals        (id, agent_name, action, details, status, feedback,
                    requested_at, decided_at, decided_by, expires_at)
  approval_events  (id, approval_id, ts, kind, payload)

Status vocabulary: pending → {approved, rejected, expired, cancelled}.
A decision only ever applies to a PENDING row (atomic ``UPDATE … WHERE
status='pending'``), so concurrent approve/reject/expire cannot double-decide.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ── Storage ──────────────────────────────────────────────────────────────────
APPROVALS_DIR = Path(__file__).resolve().parent.parent / "memory"
APPROVALS_DIR.mkdir(parents=True, exist_ok=True)
APPROVALS_DB = APPROVALS_DIR / "approvals.db"

# ── Status vocabulary ────────────────────────────────────────────────────────
APPROVAL_STATUSES = {"pending", "approved", "rejected", "expired", "cancelled"}
TERMINAL_STATUSES = {"approved", "rejected", "expired", "cancelled"}

# Cap stored details so durable approvals never persist unbounded PII / payloads.
_MAX_DETAILS_CHARS = 4000


# ── Public defaults ──────────────────────────────────────────────────────────
def default_db_path() -> Path:
    return APPROVALS_DB


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _new_id(prefix: str = "appr") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


# ── Connection / schema ──────────────────────────────────────────────────────
def _connect(db_path: Path | None = None) -> sqlite3.Connection:
    target = db_path or APPROVALS_DB
    conn = sqlite3.connect(str(target))
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    # Tolerate brief contention from concurrent approve/reject/expire callers.
    conn.execute("PRAGMA busy_timeout=5000;")
    conn.row_factory = sqlite3.Row
    conn.execute(
        "CREATE TABLE IF NOT EXISTS approvals ("
        "  id TEXT PRIMARY KEY,"
        "  agent_name TEXT NOT NULL,"
        "  action TEXT NOT NULL,"
        "  details TEXT,"
        "  status TEXT NOT NULL DEFAULT 'pending',"
        "  feedback TEXT,"
        "  requested_at TEXT NOT NULL,"
        "  decided_at TEXT,"
        "  decided_by TEXT,"
        "  expires_at TEXT"
        ")"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS approval_events ("
        "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "  approval_id TEXT NOT NULL REFERENCES approvals(id) ON DELETE CASCADE,"
        "  ts TEXT NOT NULL,"
        "  kind TEXT NOT NULL,"
        "  payload TEXT"
        ")"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_approvals_status "
        "ON approvals(status, requested_at)"
    )
    return conn


# ── Dataclass ────────────────────────────────────────────────────────────────
@dataclass
class ApprovalRow:
    id: str
    agent_name: str
    action: str
    details: str
    status: str
    feedback: str
    requested_at: str
    decided_at: Optional[str]
    decided_by: Optional[str]
    expires_at: Optional[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "agent_name": self.agent_name,
            "action": self.action,
            "details": self.details,
            "status": self.status,
            "feedback": self.feedback,
            "requested_at": self.requested_at,
            "decided_at": self.decided_at,
            "decided_by": self.decided_by,
            "expires_at": self.expires_at,
        }


# ── Internal helpers ─────────────────────────────────────────────────────────
def _row_to_approval(row: sqlite3.Row) -> ApprovalRow:
    return ApprovalRow(
        id=row["id"],
        agent_name=row["agent_name"],
        action=row["action"],
        details=row["details"] or "",
        status=row["status"],
        feedback=row["feedback"] or "",
        requested_at=row["requested_at"],
        decided_at=row["decided_at"],
        decided_by=row["decided_by"],
        expires_at=row["expires_at"],
    )


def _emit_event(
    conn: sqlite3.Connection,
    approval_id: str,
    kind: str,
    payload: dict[str, Any] | None = None,
) -> None:
    conn.execute(
        "INSERT INTO approval_events (approval_id, ts, kind, payload) "
        "VALUES (?, ?, ?, ?)",
        (approval_id, _now(), kind, json.dumps(payload or {}, default=str)),
    )


# ── CRUD ─────────────────────────────────────────────────────────────────────
def create_approval(
    agent_name: str,
    action: str,
    details: str = "",
    ttl_seconds: int | None = None,
    db_path: Path | None = None,
) -> ApprovalRow | None:
    """Persist a new PENDING approval request.

    ``ttl_seconds`` (when > 0) stamps ``expires_at`` so :func:`expire_stale` can
    later reap abandoned rows. Returns the persisted row, or ``None`` on failure
    (durable callers treat ``None`` as "fail closed").
    """
    appr_id = _new_id()
    now = _now()
    safe_details = (details or "")[:_MAX_DETAILS_CHARS]
    expires_at: str | None = None
    if ttl_seconds and ttl_seconds > 0:
        expires_at = (
            datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
        ).isoformat(timespec="seconds")
    try:
        conn = _connect(db_path)
        try:
            conn.execute(
                "INSERT INTO approvals (id, agent_name, action, details, status, "
                "feedback, requested_at, decided_at, decided_by, expires_at) "
                "VALUES (?, ?, ?, ?, 'pending', '', ?, NULL, NULL, ?)",
                (
                    appr_id,
                    agent_name or "",
                    action or "",
                    safe_details,
                    now,
                    expires_at,
                ),
            )
            _emit_event(
                conn,
                appr_id,
                "created",
                {"agent_name": agent_name, "action": action},
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM approvals WHERE id = ?", (appr_id,)
            ).fetchone()
            return _row_to_approval(row) if row else None
        finally:
            conn.close()
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("create_approval failed: %s", exc)
        return None


def get_approval(
    approval_id: str, db_path: Path | None = None
) -> ApprovalRow | None:
    """Fetch one approval by id, or ``None`` if missing / on failure."""
    try:
        conn = _connect(db_path)
        try:
            row = conn.execute(
                "SELECT * FROM approvals WHERE id = ?", (approval_id,)
            ).fetchone()
            return _row_to_approval(row) if row else None
        finally:
            conn.close()
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("get_approval failed: %s", exc)
        return None


def list_approvals(
    status: str = "",
    limit: int = 100,
    db_path: Path | None = None,
) -> list[ApprovalRow]:
    """List approvals, newest first, optionally filtered by ``status``."""
    try:
        limit = max(1, int(limit))
    except (TypeError, ValueError):
        limit = 100
    try:
        conn = _connect(db_path)
        try:
            if status:
                rows = conn.execute(
                    "SELECT * FROM approvals WHERE status = ? "
                    "ORDER BY requested_at DESC, id DESC LIMIT ?",
                    (status, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM approvals "
                    "ORDER BY requested_at DESC, id DESC LIMIT ?",
                    (limit,),
                ).fetchall()
            return [_row_to_approval(r) for r in rows]
        finally:
            conn.close()
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("list_approvals failed: %s", exc)
        return []


def decide_approval(
    approval_id: str,
    approved: bool,
    feedback: str = "",
    decided_by: str = "",
    db_path: Path | None = None,
) -> ApprovalRow | None:
    """Atomically decide a PENDING approval.

    Returns the updated row on success. Returns ``None`` if the approval does
    not exist, was already terminal, OR has passed its ``expires_at`` deadline
    (the API layer disambiguates 404 vs 409 by fetching first). The decision is
    applied via ``UPDATE … WHERE status='pending' AND (expires_at IS NULL OR
    expires_at > now)`` so a concurrent approve/reject/expire can never
    double-decide, and a late approval landing AFTER the durable timeout can
    never sneak a sensitive action through (fail-closed).
    """
    new_status = "approved" if approved else "rejected"
    now = _now()
    try:
        conn = _connect(db_path)
        try:
            cur = conn.execute(
                "UPDATE approvals SET status = ?, feedback = ?, decided_at = ?, "
                "decided_by = ? WHERE id = ? AND status = 'pending' "
                "AND (expires_at IS NULL OR expires_at > ?)",
                (new_status, feedback or "", now, decided_by or "", approval_id, now),
            )
            if cur.rowcount == 0:
                conn.rollback()
                return None
            _emit_event(
                conn,
                approval_id,
                "decided",
                {"status": new_status, "decided_by": decided_by},
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM approvals WHERE id = ?", (approval_id,)
            ).fetchone()
            return _row_to_approval(row) if row else None
        finally:
            conn.close()
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("decide_approval failed: %s", exc)
        return None


def cancel_approval(
    approval_id: str,
    reason: str = "",
    db_path: Path | None = None,
) -> ApprovalRow | None:
    """Cancel a PENDING approval (e.g. the originating call was abandoned)."""
    now = _now()
    try:
        conn = _connect(db_path)
        try:
            cur = conn.execute(
                "UPDATE approvals SET status = 'cancelled', feedback = ?, "
                "decided_at = ? WHERE id = ? AND status = 'pending'",
                (reason or "", now, approval_id),
            )
            if cur.rowcount == 0:
                conn.rollback()
                return None
            _emit_event(conn, approval_id, "cancelled", {"reason": reason})
            conn.commit()
            row = conn.execute(
                "SELECT * FROM approvals WHERE id = ?", (approval_id,)
            ).fetchone()
            return _row_to_approval(row) if row else None
        finally:
            conn.close()
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("cancel_approval failed: %s", exc)
        return None


def expire_stale(db_path: Path | None = None) -> int:
    """Mark any PENDING approval past its ``expires_at`` as ``expired``.

    Returns the number of rows expired. This is a janitor for ABANDONED rows
    (e.g. the agent process died mid-wait); the live durable poll loop enforces
    its own deadline independently.
    """
    now = _now()
    try:
        conn = _connect(db_path)
        try:
            rows = conn.execute(
                "SELECT id FROM approvals WHERE status = 'pending' "
                "AND expires_at IS NOT NULL AND expires_at <= ?",
                (now,),
            ).fetchall()
            ids = [r["id"] for r in rows]
            expired = 0
            for aid in ids:
                cur = conn.execute(
                    "UPDATE approvals SET status = 'expired', decided_at = ? "
                    "WHERE id = ? AND status = 'pending'",
                    (now, aid),
                )
                if cur.rowcount:
                    _emit_event(conn, aid, "expired", {})
                    expired += 1
            conn.commit()
            return expired
        finally:
            conn.close()
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("expire_stale failed: %s", exc)
        return 0


def expire_approval(
    approval_id: str,
    db_path: Path | None = None,
) -> ApprovalRow | None:
    """Mark a single PENDING approval as ``expired`` (deadline reached).

    Atomic ``WHERE status = 'pending'`` guard means a human decision landing at
    the same instant wins: if the row was just approved/rejected, ``rowcount``
    is 0 and the caller should re-read the (now terminal) row. Always returns
    the current row so the durable poll loop can honour a last-moment decision.
    """
    now = _now()
    try:
        conn = _connect(db_path)
        try:
            cur = conn.execute(
                "UPDATE approvals SET status = 'expired', decided_at = ? "
                "WHERE id = ? AND status = 'pending'",
                (now, approval_id),
            )
            if cur.rowcount:
                _emit_event(conn, approval_id, "expired", {})
            conn.commit()
            row = conn.execute(
                "SELECT * FROM approvals WHERE id = ?", (approval_id,)
            ).fetchone()
            return _row_to_approval(row) if row else None
        finally:
            conn.close()
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("expire_approval failed: %s", exc)
        return None


def list_events(
    approval_id: str, db_path: Path | None = None
) -> list[dict[str, Any]]:
    """Return the audit trail for one approval (oldest first)."""
    try:
        conn = _connect(db_path)
        try:
            rows = conn.execute(
                "SELECT ts, kind, payload FROM approval_events "
                "WHERE approval_id = ? ORDER BY id ASC",
                (approval_id,),
            ).fetchall()
            out: list[dict[str, Any]] = []
            for r in rows:
                try:
                    payload = json.loads(r["payload"]) if r["payload"] else {}
                except (ValueError, TypeError):
                    payload = {}
                out.append({"ts": r["ts"], "kind": r["kind"], "payload": payload})
            return out
        finally:
            conn.close()
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("list_events failed: %s", exc)
        return []
