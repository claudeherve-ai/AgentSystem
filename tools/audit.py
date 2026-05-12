"""
AgentSystem — Audit logger.

Logs every agent action to SQLite for accountability, debugging, and rollback.
"""

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).resolve().parent.parent / "memory" / "audit.db"


def _get_connection() -> sqlite3.Connection:
    """Get a connection to the audit database, creating tables if needed."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS agent_actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            agent_name TEXT NOT NULL,
            action TEXT NOT NULL,
            input_summary TEXT,
            output_summary TEXT,
            approved_by TEXT DEFAULT NULL,
            status TEXT DEFAULT 'pending',
            metadata TEXT
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_actions_agent
        ON agent_actions(agent_name, timestamp)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_actions_status
        ON agent_actions(status)
    """)
    conn.commit()
    return conn


def log_action(
    agent_name: str,
    action: str,
    input_summary: str = "",
    output_summary: str = "",
    approved_by: Optional[str] = None,
    status: str = "completed",
    metadata: Optional[dict[str, Any]] = None,
) -> int:
    """
    Log an agent action to the audit database.
    Returns the row ID of the logged action.
    """
    conn = _get_connection()
    try:
        cursor = conn.execute(
            """
            INSERT INTO agent_actions
                (timestamp, agent_name, action, input_summary, output_summary,
                 approved_by, status, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.now(timezone.utc).isoformat(),
                agent_name,
                action,
                input_summary,
                output_summary,
                approved_by,
                status,
                json.dumps(metadata) if metadata else None,
            ),
        )
        conn.commit()
        row_id = cursor.lastrowid or 0
        logger.info(f"Audit [{row_id}] {agent_name}.{action} → {status}")
        return row_id
    finally:
        conn.close()


def audit_log(
    agent_name: str,
    status: str,
    metadata: Optional[dict[str, Any]] = None,
    parent_id: Optional[int] = None,
) -> int:
    """
    Newer-style audit helper used by capability tools.

    `agent_name` is "Module.action" (e.g. "WebSearch.search").
    `status` is the lifecycle state ("started", "completed", "error", ...).
    `parent_id` is recorded inside metadata so child events can be traced
    back to their started event without needing a schema change.
    """
    md: dict[str, Any] = dict(metadata or {})
    if parent_id is not None:
        md["parent_id"] = parent_id
    return log_action(
        agent_name=agent_name,
        action=status,
        status=status,
        metadata=md or None,
    )


def get_recent_actions(limit: int = 20) -> list[dict[str, Any]]:
    """Retrieve the most recent agent actions."""
    conn = _get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM agent_actions ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        columns = [desc[0] for desc in conn.execute(
            "SELECT * FROM agent_actions LIMIT 0"
        ).description]
        return [dict(zip(columns, row)) for row in rows]
    finally:
        conn.close()


def get_actions_by_agent(agent_name: str, limit: int = 50) -> list[dict[str, Any]]:
    """Retrieve actions for a specific agent."""
    conn = _get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM agent_actions WHERE agent_name = ? ORDER BY id DESC LIMIT ?",
            (agent_name, limit),
        ).fetchall()
        columns = [desc[0] for desc in conn.execute(
            "SELECT * FROM agent_actions LIMIT 0"
        ).description]
        return [dict(zip(columns, row)) for row in rows]
    finally:
        conn.close()
