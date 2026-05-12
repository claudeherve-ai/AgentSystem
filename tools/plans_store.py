"""
Durable plan/task store for the orchestrator.

Persists multi-step plans so the orchestrator can:
  - decompose a long-running ask into ordered steps,
  - assign steps to specialist agents,
  - track per-step status (pending / in_progress / done / blocked / cancelled),
  - resume work after a restart or content-filter blip,
  - audit every transition with a parent trail.

Storage: SQLite at memory/orchestrator_plans.db (WAL).
Schema:
  plans         (id, title, goal, status, owner, tags, created_at, updated_at)
  plan_steps    (id, plan_id, step_index, title, description, status,
                 result, owner_agent, started_at, completed_at)
  plan_events   (id, plan_id, ts, kind, payload)

All public functions accept `db_path: Path | None = None` so smoke tests can
target a temp database. Nothing in this module raises on a normal control path
— callers see a clear error string and the audit log captures the failure.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ── Storage ──────────────────────────────────────────────────────────────────
PLANS_DIR = Path(__file__).resolve().parent.parent / "memory"
PLANS_DIR.mkdir(parents=True, exist_ok=True)
PLANS_DB = PLANS_DIR / "orchestrator_plans.db"

# ── Status vocabulary ────────────────────────────────────────────────────────
PLAN_STATUSES = {"pending", "in_progress", "done", "blocked", "cancelled"}
STEP_STATUSES = {"pending", "in_progress", "done", "blocked", "skipped"}

# ── Public defaults ──────────────────────────────────────────────────────────
def default_db_path() -> Path:
    return PLANS_DB


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


# ── Connection / schema ──────────────────────────────────────────────────────
def _connect(db_path: Path | None = None) -> sqlite3.Connection:
    target = db_path or PLANS_DB
    conn = sqlite3.connect(str(target))
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.row_factory = sqlite3.Row
    conn.execute(
        "CREATE TABLE IF NOT EXISTS plans ("
        "  id TEXT PRIMARY KEY,"
        "  title TEXT NOT NULL,"
        "  goal TEXT NOT NULL,"
        "  status TEXT NOT NULL DEFAULT 'pending',"
        "  owner TEXT,"
        "  tags TEXT,"
        "  created_at TEXT NOT NULL,"
        "  updated_at TEXT NOT NULL"
        ")"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS plan_steps ("
        "  id TEXT PRIMARY KEY,"
        "  plan_id TEXT NOT NULL REFERENCES plans(id) ON DELETE CASCADE,"
        "  step_index INTEGER NOT NULL,"
        "  title TEXT NOT NULL,"
        "  description TEXT,"
        "  status TEXT NOT NULL DEFAULT 'pending',"
        "  result TEXT,"
        "  owner_agent TEXT,"
        "  started_at TEXT,"
        "  completed_at TEXT"
        ")"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_steps_plan ON plan_steps(plan_id)"
    )
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_steps_plan_index "
        "ON plan_steps(plan_id, step_index)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS plan_events ("
        "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "  plan_id TEXT NOT NULL REFERENCES plans(id) ON DELETE CASCADE,"
        "  ts TEXT NOT NULL,"
        "  kind TEXT NOT NULL,"
        "  payload TEXT"
        ")"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_events_plan ON plan_events(plan_id)"
    )
    return conn


# ── Data classes ─────────────────────────────────────────────────────────────
@dataclass
class StepSpec:
    title: str
    description: str = ""
    owner_agent: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "description": self.description,
            "owner_agent": self.owner_agent,
        }


@dataclass
class StepRow:
    id: str
    plan_id: str
    step_index: int
    title: str
    description: str
    status: str
    result: str
    owner_agent: str
    started_at: Optional[str]
    completed_at: Optional[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "plan_id": self.plan_id,
            "step_index": self.step_index,
            "title": self.title,
            "description": self.description,
            "status": self.status,
            "result": self.result,
            "owner_agent": self.owner_agent,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }


@dataclass
class PlanRow:
    id: str
    title: str
    goal: str
    status: str
    owner: str
    tags: str
    created_at: str
    updated_at: str
    steps: list[StepRow] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "goal": self.goal,
            "status": self.status,
            "owner": self.owner,
            "tags": [t for t in (self.tags or "").split(",") if t],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "steps": [s.to_dict() for s in self.steps],
        }


# ── Internal helpers ─────────────────────────────────────────────────────────
def _row_to_plan(row: sqlite3.Row) -> PlanRow:
    return PlanRow(
        id=row["id"],
        title=row["title"],
        goal=row["goal"],
        status=row["status"],
        owner=row["owner"] or "",
        tags=row["tags"] or "",
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _row_to_step(row: sqlite3.Row) -> StepRow:
    return StepRow(
        id=row["id"],
        plan_id=row["plan_id"],
        step_index=row["step_index"],
        title=row["title"],
        description=row["description"] or "",
        status=row["status"],
        result=row["result"] or "",
        owner_agent=row["owner_agent"] or "",
        started_at=row["started_at"],
        completed_at=row["completed_at"],
    )


def _emit_event(
    conn: sqlite3.Connection,
    plan_id: str,
    kind: str,
    payload: dict[str, Any] | None = None,
) -> None:
    conn.execute(
        "INSERT INTO plan_events (plan_id, ts, kind, payload) VALUES (?, ?, ?, ?)",
        (plan_id, _now(), kind, json.dumps(payload or {}, default=str)),
    )


def _touch_plan(conn: sqlite3.Connection, plan_id: str) -> None:
    conn.execute(
        "UPDATE plans SET updated_at = ? WHERE id = ?",
        (_now(), plan_id),
    )


def _maybe_complete_plan(conn: sqlite3.Connection, plan_id: str) -> Optional[str]:
    """If every step is terminal, roll the plan up to a final status. Returns the new status, if any."""
    rows = conn.execute(
        "SELECT status FROM plan_steps WHERE plan_id = ?", (plan_id,)
    ).fetchall()
    if not rows:
        return None
    statuses = {r["status"] for r in rows}
    if statuses <= {"done", "skipped"}:
        new_status = "done"
    elif "blocked" in statuses:
        new_status = "blocked"
    else:
        return None
    conn.execute(
        "UPDATE plans SET status = ?, updated_at = ? WHERE id = ?",
        (new_status, _now(), plan_id),
    )
    return new_status


# ── CRUD: plans ──────────────────────────────────────────────────────────────
def create_plan(
    title: str,
    goal: str,
    steps: list[StepSpec] | list[dict[str, Any]] | None = None,
    owner: str = "",
    tags: list[str] | None = None,
    db_path: Path | None = None,
) -> PlanRow:
    """Create a plan with zero or more initial steps. Returns the persisted row."""
    title = (title or "").strip() or "Untitled plan"
    goal = (goal or "").strip()
    plan_id = _new_id("plan")
    tags_str = ",".join((t or "").strip() for t in (tags or []) if (t or "").strip())
    now = _now()
    norm_steps: list[StepSpec] = []
    for s in steps or []:
        if isinstance(s, StepSpec):
            norm_steps.append(s)
        elif isinstance(s, dict):
            norm_steps.append(
                StepSpec(
                    title=str(s.get("title", "")).strip() or "Untitled step",
                    description=str(s.get("description", "") or ""),
                    owner_agent=str(s.get("owner_agent", "") or ""),
                )
            )
    conn = _connect(db_path)
    try:
        conn.execute(
            "INSERT INTO plans (id, title, goal, status, owner, tags, created_at, updated_at)"
            " VALUES (?, ?, ?, 'pending', ?, ?, ?, ?)",
            (plan_id, title, goal, owner.strip(), tags_str, now, now),
        )
        for idx, spec in enumerate(norm_steps):
            conn.execute(
                "INSERT INTO plan_steps (id, plan_id, step_index, title, description,"
                " status, result, owner_agent) VALUES (?, ?, ?, ?, ?, 'pending', '', ?)",
                (
                    _new_id("step"),
                    plan_id,
                    idx,
                    spec.title,
                    spec.description,
                    spec.owner_agent,
                ),
            )
        _emit_event(
            conn,
            plan_id,
            "plan_created",
            {"title": title, "step_count": len(norm_steps)},
        )
        conn.commit()
        return get_plan(plan_id, db_path=db_path) or _row_to_plan(
            conn.execute("SELECT * FROM plans WHERE id = ?", (plan_id,)).fetchone()
        )
    finally:
        conn.close()


def get_plan(plan_id: str, db_path: Path | None = None) -> Optional[PlanRow]:
    conn = _connect(db_path)
    try:
        row = conn.execute("SELECT * FROM plans WHERE id = ?", (plan_id,)).fetchone()
        if not row:
            return None
        plan = _row_to_plan(row)
        step_rows = conn.execute(
            "SELECT * FROM plan_steps WHERE plan_id = ? ORDER BY step_index ASC",
            (plan_id,),
        ).fetchall()
        plan.steps = [_row_to_step(r) for r in step_rows]
        return plan
    finally:
        conn.close()


def list_plans(
    status: str = "",
    limit: int = 50,
    db_path: Path | None = None,
) -> list[PlanRow]:
    conn = _connect(db_path)
    try:
        if status and status in PLAN_STATUSES:
            rows = conn.execute(
                "SELECT * FROM plans WHERE status = ? ORDER BY updated_at DESC LIMIT ?",
                (status, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM plans ORDER BY updated_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        plans = [_row_to_plan(r) for r in rows]
        for p in plans:
            step_rows = conn.execute(
                "SELECT * FROM plan_steps WHERE plan_id = ? ORDER BY step_index ASC",
                (p.id,),
            ).fetchall()
            p.steps = [_row_to_step(r) for r in step_rows]
        return plans
    finally:
        conn.close()


def cancel_plan(
    plan_id: str,
    reason: str = "",
    db_path: Path | None = None,
) -> Optional[PlanRow]:
    conn = _connect(db_path)
    try:
        row = conn.execute("SELECT * FROM plans WHERE id = ?", (plan_id,)).fetchone()
        if not row:
            return None
        conn.execute(
            "UPDATE plans SET status = 'cancelled', updated_at = ? WHERE id = ?",
            (_now(), plan_id),
        )
        conn.execute(
            "UPDATE plan_steps SET status = 'skipped', completed_at = ?"
            " WHERE plan_id = ? AND status NOT IN ('done', 'skipped')",
            (_now(), plan_id),
        )
        _emit_event(conn, plan_id, "plan_cancelled", {"reason": reason})
        conn.commit()
        return get_plan(plan_id, db_path=db_path)
    finally:
        conn.close()


# ── CRUD: steps ──────────────────────────────────────────────────────────────
def update_step(
    plan_id: str,
    step_index: int,
    status: str = "",
    result: str = "",
    owner_agent: str = "",
    description: str = "",
    db_path: Path | None = None,
) -> Optional[StepRow]:
    """Patch a single step. Empty strings = leave unchanged. Returns the new row."""
    if status and status not in STEP_STATUSES:
        raise ValueError(
            f"Invalid step status {status!r}. Allowed: {sorted(STEP_STATUSES)}"
        )
    conn = _connect(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM plan_steps WHERE plan_id = ? AND step_index = ?",
            (plan_id, step_index),
        ).fetchone()
        if not row:
            return None
        sets: list[str] = []
        vals: list[Any] = []
        if status:
            sets.append("status = ?")
            vals.append(status)
            if status == "in_progress" and not row["started_at"]:
                sets.append("started_at = ?")
                vals.append(_now())
            if status in {"done", "skipped", "blocked"}:
                sets.append("completed_at = ?")
                vals.append(_now())
        if result:
            sets.append("result = ?")
            vals.append(result)
        if owner_agent:
            sets.append("owner_agent = ?")
            vals.append(owner_agent)
        if description:
            sets.append("description = ?")
            vals.append(description)
        if sets:
            vals.extend([plan_id, step_index])
            conn.execute(
                f"UPDATE plan_steps SET {', '.join(sets)}"
                " WHERE plan_id = ? AND step_index = ?",
                vals,
            )
            _touch_plan(conn, plan_id)
            _emit_event(
                conn,
                plan_id,
                "step_updated",
                {"step_index": step_index, "status": status, "owner_agent": owner_agent},
            )
            # If the plan was pending and we just started a step, mark it in_progress
            if status == "in_progress":
                conn.execute(
                    "UPDATE plans SET status = 'in_progress', updated_at = ?"
                    " WHERE id = ? AND status = 'pending'",
                    (_now(), plan_id),
                )
            _maybe_complete_plan(conn, plan_id)
            conn.commit()
        new_row = conn.execute(
            "SELECT * FROM plan_steps WHERE plan_id = ? AND step_index = ?",
            (plan_id, step_index),
        ).fetchone()
        return _row_to_step(new_row) if new_row else None
    finally:
        conn.close()


def next_pending_step(
    plan_id: str,
    db_path: Path | None = None,
) -> Optional[StepRow]:
    """Return the lowest-index step whose status is 'pending' or 'in_progress'."""
    conn = _connect(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM plan_steps WHERE plan_id = ?"
            " AND status IN ('pending', 'in_progress')"
            " ORDER BY step_index ASC LIMIT 1",
            (plan_id,),
        ).fetchone()
        return _row_to_step(row) if row else None
    finally:
        conn.close()


def add_step(
    plan_id: str,
    title: str,
    description: str = "",
    owner_agent: str = "",
    db_path: Path | None = None,
) -> Optional[StepRow]:
    conn = _connect(db_path)
    try:
        plan_row = conn.execute("SELECT id FROM plans WHERE id = ?", (plan_id,)).fetchone()
        if not plan_row:
            return None
        idx_row = conn.execute(
            "SELECT COALESCE(MAX(step_index) + 1, 0) AS next_idx FROM plan_steps WHERE plan_id = ?",
            (plan_id,),
        ).fetchone()
        next_idx = idx_row["next_idx"] if idx_row else 0
        step_id = _new_id("step")
        conn.execute(
            "INSERT INTO plan_steps (id, plan_id, step_index, title, description,"
            " status, result, owner_agent) VALUES (?, ?, ?, ?, ?, 'pending', '', ?)",
            (step_id, plan_id, next_idx, title.strip() or "Untitled step",
             description, owner_agent),
        )
        _touch_plan(conn, plan_id)
        _emit_event(conn, plan_id, "step_added", {"step_index": next_idx, "title": title})
        conn.commit()
        new_row = conn.execute(
            "SELECT * FROM plan_steps WHERE id = ?", (step_id,)
        ).fetchone()
        return _row_to_step(new_row) if new_row else None
    finally:
        conn.close()


# ── Diagnostic helpers ───────────────────────────────────────────────────────
def count_plans(db_path: Path | None = None) -> int:
    conn = _connect(db_path)
    try:
        row = conn.execute("SELECT COUNT(*) AS c FROM plans").fetchone()
        return int(row["c"]) if row else 0
    finally:
        conn.close()


def get_events(
    plan_id: str,
    limit: int = 50,
    db_path: Path | None = None,
) -> list[dict[str, Any]]:
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            "SELECT ts, kind, payload FROM plan_events WHERE plan_id = ?"
            " ORDER BY id DESC LIMIT ?",
            (plan_id, limit),
        ).fetchall()
        out: list[dict[str, Any]] = []
        for r in rows:
            try:
                payload = json.loads(r["payload"] or "{}")
            except json.JSONDecodeError:
                payload = {"raw": r["payload"]}
            out.append({"ts": r["ts"], "kind": r["kind"], "payload": payload})
        return out
    finally:
        conn.close()
