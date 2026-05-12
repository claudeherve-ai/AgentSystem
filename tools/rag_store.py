"""
RAG store — local SQLite-backed semantic + FTS5 index over Work_cases\\Cases\\.

Indexes every case artifact (PDF, DOCX, XLSX, HTML, JSON, log, code, text) into
chunks with optional Azure OpenAI embeddings. Falls back to FTS5-only search
when no embedding deployment is configured (`RAG_EMBEDDINGS_ENABLED=false`,
deployment missing, or transient embed failure).

Embeddings are stored as raw float32 bytes via `array.array('f', ...)` so the
store is portable across machines without requiring numpy at write time.
Cosine search uses numpy when available and a pure-Python fallback otherwise.
"""

from __future__ import annotations

import array
import asyncio
import hashlib
import json
import logging
import math
import os
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional

import httpx

from .audit import audit_log

logger = logging.getLogger(__name__)

# ── Storage ──────────────────────────────────────────────────────────────────
RAG_DIR = Path(__file__).resolve().parent.parent / "memory"
RAG_DIR.mkdir(parents=True, exist_ok=True)
RAG_DB = RAG_DIR / "rag_store.db"

# ── Indexer config ───────────────────────────────────────────────────────────
_INDEXABLE_EXTS = {
    ".txt", ".md", ".log", ".csv", ".json", ".yaml", ".yml",
    ".py", ".js", ".ts", ".tsx", ".jsx", ".ps1", ".sh", ".bat",
    ".sql", ".html", ".htm", ".xml", ".ini", ".cfg", ".toml",
    ".pdf", ".docx", ".xlsx",
}
_MAX_FILE_BYTES = 5 * 1024 * 1024  # 5 MB per file
_CHUNK_SIZE = 800
_CHUNK_OVERLAP = 100
_EMBED_DIM_HINT = 1536  # text-embedding-3-small default

# ── Embeddings warning gate (emit once, not on every call) ───────────────────
_EMBED_WARNED = False


# ── Public default for cases root ────────────────────────────────────────────
def default_cases_root() -> Path:
    """Resolve the default Work_cases\\Cases\\ folder.

    Honors `CASES_ROOT` env var, falls back to the conventional OneDrive path,
    and finally to `~/Work_cases/Cases` so the module never raises on import.
    """
    explicit = (os.getenv("CASES_ROOT") or "").strip().strip('"').strip("'")
    if explicit:
        return Path(os.path.expandvars(os.path.expanduser(explicit))).resolve()
    home = Path.home()
    candidate = home / "OneDrive - Microsoft" / "Work_cases" / "Cases"
    if candidate.exists():
        return candidate.resolve()
    return (home / "Work_cases" / "Cases").resolve()


# ── Embedding config helpers ─────────────────────────────────────────────────
def _env(name: str, default: str = "") -> str:
    val = os.getenv(name, default)
    if val is None:
        return ""
    return val.strip().strip('"').strip("'")


def embeddings_enabled() -> bool:
    """Return True only when a deployment is configured AND not explicitly disabled."""
    flag = _env("RAG_EMBEDDINGS_ENABLED", "auto").lower()
    if flag in {"false", "0", "no", "off"}:
        return False
    deployment = _env("AZURE_EMBEDDING_DEPLOYMENT") or _env("AZURE_OPENAI_EMBEDDING_DEPLOYMENT")
    endpoint = _env("AZURE_OPENAI_ENDPOINT")
    api_key = _env("AZURE_OPENAI_API_KEY")
    if not (deployment and endpoint and api_key):
        return False
    return True


def embeddings_status() -> dict[str, str]:
    """Return a small status dict for diagnostics / smoke tests."""
    return {
        "enabled": str(embeddings_enabled()).lower(),
        "deployment": _env("AZURE_EMBEDDING_DEPLOYMENT")
        or _env("AZURE_OPENAI_EMBEDDING_DEPLOYMENT")
        or "<unset>",
        "api_version": _env("AZURE_EMBEDDING_API_VERSION", "2024-12-01-preview"),
        "flag": _env("RAG_EMBEDDINGS_ENABLED", "auto").lower(),
    }


