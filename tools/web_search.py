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


# ── URL validation and filtering ────────────────────────────────────────────

# Patterns that indicate a section hub / category page, not an individual article
_HUB_URL_PATTERNS = [
    r"/hub/",
    r"/category/",
    r"/tag/",
    r"/topics/",
    r"/topic/",
    r"/section/",
]

# Broken redirect artifacts that should be discarded
_BROKEN_URL_PATTERNS = [
    r"^</",           # HTML fragment like </clev?...
    r"^javascript:",
    r"^data:",
    r"^#",
    r"StartpageResultClick",
    r"uddg=",          # Raw DuckDuckGo redirect wrapper (should be unwrapped, not kept)
]


def _is_valid_article_url(url: str) -> bool:
    """Check if a URL looks like a real article, not a hub or broken redirect."""
    if not url or not url.startswith("http"):
        return False

    for pattern in _BROKEN_URL_PATTERNS:
        if re.search(pattern, url, re.IGNORECASE):
            return False

    return True


def _is_hub_url(url: str) -> bool:
    """Check if a URL is a section hub / category / topic page."""
    for pattern in _HUB_URL_PATTERNS:
        if re.search(pattern, url, re.IGNORECASE):
            return True

    # Also check if the URL looks like a homepage/root with no article path
    parsed = urlparse(url)
    path = parsed.path.rstrip("/")
    if not path or path == "":
        return True  # bare domain root

    return False


# ── Backend 1: ddgs library ────────────────────────────────────────────────

async def _search_ddgs(query: str, max_results: int) -> tuple[list[dict], str]:
    """Search using the ddgs library. Returns (results, diagnostic)."""
    try:
        from ddgs import DDGS
    except ImportError:
        return [], "ddgs library not installed"

    try:
        with DDGS() as ddgs:
            raw = list(ddgs.text(query, max_results=max_results))
        results = [
            {"title": r.get("title", ""), "url": r.get("href", ""), "snippet": r.get("body", "")}
            for r in raw
        ]
        if not results:
            return [], "ddgs: 0 results returned (no error)"
        return results, f"ddgs: {len(results)} results OK"
    except Exception as exc:
        return [], f"ddgs error: {type(exc).__name__}: {exc}"


# ── Backend 2: DuckDuckGo HTML scraping ────────────────────────────────────

async def _search_ddg_html(query: str, max_results: int = 10) -> tuple[list[dict], str]:
    """Search using DuckDuckGo HTML scraping. Returns (results, diagnostic)."""
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

        if not results:
            return [], "ddg_html: page returned but no result links parsed"
        return results, f"ddg_html: {len(results)} results OK"
    except httpx.ConnectError as exc:
        return [], f"ddg_html connect error: {exc}"
    except httpx.TimeoutException:
        return [], "ddg_html timeout"
    except Exception as exc:
        return [], f"ddg_html error: {type(exc).__name__}: {exc}"


# ── Backend 3: Bing Web Search API (optional) ──────────────────────────────

async def _search_bing(query: str, max_results: int) -> tuple[list[dict], str]:
    """Search using Bing Web Search API. Returns (results, diagnostic)."""
    api_key = os.environ.get("BING_SEARCH_API_KEY", "").strip()
    if not api_key:
        return [], "bing: no BING_SEARCH_API_KEY set"

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

        if not results:
            return [], "bing: API responded but 0 results"
        return results, f"bing: {len(results)} results OK"
    except httpx.HTTPStatusError as exc:
        return [], f"bing HTTP {exc.response.status_code}"
    except httpx.ConnectError as exc:
        return [], f"bing connect error: {exc}"
    except Exception as exc:
        return [], f"bing error: {type(exc).__name__}: {exc}"


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
    snippet. If all backends fail, returns a detailed diagnostic error with
    per-backend reasons so the agent can diagnose the issue.
    """
    audit_id = audit_log("WebSearch.search", "started", {"query": query, "max_results": max_results})
    max_results = max(1, min(10, int(max_results or 5)))
    diagnostics = []
    results = []

    # Try backends in order, collecting diagnostics
    for backend_name, backend_fn in [
        ("ddgs", _search_ddgs),
        ("ddg_html", _search_ddg_html),
        ("bing", _search_bing),
    ]:
        try:
            res, diag = await backend_fn(query, max_results)
            diagnostics.append(diag)
            if res:
                results = res
                break
        except Exception as exc:
            diagnostics.append(f"{backend_name}: {type(exc).__name__}: {exc}")

    if not results:
        diag_str = "; ".join(diagnostics)
        audit_log(
            "WebSearch.search", "no_results",
            {"query": query, "diagnostics": diag_str},
            parent_id=audit_id,
        )
        # Provide actionable diagnosis based on error patterns
        if all("connect error" in d or "timeout" in d for d in diagnostics):
            hint = "All backends failed to connect. Check network/DNS — can this environment reach the internet?"
        elif all("not installed" in d or "no BING" in d for d in diagnostics):
            hint = "No search backend is installed or configured. Install ddgs: pip install ddgs"
        else:
            hint = "All search backends returned empty or errored. Check connectivity and API keys."
        return (
            f"No web results for: {query!r}.\n"
            f"Diagnostics: {diag_str}\n"
            f"{hint}"
        )

    # Format results as Markdown, filtering out broken URLs and deprioritizing hubs
    # Separate into articles and hubs
    articles = []
    hubs = []
    broken = []

    for r in results[:max_results * 2]:  # Fetch extra to have enough after filtering
        url = r.get("url", "")
        if not _is_valid_article_url(url):
            broken.append(r)
            continue
        if _is_hub_url(url):
            r["_hub"] = True
            hubs.append(r)
        else:
            articles.append(r)

    # Prefer articles, fall back to hubs if not enough articles
    display = articles[:max_results]
    if len(display) < max_results:
        remaining = max_results - len(display)
        display.extend(hubs[:remaining])

    if not display:
        # If everything was filtered out, return unfiltered results
        display = results[:max_results]

    lines = [f"# Web search results: {query}"]
    for i, r in enumerate(display, start=1):
        hub_label = " [section page]" if r.get("_hub") else ""
        lines.append(f"\n**{i}. {r['title']}{hub_label}**")
        lines.append(f"<{r['url']}>")
        if r["snippet"]:
            lines.append(r["snippet"][:500])

    result = "\n".join(lines)
    audit_log(
        "WebSearch.search",
        "completed",
        {"query": query, "result_count": len(results[:max_results]), "backend": diagnostics[0] if diagnostics else "unknown"},
        parent_id=audit_id,
    )
    return result


WEB_SEARCH_TOOLS = [web_search]
