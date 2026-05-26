"""
Web search tool — multi-backend for reliability.

Primary:    ddgs (DuckDuckGo via ddgs library, handles rate-limiting/IP rotation)
Fallback:   DuckDuckGo HTML scraping (current approach, works on non-blocked IPs)
Optional:   Bing Web Search API (if BING_SEARCH_API_KEY env var is set)

Any specialist agent or the orchestrator can call this to get current information.
Falls back gracefully through backends; never raises out of the tool.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Annotated
from urllib.parse import quote_plus, unquote, urlparse, parse_qs

import httpx
from pydantic import Field

from .audit import audit_log

logger = logging.getLogger(__name__)

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
_DUCKDUCKGO_HTML = "https://html.duckduckgo.com/html/"
_BING_API = "https://api.bing.microsoft.com/v7.0/search"

_LINK_RE = re.compile(
    r'<a[^>]+class="[^"]*result__a[^"]*"[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
    re.IGNORECASE | re.DOTALL,
)
_SNIPPET_RE = re.compile(
    r'<a[^>]+class="[^"]*result__snippet[^"]*"[^>]*>(.*?)</a>',
    re.IGNORECASE | re.DOTALL,
)
_TAG_RE = re.compile(r"<[^>]+>")


def _clean_text(html: str) -> str:
    text = _TAG_RE.sub("", html)
    text = text.replace("&amp;", "&").replace("&quot;", '"')
    text = text.replace("&lt;", "<").replace("&gt;", ">").replace("&#x27;", "'")
    return re.sub(r"\s+", " ", text).strip()


def _resolve_redirect(href: str) -> str:
    """DuckDuckGo HTML wraps results in a /l/?uddg=<encoded> redirect — unwrap it."""
    if href.startswith("//"):
        href = "https:" + href
    parsed = urlparse(href)
    if parsed.netloc.endswith("duckduckgo.com") and parsed.path.startswith("/l/"):
        qs = parse_qs(parsed.query)
        target = qs.get("uddg", [""])[0]
        if target:
            return unquote(target)
    return href


# ── Backend 1: ddgs library ────────────────────────────────────────────────

async def _search_ddgs(query: str, max_results: int) -> list[dict]:
    """Search using the ddgs library (DuckDuckGo, more robust)."""
    try:
        from ddgs import DDGS
    except ImportError:
        logger.debug("ddgs library not installed, skipping ddgs backend")
        return []

    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        return [
            {"title": r.get("title", ""), "url": r.get("href", ""), "snippet": r.get("body", "")}
            for r in results
        ]
    except Exception as exc:
        logger.warning("ddgs search failed: %s", exc)
        return []


# ── Backend 2: DuckDuckGo HTML scraping ────────────────────────────────────

async def _search_ddg_html(query: str, max_results: int = 10) -> list[dict]:
    """Search using DuckDuckGo HTML scraping (original approach)."""
    try:
        async with httpx.AsyncClient(
            timeout=15.0,
            headers={"User-Agent": _USER_AGENT, "Accept-Language": "en-US,en;q=0.9"},
            follow_redirects=True,
        ) as client:
            resp = await client.post(
                _DUCKDUCKGO_HTML,
                data={"q": query, "kl": "us-en"},
            )
            resp.raise_for_status()
            html = resp.text

        links = _LINK_RE.findall(html)
        snippets = _SNIPPET_RE.findall(html)

        results = []
        for i, (href, title_html) in enumerate(links):
            if i >= max_results:
                break
            url = _resolve_redirect(href)
            title = _clean_text(title_html) or url
            snippet = ""
            if i < len(snippets):
                snippet = _clean_text(snippets[i])
            results.append({"title": title, "url": url, "snippet": snippet})
        return results
    except Exception as exc:
        logger.warning("DDG HTML search failed: %s", exc)
        return []


# ── Backend 3: Bing Web Search API (optional) ──────────────────────────────

async def _search_bing(query: str, max_results: int) -> list[dict]:
    """Search using Bing Web Search API (requires BING_SEARCH_API_KEY env var)."""
    api_key = os.environ.get("BING_SEARCH_API_KEY", "").strip()
    if not api_key:
        return []

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                _BING_API,
                params={"q": query, "count": max_results, "mkt": "en-US"},
                headers={"Ocp-Apim-Subscription-Key": api_key},
            )
            resp.raise_for_status()
            data = resp.json()

        results = []
        for page in data.get("webPages", {}).get("value", [])[:max_results]:
            results.append({
                "title": page.get("name", ""),
                "url": page.get("url", ""),
                "snippet": page.get("snippet", ""),
            })
        return results
    except Exception as exc:
        logger.warning("Bing search failed: %s", exc)
        return []


# ── Main search function ───────────────────────────────────────────────────

async def web_search(
    query: Annotated[str, Field(description="The search query")],
    max_results: Annotated[int, Field(description="Maximum number of results to return (1-10)")] = 5,
) -> str:
    """
    Search the public web and return a Markdown list of results.

    Tries multiple backends in order:
      1. ddgs library (DuckDuckGo, handles rate-limiting)
      2. DuckDuckGo HTML scraping (original approach)
      3. Bing Web Search API (if BING_SEARCH_API_KEY env var is set)

    Returns up to `max_results` items; each item has a title, URL, and a short
    snippet. If all backends fail, returns a clear error string instead of raising.
    """
    audit_id = audit_log("WebSearch.search", "started", {"query": query, "max_results": max_results})
    max_results = max(1, min(10, int(max_results or 5)))
    backends_tried = []

    # Try backends in order
    for backend_name, backend_fn in [
        ("ddgs", _search_ddgs),
        ("ddg_html", _search_ddg_html),
        ("bing", _search_bing),
    ]:
        try:
            results = await backend_fn(query, max_results)
            if results:
                backends_tried.append(backend_name)
                break
            backends_tried.append(f"{backend_name}(empty)")
        except Exception as exc:
            logger.warning("%s backend raised: %s", backend_name, exc)
            backends_tried.append(f"{backend_name}(error)")

    if not results:
        audit_log(
            "WebSearch.search", "no_results",
            {"query": query, "backends": backends_tried},
            parent_id=audit_id,
        )
        return (
            f"No web results for: {query!r}. "
            f"Tried: {', '.join(backends_tried)}. "
            "Try a different query or check connectivity."
        )

    # Format results as Markdown
    lines = [f"# Web search results: {query}"]
    for i, r in enumerate(results[:max_results], start=1):
        lines.append(f"\n**{i}. {r['title']}**")
        lines.append(f"<{r['url']}>")
        if r["snippet"]:
            lines.append(r["snippet"][:500])

    result = "\n".join(lines)
    audit_log(
        "WebSearch.search",
        "completed",
        {"query": query, "result_count": len(results[:max_results]), "backend": backends_tried[0]},
        parent_id=audit_id,
    )
    return result


WEB_SEARCH_TOOLS = [web_search]