# ── Connection / schema ──────────────────────────────────────────────────────
def _connect(db_path: Path | None = None) -> sqlite3.Connection:
    target = db_path or RAG_DB
    conn = sqlite3.connect(str(target))
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS case_documents ("
        "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "  case_folder TEXT NOT NULL,"
        "  file_path TEXT NOT NULL UNIQUE,"
        "  file_hash TEXT,"
        "  mtime REAL,"
        "  size INTEGER,"
        "  indexed_at TEXT NOT NULL"
        ")"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_docs_case ON case_documents(case_folder)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS case_chunks ("
        "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "  document_id INTEGER NOT NULL REFERENCES case_documents(id) ON DELETE CASCADE,"
        "  chunk_index INTEGER NOT NULL,"
        "  content TEXT NOT NULL,"
        "  embedding BLOB,"
        "  created_at TEXT NOT NULL"
        ")"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_chunks_doc ON case_chunks(document_id)"
    )
    conn.execute(
        "CREATE VIRTUAL TABLE IF NOT EXISTS case_chunks_fts USING fts5("
        "  content, case_folder UNINDEXED, file_path UNINDEXED, chunk_index UNINDEXED,"
        "  document_id UNINDEXED, chunk_id UNINDEXED, tokenize='porter unicode61'"
        ")"
    )
    return conn


# ── File walking + reading ──────────────────────────────────────────────────
def _iter_indexable(root: Path, only_case_folder: Optional[str] = None) -> Iterable[Path]:
    if not root.exists() or not root.is_dir():
        return
    if only_case_folder:
        sub = root / only_case_folder
        if not sub.exists() or not sub.is_dir():
            return
        scan_root = sub
    else:
        scan_root = root
    for f in scan_root.rglob("*"):
        try:
            if not f.is_file():
                continue
            if f.suffix.lower() not in _INDEXABLE_EXTS:
                continue
            if f.stat().st_size > _MAX_FILE_BYTES:
                continue
        except OSError:
            continue
        yield f


def _read_artifact(p: Path) -> Optional[str]:
    """Read a case artifact for indexing — reuses file_reader's soft-dep handlers."""
    ext = p.suffix.lower()
    try:
        if ext == ".pdf":
            from .file_reader import _read_pdf
            text = _read_pdf(p)
        elif ext == ".docx":
            from .file_reader import _read_docx
            text = _read_docx(p)
        elif ext == ".xlsx":
            from .file_reader import _read_xlsx
            text = _read_xlsx(p)
        elif ext in {".html", ".htm"}:
            from .file_reader import _read_html
            text = _read_html(p)
        elif ext == ".json":
            from .file_reader import _read_json
            text = _read_json(p)
        else:
            text = p.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:  # noqa: BLE001
        logger.warning("RAG: failed to read %s: %s", p, exc)
        return None
    if not text or not text.strip():
        return None
    if text.startswith("[") and ("reader unavailable" in text or "read failed" in text):
        # file_reader returned a placeholder string — treat as no content
        return None
    return text


def _chunk_text(text: str, size: int = _CHUNK_SIZE, overlap: int = _CHUNK_OVERLAP) -> list[str]:
    text = re.sub(r"[ \t]+", " ", text).strip()
    if not text:
        return []
    if len(text) <= size:
        return [text]
    chunks: list[str] = []
    step = max(1, size - overlap)
    for start in range(0, len(text), step):
        piece = text[start : start + size].strip()
        if piece:
            chunks.append(piece)
        if start + size >= len(text):
            break
    return chunks


def _hash_file(p: Path) -> str:
    h = hashlib.sha1()
    try:
        with p.open("rb") as fh:
            for blk in iter(lambda: fh.read(65536), b""):
                h.update(blk)
        return h.hexdigest()
    except OSError:
        return ""


# ── Embedding helpers ────────────────────────────────────────────────────────
def _pack_embedding(vec: list[float]) -> bytes:
    return array.array("f", vec).tobytes()


def _unpack_embedding(blob: bytes) -> list[float]:
    a = array.array("f")
    a.frombytes(blob)
    return list(a)


async def _embed_text(text: str, *, timeout: float = 30.0) -> Optional[list[float]]:
    """Call Azure OpenAI Embeddings; return None on disable / failure."""
    global _EMBED_WARNED
    if not embeddings_enabled():
        return None
    deployment = _env("AZURE_EMBEDDING_DEPLOYMENT") or _env("AZURE_OPENAI_EMBEDDING_DEPLOYMENT")
    endpoint = _env("AZURE_OPENAI_ENDPOINT").rstrip("/")
    api_key = _env("AZURE_OPENAI_API_KEY")
    api_version = _env("AZURE_EMBEDDING_API_VERSION", "2024-12-01-preview")
    url = f"{endpoint}/openai/deployments/{deployment}/embeddings?api-version={api_version}"
    headers = {"api-key": api_key, "Content-Type": "application/json"}
    payload = {"input": text[:8000]}
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, headers=headers, json=payload)
        if resp.status_code != 200:
            if not _EMBED_WARNED:
                logger.warning(
                    "RAG: embedding endpoint returned %s — falling back to FTS5. "
                    "Body (truncated): %s",
                    resp.status_code,
                    resp.text[:300],
                )
                _EMBED_WARNED = True
            return None
        data = resp.json()
        vec = data.get("data", [{}])[0].get("embedding")
        if not vec or not isinstance(vec, list):
            return None
        return [float(x) for x in vec]
    except Exception as exc:  # noqa: BLE001
        if not _EMBED_WARNED:
            logger.warning("RAG: embedding call failed (%s) — falling back to FTS5.", exc)
            _EMBED_WARNED = True
        return None


