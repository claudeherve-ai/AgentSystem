"""
Knowledge base tool — local SQLite FTS5 index over the user's files.

Lets the agent index a directory or file once, then perform fast full-text
search across it later. Stores nothing remote; everything is local.
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Annotated

from pydantic import Field

from .audit import audit_log

logger = logging.getLogger(__name__)

KB_DIR = Path(__file__).resolve().parent.parent / "memory"
KB_DIR.mkdir(parents=True, exist_ok=True)
KB_DB = KB_DIR / "knowledge_base.db"

_INDEXABLE_EXTS = {
    ".txt", ".md", ".log", ".csv", ".json", ".yaml", ".yml",
    ".py", ".js", ".ts", ".tsx", ".jsx", ".ps1", ".sh", ".bat",
    ".sql", ".html", ".htm", ".xml", ".ini", ".cfg", ".toml",
    ".pdf", ".docx",
}
_MAX_FILE_BYTES = 5 * 1024 * 1024  # 5 MB cap per file


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(KB_DB))
    conn.execute(
        "CREATE VIRTUAL TABLE IF NOT EXISTS docs USING fts5("
        "path, body, mtime UNINDEXED, tokenize='porter unicode61')"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS sources ("
        "path TEXT PRIMARY KEY, mtime REAL, size INTEGER, indexed_at TEXT)"
    )
    return conn


def _read_for_index(p: Path) -> str | None:
    """Read a file for indexing — uses file_reader's logic for soft-dep formats."""
    if p.suffix.lower() in {".pdf", ".docx"}:
        try:
            if p.suffix.lower() == ".pdf":
                import pdfplumber  # type: ignore

                with pdfplumber.open(str(p)) as pdf:
                    return "\n".join((page.extract_text() or "") for page in pdf.pages)
            else:
                from docx import Document  # type: ignore

                doc = Document(str(p))
                return "\n".join(para.text for para in doc.paragraphs)
        except ImportError:
            logger.debug("Skipping %s (reader dep missing)", p)
            return None
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to read %s: %s", p, exc)
            return None
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to read %s: %s", p, exc)
        return None


async def kb_index(
    path: Annotated[str, Field(description="File or directory to index")],
    recursive: Annotated[bool, Field(description="If a directory, descend into subfolders")] = True,
) -> str:
    """
    Index a file or all eligible files in a directory into the knowledge base.

    Re-indexes when the file's mtime has changed. Returns a summary.
    """
    audit_id = audit_log("KB.index", "started", {"path": path, "recursive": recursive})
    p = Path(path).expanduser().resolve()
    if not p.exists():
        return f"Path not found: {p}"

    targets: list[Path] = []
    if p.is_file():
        if p.suffix.lower() in _INDEXABLE_EXTS:
            targets.append(p)
    else:
        glob = "**/*" if recursive else "*"
        for f in p.glob(glob):
            if f.is_file() and f.suffix.lower() in _INDEXABLE_EXTS:
                try:
                    if f.stat().st_size <= _MAX_FILE_BYTES:
                        targets.append(f)
                except OSError:
                    continue

    if not targets:
        return f"No indexable files found under {p}"

    indexed = 0
    skipped = 0
    failed = 0
    from datetime import datetime, timezone

    conn = _connect()
    try:
        for f in targets:
            try:
                mtime = f.stat().st_mtime
                size = f.stat().st_size
            except OSError:
                failed += 1
                continue
            existing = conn.execute(
                "SELECT mtime FROM sources WHERE path = ?", (str(f),)
            ).fetchone()
            if existing and abs(existing[0] - mtime) < 1:
                skipped += 1
                continue
            body = _read_for_index(f)
            if body is None:
                failed += 1
                continue
            conn.execute("DELETE FROM docs WHERE path = ?", (str(f),))
            conn.execute(
                "INSERT INTO docs(path, body, mtime) VALUES (?, ?, ?)",
                (str(f), body, mtime),
            )
            conn.execute(
                "INSERT OR REPLACE INTO sources(path, mtime, size, indexed_at) VALUES (?, ?, ?, ?)",
                (str(f), mtime, size, datetime.now(timezone.utc).isoformat()),
            )
            indexed += 1
        conn.commit()
    finally:
        conn.close()

    audit_log(
        "KB.index",
        "completed",
        {"indexed": indexed, "skipped": skipped, "failed": failed},
        parent_id=audit_id,
    )
    return (
        f"Indexed: {indexed}, skipped (unchanged): {skipped}, failed: {failed}. "
        f"KB at {KB_DB}."
    )


async def kb_search(
    query: Annotated[str, Field(description="Full-text query (FTS5 syntax allowed)")],
    top_k: Annotated[int, Field(description="Maximum number of hits to return (1-20)")] = 5,
) -> str:
    """Search the knowledge base. Returns a snippet + path for each hit."""
    audit_id = audit_log("KB.search", "started", {"query": query})
    top_k = max(1, min(20, int(top_k or 5)))
    if not KB_DB.exists():
        return "Knowledge base is empty. Use `kb_index` first."

    conn = _connect()
    try:
        try:
            rows = conn.execute(
                "SELECT path, snippet(docs, 1, '**', '**', '…', 24) AS s, "
                "rank FROM docs WHERE docs MATCH ? ORDER BY rank LIMIT ?",
                (query, top_k),
            ).fetchall()
        except sqlite3.OperationalError as exc:
            return f"Search failed (FTS5 syntax?): {exc!s}"
    finally:
        conn.close()

    audit_log("KB.search", "completed", {"hits": len(rows)}, parent_id=audit_id)
    if not rows:
        return f"No KB hits for {query!r}."
    out = [f"# KB hits for {query!r}"]
    for path, snippet, _rank in rows:
        out.append(f"\n**{path}**\n{snippet}")
    return "\n".join(out)


async def kb_list_sources(
    limit: Annotated[int, Field(description="Maximum number of sources to list (1-200)")] = 50,
) -> str:
    """List indexed source files."""
    if not KB_DB.exists():
        return "Knowledge base is empty."
    limit = max(1, min(200, int(limit or 50)))
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT path, size, indexed_at FROM sources ORDER BY indexed_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        total = conn.execute("SELECT COUNT(*) FROM sources").fetchone()[0]
    finally:
        conn.close()
    if not rows:
        return "Knowledge base is empty."
    out = [f"# Indexed sources ({total} total, showing {len(rows)})"]
    for path, size, indexed_at in rows:
        out.append(f"- `{path}` — {size} B — indexed {indexed_at}")
    return "\n".join(out)


KNOWLEDGE_BASE_TOOLS = [kb_index, kb_search, kb_list_sources]
