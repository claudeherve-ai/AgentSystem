"""
RAG tools — semantic + FTS5 search over Work_cases\\Cases\\.

Exposes 4 function tools for the orchestrator and specialists:
- case_index_rebuild : full rescan (slow; use after first deploy or major changes)
- case_index_update  : incremental, mtime-based (cheap; safe to call often)
- case_search        : hybrid semantic+FTS search; returns ranked chunks
- case_list_indexed  : show what's currently in the local RAG store

All tools NEVER raise — they return human-readable strings and audit-log
their lifecycle.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Annotated, Optional

from pydantic import Field

from .audit import audit_log
from .rag_store import (
    RAG_DB,
    default_cases_root,
    embeddings_status,
    index_cases,
    list_indexed,
    search_cases,
)

logger = logging.getLogger(__name__)


def _format_status_hint() -> str:
    s = embeddings_status()
    if s["enabled"] == "true":
        return f"(embeddings: ON, deployment={s['deployment']})"
    return (
        "(embeddings: OFF — running FTS-only. Set AZURE_EMBEDDING_DEPLOYMENT "
        "in .env to enable semantic search)"
    )


def _resolve_root(case_folder: Optional[str]) -> Path:
    return default_cases_root()


async def case_index_rebuild(
    case_folder: Annotated[
        str,
        Field(
            default="",
            description=(
                "Optional case-folder name to rebuild (e.g. '2026-02-19_SR_1234567'). "
                "Empty = rebuild ALL cases under CASES_ROOT."
            ),
        ),
    ] = "",
) -> str:
    """Drop and rebuild the local case index from scratch (slow).

    Use after a fresh deploy, after upgrading the indexer, or when a case folder
    is suspected to have stale entries. For routine refresh use `case_index_update`.
    """
    audit_id = audit_log(
        "RAG.index_rebuild",
        "started",
        {"case_folder": case_folder or "<all>"},
    )
    folder = (case_folder or "").strip() or None
    root = _resolve_root(folder)
    if not root.exists():
        msg = (
            f"Cases root not found: {root}. "
            f"Set CASES_ROOT in .env to the correct path."
        )
        audit_log("RAG.index_rebuild", "error", {"reason": "no_root", "root": str(root)}, parent_id=audit_id)
        return msg

    result = await index_cases(root, only_case_folder=folder, full_rebuild=True)
    audit_log(
        "RAG.index_rebuild",
        "completed",
        {
            "indexed": result.indexed,
            "skipped": result.skipped,
            "failed": result.failed,
            "embedded_files": result.embedded,
            "fts_only_files": result.fts_only,
            "files_scanned": result.files_scanned,
            "cases": len(result.cases_seen),
        },
        parent_id=audit_id,
    )
    return (
        f"Case index rebuilt {_format_status_hint()}.\n"
        f"  Cases touched : {len(result.cases_seen)}\n"
        f"  Files scanned : {result.files_scanned}\n"
        f"  Indexed       : {result.indexed}\n"
        f"  Skipped       : {result.skipped}\n"
        f"  Failed        : {result.failed}\n"
        f"  Files embedded: {result.embedded}\n"
        f"  FTS-only files: {result.fts_only}\n"
        f"  Store         : {RAG_DB}"
    )


async def case_index_update(
    case_folder: Annotated[
        str,
        Field(
            default="",
            description=(
                "Optional case-folder name to refresh. Empty = refresh ALL cases."
            ),
        ),
    ] = "",
) -> str:
    """Incrementally update the case index (mtime-based; cheap to call)."""
    audit_id = audit_log(
        "RAG.index_update",
        "started",
        {"case_folder": case_folder or "<all>"},
    )
    folder = (case_folder or "").strip() or None
    root = _resolve_root(folder)
    if not root.exists():
        msg = (
            f"Cases root not found: {root}. "
            f"Set CASES_ROOT in .env to the correct path."
        )
        audit_log("RAG.index_update", "error", {"reason": "no_root", "root": str(root)}, parent_id=audit_id)
        return msg

    result = await index_cases(root, only_case_folder=folder, full_rebuild=False)
    audit_log(
        "RAG.index_update",
        "completed",
        {
            "indexed": result.indexed,
            "skipped": result.skipped,
            "failed": result.failed,
            "embedded_files": result.embedded,
            "fts_only_files": result.fts_only,
            "files_scanned": result.files_scanned,
            "cases": len(result.cases_seen),
        },
        parent_id=audit_id,
    )
    return (
        f"Case index updated {_format_status_hint()}.\n"
        f"  Cases touched : {len(result.cases_seen)}\n"
        f"  Files scanned : {result.files_scanned}\n"
        f"  Indexed (new) : {result.indexed}\n"
        f"  Skipped (same): {result.skipped}\n"
        f"  Failed        : {result.failed}\n"
        f"  Store         : {RAG_DB}"
    )


async def case_search(
    query: Annotated[str, Field(description="Free-text question or keywords to search across case artifacts.")],
    top_k: Annotated[int, Field(default=5, ge=1, le=20, description="Maximum number of chunks to return (1-20).")] = 5,
    case_folder: Annotated[
        str,
        Field(
            default="",
            description="Optional case-folder name to restrict the search (e.g. '2026-02-19_SR_1234567').",
        ),
    ] = "",
) -> str:
    """Search the local RAG store across Work_cases\\Cases\\ artifacts.

    Use this BEFORE answering any case-specific question — it grounds the answer
    in the user's actual case files instead of hallucinating from training data.
    Returns ranked snippets with file paths so the caller can cite or open them.
    """
    audit_id = audit_log(
        "RAG.search",
        "started",
        {"query": query[:200], "top_k": top_k, "case_folder": case_folder or "<all>"},
    )
    folder = (case_folder or "").strip() or None
    if not RAG_DB.exists() or not list_indexed():
        audit_log("RAG.search", "completed", {"hits": 0, "reason": "empty_index"}, parent_id=audit_id)
        return (
            "No case artifacts are indexed yet. Run `case_index_update` (or "
            "`case_index_rebuild` after first install) to populate the local "
            f"RAG store. Cases root: {default_cases_root()}"
        )

    hits = await search_cases(query, top_k=top_k, case_folder=folder)
    audit_log("RAG.search", "completed", {"hits": len(hits)}, parent_id=audit_id)
    if not hits:
        return (
            f"No case content matched: {query!r} {_format_status_hint()}.\n"
            f"Try broader terms, or run `case_index_update` if you've added new files."
        )

    lines = [f"Top {len(hits)} hits for: {query!r} {_format_status_hint()}\n"]
    for i, h in enumerate(hits, 1):
        lines.append(
            f"[{i}] case={h.case_folder!r}  score={h.score:.3f}  src={h.source}  chunk#{h.chunk_index}\n"
            f"    file: {h.file_path}\n"
            f"    {h.snippet.strip()[:500].replace(chr(10), ' ⏎ ')}\n"
        )
    return "\n".join(lines)


async def case_list_indexed() -> str:
    """List indexed case folders with document and chunk counts."""
    audit_id = audit_log("RAG.list", "started", {})
    summary = list_indexed()
    audit_log("RAG.list", "completed", {"cases": len(summary)}, parent_id=audit_id)
    if not summary:
        return (
            f"No case artifacts are indexed yet. Cases root: {default_cases_root()}. "
            f"Run `case_index_update` to populate the store."
        )
    lines = [f"Indexed cases ({len(summary)}) {_format_status_hint()}:"]
    for case, stats in summary.items():
        lines.append(
            f"  - {case}: {stats['documents']} docs, {stats['chunks']} chunks, "
            f"{stats['embedded_chunks']} embedded"
        )
    lines.append(f"\nStore: {RAG_DB}")
    return "\n".join(lines)


RAG_TOOLS = [
    case_search,
    case_index_update,
    case_index_rebuild,
    case_list_indexed,
]