def _cosine(a: list[float], b: list[float]) -> float:
    try:
        import numpy as np  # type: ignore
        va = np.asarray(a, dtype=np.float32)
        vb = np.asarray(b, dtype=np.float32)
        denom = float(np.linalg.norm(va) * np.linalg.norm(vb))
        if denom == 0.0:
            return 0.0
        return float(np.dot(va, vb) / denom)
    except Exception:  # noqa: BLE001
        # Pure-Python fallback
        if not a or not b:
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        na = math.sqrt(sum(x * x for x in a))
        nb = math.sqrt(sum(y * y for y in b))
        if na == 0.0 or nb == 0.0:
            return 0.0
        return dot / (na * nb)


# ── Public dataclasses ──────────────────────────────────────────────────────
@dataclass
class IndexResult:
    indexed: int = 0
    skipped: int = 0
    failed: int = 0
    embedded: int = 0
    fts_only: int = 0
    files_scanned: int = 0
    cases_seen: set[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.cases_seen is None:
            self.cases_seen = set()


@dataclass
class SearchHit:
    case_folder: str
    file_path: str
    chunk_index: int
    snippet: str
    score: float
    source: str  # "semantic" | "fts" | "hybrid"


# ── Indexing ─────────────────────────────────────────────────────────────────
async def index_cases(
    root: Path,
    only_case_folder: Optional[str] = None,
    *,
    full_rebuild: bool = False,
    db_path: Path | None = None,
) -> IndexResult:
    """Walk `root` (filtered by `only_case_folder` if given), index changed files."""
    result = IndexResult()
    if not root.exists():
        return result

    conn = _connect(db_path)
    try:
        if full_rebuild:
            if only_case_folder:
                conn.execute(
                    "DELETE FROM case_chunks WHERE document_id IN ("
                    "  SELECT id FROM case_documents WHERE case_folder = ?"
                    ")",
                    (only_case_folder,),
                )
                conn.execute(
                    "DELETE FROM case_chunks_fts WHERE case_folder = ?",
                    (only_case_folder,),
                )
                conn.execute(
                    "DELETE FROM case_documents WHERE case_folder = ?",
                    (only_case_folder,),
                )
            else:
                conn.execute("DELETE FROM case_chunks")
                conn.execute("DELETE FROM case_chunks_fts")
                conn.execute("DELETE FROM case_documents")
            conn.commit()

        for f in _iter_indexable(root, only_case_folder=only_case_folder):
            result.files_scanned += 1
            try:
                rel = f.relative_to(root)
            except ValueError:
                continue
            parts = rel.parts
            if not parts:
                continue
            case_folder = parts[0]
            result.cases_seen.add(case_folder)

            try:
                mtime = f.stat().st_mtime
                size = f.stat().st_size
            except OSError:
                result.failed += 1
                continue

            existing = conn.execute(
                "SELECT id, mtime FROM case_documents WHERE file_path = ?",
                (str(f),),
            ).fetchone()
            if existing and not full_rebuild and abs((existing[1] or 0) - mtime) < 1:
                result.skipped += 1
                continue

            text = _read_artifact(f)
            if text is None:
                result.failed += 1
                continue
            chunks = _chunk_text(text)
            if not chunks:
                result.failed += 1
                continue

            file_hash = _hash_file(f)
            now = datetime.now(timezone.utc).isoformat()

            if existing:
                doc_id = existing[0]
                # Replace its chunks
                conn.execute(
                    "DELETE FROM case_chunks WHERE document_id = ?", (doc_id,)
                )
                conn.execute(
                    "DELETE FROM case_chunks_fts WHERE document_id = ?", (doc_id,)
                )
                conn.execute(
                    "UPDATE case_documents SET case_folder = ?, file_hash = ?, "
                    "mtime = ?, size = ?, indexed_at = ? WHERE id = ?",
                    (case_folder, file_hash, mtime, size, now, doc_id),
                )
            else:
                cur = conn.execute(
                    "INSERT INTO case_documents(case_folder, file_path, file_hash, "
                    "mtime, size, indexed_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (case_folder, str(f), file_hash, mtime, size, now),
                )
                doc_id = cur.lastrowid

            embed_this_file = embeddings_enabled()
            for idx, chunk in enumerate(chunks):
                vec_blob: Optional[bytes] = None
                if embed_this_file:
                    vec = await _embed_text(chunk)
                    if vec:
                        vec_blob = _pack_embedding(vec)
                cur = conn.execute(
                    "INSERT INTO case_chunks(document_id, chunk_index, content, "
                    "embedding, created_at) VALUES (?, ?, ?, ?, ?)",
                    (doc_id, idx, chunk, vec_blob, now),
                )
                chunk_id = cur.lastrowid
                conn.execute(
                    "INSERT INTO case_chunks_fts(rowid, content, case_folder, "
                    "file_path, chunk_index, document_id, chunk_id) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (chunk_id, chunk, case_folder, str(f), idx, doc_id, chunk_id),
                )
            if embed_this_file:
                result.embedded += 1
            else:
                result.fts_only += 1
            result.indexed += 1
            # Yield occasionally so a long index doesn't block the loop
            if result.indexed % 25 == 0:
                await asyncio.sleep(0)
        conn.commit()
    finally:
        conn.close()

    return result


# ── Search ───────────────────────────────────────────────────────────────────
def _semantic_search(
    conn: sqlite3.Connection,
    query_vec: list[float],
    top_k: int,
    case_folder: Optional[str],
) -> list[SearchHit]:
    sql = (
        "SELECT c.id, c.document_id, c.chunk_index, c.content, c.embedding, "
        "       d.case_folder, d.file_path "
        "FROM case_chunks c JOIN case_documents d ON c.document_id = d.id "
        "WHERE c.embedding IS NOT NULL"
    )
    params: list = []
    if case_folder:
        sql += " AND d.case_folder = ?"
        params.append(case_folder)
    rows = conn.execute(sql, params).fetchall()
    scored: list[SearchHit] = []
    for chunk_id, _doc_id, chunk_idx, content, blob, case, path in rows:
        if not blob:
            continue
        try:
            vec = _unpack_embedding(blob)
        except Exception:  # noqa: BLE001
            continue
        score = _cosine(query_vec, vec)
        scored.append(
            SearchHit(
                case_folder=case,
                file_path=path,
                chunk_index=int(chunk_idx),
                snippet=content[:600],
                score=float(score),
                source="semantic",
            )
        )
    scored.sort(key=lambda h: h.score, reverse=True)
    return scored[:top_k]


def _fts_search(
    conn: sqlite3.Connection,
    query: str,
    top_k: int,
    case_folder: Optional[str],
) -> list[SearchHit]:
    sql = (
        "SELECT case_folder, file_path, chunk_index, "
        "       snippet(case_chunks_fts, 0, '**', '**', '…', 24), rank "
        "FROM case_chunks_fts WHERE case_chunks_fts MATCH ?"
    )
    params: list = [query]
    if case_folder:
        sql += " AND case_folder = ?"
        params.append(case_folder)
    sql += " ORDER BY rank LIMIT ?"
    params.append(top_k)
    try:
        rows = conn.execute(sql, params).fetchall()
    except sqlite3.OperationalError as exc:
        logger.debug("RAG FTS query failed: %s", exc)
        return []
    return [
        SearchHit(
            case_folder=case,
            file_path=path,
            chunk_index=int(chunk_idx),
            snippet=snippet,
            score=-float(rank),  # rank is negative-ish; flip so higher = better
            source="fts",
        )
        for case, path, chunk_idx, snippet, rank in rows
    ]


async def search_cases(
    query: str,
    top_k: int = 5,
    case_folder: Optional[str] = None,
    db_path: Path | None = None,
) -> list[SearchHit]:
    """Hybrid case search — semantic when available, FTS5 fallback, merged when both."""
    if not query or not query.strip():
        return []
    top_k = max(1, min(20, int(top_k or 5)))
    query = query.strip()

    target = db_path or RAG_DB
    if not target.exists():
        return []

    conn = _connect(db_path)
    try:
        sem_hits: list[SearchHit] = []
        if embeddings_enabled():
            qvec = await _embed_text(query)
            if qvec:
                sem_hits = _semantic_search(conn, qvec, top_k, case_folder)
        fts_hits = _fts_search(conn, _safe_fts_query(query), top_k, case_folder)
    finally:
        conn.close()

    # Merge: dedupe by (file_path, chunk_index), prefer semantic score
    by_key: dict[tuple[str, int], SearchHit] = {}
    for h in sem_hits:
        by_key[(h.file_path, h.chunk_index)] = h
    for h in fts_hits:
        key = (h.file_path, h.chunk_index)
        if key in by_key:
            existing = by_key[key]
            by_key[key] = SearchHit(
                case_folder=existing.case_folder,
                file_path=existing.file_path,
                chunk_index=existing.chunk_index,
                snippet=existing.snippet,
                score=existing.score + 0.05,  # small bonus for appearing in both
                source="hybrid",
            )
        else:
            by_key[key] = h
    merged = sorted(by_key.values(), key=lambda h: h.score, reverse=True)
    return merged[:top_k]


def _safe_fts_query(query: str) -> str:
    """Sanitize query for FTS5 — strip control chars, quote bare phrases."""
    cleaned = re.sub(r'["\']', "", query)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if not cleaned:
        return query
    # If query has only word chars + spaces, leave it for default FTS parsing.
    if re.fullmatch(r"[\w\s\.\-/]+", cleaned):
        return cleaned
    # Otherwise quote it as a phrase.
    return f'"{cleaned}"'


# ── Listing ─────────────────────────────────────────────────────────────────
def list_indexed(db_path: Path | None = None) -> dict[str, dict[str, int]]:
    """Return {case_folder: {documents: N, chunks: M, embedded_chunks: K}}."""
    target = db_path or RAG_DB
    if not target.exists():
        return {}
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            "SELECT d.case_folder, COUNT(DISTINCT d.id), COUNT(c.id), "
            "       SUM(CASE WHEN c.embedding IS NOT NULL THEN 1 ELSE 0 END) "
            "FROM case_documents d LEFT JOIN case_chunks c ON c.document_id = d.id "
            "GROUP BY d.case_folder ORDER BY d.case_folder"
        ).fetchall()
    finally:
        conn.close()
    return {
        case: {
            "documents": int(docs or 0),
            "chunks": int(chunks or 0),
            "embedded_chunks": int(embedded or 0),
        }
        for case, docs, chunks, embedded in rows
    }
