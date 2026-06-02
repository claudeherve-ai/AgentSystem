"""
AgentSystem — Azure AI Search vector backend (PR4, OPTIONAL / ADDITIVE)

A thin, fully-optional adapter that lets case memory (:mod:`tools.rag_store`) fan
out a semantic query to an **Azure AI Search** index in addition to the local
SQLite FTS5 + embedding store. It is a Microsoft/Azure-native alternative to
running a separate vector database.

Design contract (deliberately conservative):
  * The ``azure-search-documents`` SDK is imported behind a guarded ``try`` — if
    it is not installed the module still imports cleanly and simply reports
    "disabled". The dependency is COMMENTED/optional in ``requirements.txt``.
  * Enabled only when BOTH the SDK is importable AND
    :func:`config.get_azure_search_config` reports configured (real endpoint +
    key, not a ``<placeholder>``).
  * :func:`azure_semantic_search` returns ``list[dict]`` on success or ``None``
    on ANY failure (disabled, network error, bad index …). It NEVER raises and
    NEVER blocks the local search path. A failure is logged once per process.
  * This module imports NOTHING from :mod:`tools.rag_store` (avoids a circular
    import). It returns plain dicts; ``rag_store`` maps them onto its own
    ``SearchHit`` dataclass.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ── Guarded SDK import ───────────────────────────────────────────────────────
try:  # pragma: no cover - exercised only when the optional SDK is installed
    from azure.core.credentials import AzureKeyCredential
    from azure.search.documents.aio import SearchClient
    from azure.search.documents.models import VectorizedQuery

    _SDK_AVAILABLE = True
except Exception:  # noqa: BLE001 - any import problem => feature simply off
    AzureKeyCredential = None  # type: ignore[assignment]
    SearchClient = None  # type: ignore[assignment]
    VectorizedQuery = None  # type: ignore[assignment]
    _SDK_AVAILABLE = False

# Log a disabled-because-of-failure warning at most once per process.
_WARNED = False

# Field names expected in the Azure AI Search index. Kept here (not in the index)
# so the mapping is explicit and easy to adapt to an existing schema.
_VECTOR_FIELD = "content_vector"
_CONTENT_FIELD = "content"
_CASE_FIELD = "case_folder"
_PATH_FIELD = "file_path"
_CHUNK_FIELD = "chunk_index"


def sdk_available() -> bool:
    """True if the optional ``azure-search-documents`` SDK is importable."""
    return _SDK_AVAILABLE


def azure_search_enabled() -> bool:
    """True only when the SDK is present AND the service is configured."""
    if not _SDK_AVAILABLE:
        return False
    try:
        from config import get_azure_search_config

        return bool(get_azure_search_config().enabled)
    except Exception as exc:  # noqa: BLE001 - config issues => disabled
        logger.debug("azure_search_enabled: config load failed (%s)", exc)
        return False


def azure_search_status() -> dict[str, Any]:
    """Diagnostic snapshot for ``/api/v1/models``-style status surfaces."""
    status: dict[str, Any] = {
        "sdk_available": _SDK_AVAILABLE,
        "enabled": False,
        "index_name": None,
        "endpoint_configured": False,
    }
    try:
        from config import get_azure_search_config

        cfg = get_azure_search_config()
        status["enabled"] = bool(cfg.enabled and _SDK_AVAILABLE)
        status["index_name"] = cfg.index_name
        status["endpoint_configured"] = bool(cfg.endpoint)
    except Exception as exc:  # noqa: BLE001
        logger.debug("azure_search_status: config load failed (%s)", exc)
    return status


def _warn_once(msg: str, *args: Any) -> None:
    global _WARNED
    if not _WARNED:
        logger.warning(msg, *args)
        _WARNED = True


async def azure_semantic_search(
    query: str,
    query_vector: Optional[list[float]] = None,
    top_k: int = 5,
    case_folder: Optional[str] = None,
) -> Optional[list[dict[str, Any]]]:
    """Run a vector (and optional text) search against Azure AI Search.

    Returns a list of plain dicts shaped like::

        {"case_folder", "file_path", "chunk_index", "snippet", "score"}

    or ``None`` if the feature is disabled or anything goes wrong. Never raises.
    A non-empty ``query_vector`` enables the vector leg; without it we fall back
    to a plain text query so the caller still gets useful hits.
    """
    if not azure_search_enabled():
        return None
    if not query or not query.strip():
        return None

    try:
        top_k = max(1, min(50, int(top_k or 5)))
    except (TypeError, ValueError):
        top_k = 5

    try:
        from config import get_azure_search_config

        cfg = get_azure_search_config()
        credential = AzureKeyCredential(cfg.api_key)
        client = SearchClient(
            endpoint=cfg.endpoint,
            index_name=cfg.index_name,
            credential=credential,
        )
    except Exception as exc:  # noqa: BLE001
        _warn_once("Azure AI Search client init failed (%s) — using local store.", exc)
        return None

    # Optional server-side filter to a single case folder.
    odata_filter = None
    if case_folder:
        safe = str(case_folder).replace("'", "''")
        odata_filter = f"{_CASE_FIELD} eq '{safe}'"

    vector_queries = None
    if query_vector:
        try:
            vector_queries = [
                VectorizedQuery(
                    vector=[float(x) for x in query_vector],
                    k_nearest_neighbors=top_k,
                    fields=_VECTOR_FIELD,
                )
            ]
        except Exception as exc:  # noqa: BLE001
            logger.debug("Azure AI Search vector query build failed (%s)", exc)
            vector_queries = None

    try:
        results: list[dict[str, Any]] = []
        async with client:
            response = await client.search(
                search_text=query,
                vector_queries=vector_queries,
                filter=odata_filter,
                top=top_k,
            )
            async for doc in response:
                results.append(_map_doc(doc))
        return results
    except Exception as exc:  # noqa: BLE001
        _warn_once("Azure AI Search query failed (%s) — using local store.", exc)
        return None


def _map_doc(doc: Any) -> dict[str, Any]:
    """Map one Azure AI Search result document to the rag_store shape."""
    def _get(field: str, default: Any = "") -> Any:
        try:
            return doc.get(field, default)
        except Exception:  # noqa: BLE001 - some SDK rows are attr-only
            return getattr(doc, field, default)

    score = _get("@search.score", 0.0)
    try:
        chunk_index = int(_get(_CHUNK_FIELD, 0) or 0)
    except (TypeError, ValueError):
        chunk_index = 0
    return {
        "case_folder": str(_get(_CASE_FIELD, "") or ""),
        "file_path": str(_get(_PATH_FIELD, "") or ""),
        "chunk_index": chunk_index,
        "snippet": str(_get(_CONTENT_FIELD, "") or "")[:1000],
        "score": float(score or 0.0),
    }
