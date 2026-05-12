"""
AgentSystem — Memory tools.

Provides durable user memory plus lightweight conversation history so the
orchestrator can preserve context within a session and across restarts.
"""

import json
import logging
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Any, Optional

from tools.audit import log_action

logger = logging.getLogger(__name__)

MEMORY_DB = Path(__file__).resolve().parent.parent / "memory" / "agent_memory.db"
SESSION_STATE_PATH = Path(__file__).resolve().parent.parent / "memory" / "session_state.json"
PROFILE_SEED_PATH = Path(__file__).resolve().parent.parent / "memory" / "profile_seed.json"


def _utcnow() -> str:
    """Return the current UTC timestamp in ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat()


class MemoryStore:
    """SQLite-backed memory and session history store."""

    def __init__(
        self,
        db_path: Optional[Path] = None,
        session_state_path: Optional[Path] = None,
        profile_seed_path: Optional[Path] = None,
    ):
        self.db_path = db_path or MEMORY_DB
        self.session_state_path = session_state_path or SESSION_STATE_PATH
        self.profile_seed_path = profile_seed_path or PROFILE_SEED_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()
        self._load_profile_seed()

    @staticmethod
    def normalize_key(key: str) -> str:
        """Normalize a memory key for consistent lookup."""
        normalized = "_".join(key.strip().lower().split())
        return normalized.replace("-", "_")

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _ensure_schema(self) -> None:
        conn = self._get_connection()
        try:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS memories (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    category TEXT NOT NULL DEFAULT 'general',
                    source TEXT DEFAULT 'user',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS conversation_turns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_memories_category
                ON memories(category, updated_at);

                CREATE INDEX IF NOT EXISTS idx_turns_session
                ON conversation_turns(session_id, id);
                """
            )
            conn.commit()
        finally:
            conn.close()

    def _load_profile_seed(self) -> None:
        """Load local-only durable profile facts without overwriting explicit memories."""
        if not self.profile_seed_path.exists():
            return

        try:
            payload = json.loads(self.profile_seed_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to load profile seed from %s: %s", self.profile_seed_path, exc)
            return

        if not isinstance(payload, list):
            logger.warning("Profile seed must be a JSON list: %s", self.profile_seed_path)
            return

        now = _utcnow()
        seeded = 0
        conn = self._get_connection()
        try:
            for item in payload:
                if not isinstance(item, dict):
                    continue

                raw_key = str(item.get("key", "")).strip()
                raw_value = str(item.get("value", "")).strip()
                raw_category = str(item.get("category", "general")).strip() or "general"

                if not raw_key or not raw_value:
                    continue

                normalized_key = self.normalize_key(raw_key)
                existing = conn.execute(
                    "SELECT source FROM memories WHERE key = ?",
                    (normalized_key,),
                ).fetchone()

                # Preserve facts the user explicitly updated through conversation/tools.
                if existing and existing["source"] != "profile_seed":
                    continue

                conn.execute(
                    """
                    INSERT INTO memories (key, value, category, source, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(key) DO UPDATE SET
                        value = excluded.value,
                        category = excluded.category,
                        source = excluded.source,
                        updated_at = excluded.updated_at
                    """,
                    (normalized_key, raw_value, raw_category, "profile_seed", now, now),
                )
                seeded += 1
            conn.commit()
        finally:
            conn.close()

        if seeded:
            logger.info("Loaded %d profile seed fact(s) from %s", seeded, self.profile_seed_path)

    def _load_session_state(self) -> dict[str, Any]:
        if not self.session_state_path.exists():
            return {}
        try:
            return json.loads(self.session_state_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    def _save_session_state(self, session_id: str) -> None:
        payload = {
            "session_id": session_id,
            "updated_at": _utcnow(),
        }
        self.session_state_path.parent.mkdir(parents=True, exist_ok=True)
        self.session_state_path.write_text(
            json.dumps(payload, indent=2),
            encoding="utf-8",
        )

    def get_active_session_id(self) -> str:
        """Return the current active session ID, creating one if needed."""
        state = self._load_session_state()
        session_id = state.get("session_id")
        if session_id:
            return str(session_id)
        return self.start_new_session()

    def start_new_session(self) -> str:
        """Create and persist a new active session ID."""
        session_id = str(uuid.uuid4())
        self._save_session_state(session_id)
        return session_id

    def remember(
        self,
        key: str,
        value: str,
        category: str = "general",
        source: str = "user",
    ) -> str:
        """Create or update a durable memory record."""
        normalized_key = self.normalize_key(key)
        now = _utcnow()
        conn = self._get_connection()
        try:
            conn.execute(
                """
                INSERT INTO memories (key, value, category, source, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    category = excluded.category,
                    source = excluded.source,
                    updated_at = excluded.updated_at
                """,
                (normalized_key, value.strip(), category.strip() or "general", source, now, now),
            )
            conn.commit()
        finally:
            conn.close()
        return normalized_key

    def forget(self, key: str) -> bool:
        """Delete a durable memory record by key."""
        normalized_key = self.normalize_key(key)
        conn = self._get_connection()
        try:
            cursor = conn.execute("DELETE FROM memories WHERE key = ?", (normalized_key,))
            conn.commit()
            return (cursor.rowcount or 0) > 0
        finally:
            conn.close()

    def list_memories(
        self,
        category: str = "",
        limit: int = 50,
    ) -> list[dict[str, str]]:
        """List durable memory records."""
        conn = self._get_connection()
        try:
            if category:
                rows = conn.execute(
                    """
                    SELECT key, value, category, source, updated_at
                    FROM memories
                    WHERE category = ?
                    ORDER BY updated_at DESC, key ASC
                    LIMIT ?
                    """,
                    (category, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT key, value, category, source, updated_at
                    FROM memories
                    ORDER BY updated_at DESC, key ASC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def search_memories(
        self,
        query: str = "",
        category: str = "",
        limit: int = 10,
    ) -> list[dict[str, str]]:
        """Search durable memory records by key or value."""
        conn = self._get_connection()
        try:
            if query:
                like = f"%{query.strip()}%"
                if category:
                    rows = conn.execute(
                        """
                        SELECT key, value, category, source, updated_at
                        FROM memories
                        WHERE category = ?
                          AND (key LIKE ? OR value LIKE ?)
                        ORDER BY updated_at DESC, key ASC
                        LIMIT ?
                        """,
                        (category, like, like, limit),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        """
                        SELECT key, value, category, source, updated_at
                        FROM memories
                        WHERE key LIKE ? OR value LIKE ?
                        ORDER BY updated_at DESC, key ASC
                        LIMIT ?
                        """,
                        (like, like, limit),
                    ).fetchall()
            else:
                rows = self.list_memories(category=category, limit=limit)
                return rows
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def count_memories(self) -> int:
        """Count durable memory records."""
        conn = self._get_connection()
        try:
            row = conn.execute("SELECT COUNT(*) AS count FROM memories").fetchone()
            return int(row["count"]) if row else 0
        finally:
            conn.close()

    def build_memory_summary(self, limit: int = 12) -> str:
        """Render a compact summary of durable memory."""
        rows = self.list_memories(limit=limit)
        if not rows:
            return "No durable memory stored yet."

        lines = ["Remembered user facts:"]
        for row in rows:
            key = row["key"].replace("_", " ")
            lines.append(f"- [{row['category']}] {key}: {row['value']}")
        return "\n".join(lines)

    def save_turn(self, session_id: str, role: str, content: str) -> None:
        """Persist one conversation turn."""
        if not content.strip():
            return
        conn = self._get_connection()
        try:
            conn.execute(
                """
                INSERT INTO conversation_turns (session_id, role, content, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (session_id, role, content.strip(), _utcnow()),
            )
            conn.commit()
        finally:
            conn.close()

    def get_recent_turns(self, session_id: str, limit: int = 6) -> list[dict[str, str]]:
        """Fetch recent turns for one session."""
        conn = self._get_connection()
        try:
            rows = conn.execute(
                """
                SELECT role, content, created_at
                FROM conversation_turns
                WHERE session_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (session_id, limit),
            ).fetchall()
            ordered = list(reversed(rows))
            return [dict(row) for row in ordered]
        finally:
            conn.close()

    def render_recent_turns(self, session_id: str, limit: int = 6) -> str:
        """Render recent turns as compact prompt context."""
        turns = self.get_recent_turns(session_id, limit=limit)
        if not turns:
            return "No recent conversation context yet."

        rendered: list[str] = []
        for turn in turns:
            compact = " ".join(turn["content"].split())
            if len(compact) > 280:
                compact = compact[:277] + "..."
            rendered.append(f"{turn['role'].title()}: {compact}")
        return "\n".join(rendered)


MEMORY_STORE = MemoryStore()


async def remember_fact(
    key: Annotated[str, "Short memory key, such as name, birthday, hobby, spouse, or favorite_team"],
    value: Annotated[str, "The fact value to remember for the user"],
    category: Annotated[str, "Memory category, such as identity, family, preference, contact, or biography"] = "general",
) -> str:
    """Remember or update a durable user fact."""
    normalized_key = MEMORY_STORE.remember(key, value, category=category, source="explicit_memory")
    log_action(
        "Memory",
        "remember_fact",
        f"{normalized_key}={value[:120]}",
        f"category={category}",
    )
    return f"✅ Remembered {normalized_key.replace('_', ' ')}."


async def search_memory(
    query: Annotated[str, "Words to search for in remembered facts. Leave blank to list all memories"] = "",
    category: Annotated[str, "Optional category filter"] = "",
    limit: Annotated[int, "Maximum number of memories to return"] = 10,
) -> str:
    """Search remembered facts."""
    rows = MEMORY_STORE.search_memories(query=query, category=category, limit=limit)
    if not rows:
        return "No matching memory found."

    lines = ["🧠 Memory matches"]
    for row in rows:
        pretty_key = row["key"].replace("_", " ")
        lines.append(f"- [{row['category']}] {pretty_key}: {row['value']}")

    log_action(
        "Memory",
        "search_memory",
        f"query={query}, category={category}, limit={limit}",
        f"matches={len(rows)}",
    )
    return "\n".join(lines)


async def get_memory_summary() -> str:
    """Return a compact summary of remembered user facts."""
    summary = MEMORY_STORE.build_memory_summary(limit=20)
    log_action("Memory", "get_memory_summary", output_summary=f"chars={len(summary)}")
    return summary


async def forget_fact(
    key: Annotated[str, "Memory key to delete, such as birthday or hobby"],
) -> str:
    """Forget a stored user fact."""
    deleted = MEMORY_STORE.forget(key)
    log_action("Memory", "forget_fact", key, status="completed" if deleted else "not_found")
    if deleted:
        return f"🗑️ Forgot {MEMORY_STORE.normalize_key(key).replace('_', ' ')}."
    return "Memory key not found."


MEMORY_TOOLS = [remember_fact, search_memory, get_memory_summary, forget_fact]
