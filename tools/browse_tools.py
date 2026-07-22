"""
Browser tools — powered by browse.sh CLI over local Chromium CDP.

Adds JS-rendered page extraction, interactive browsing, and element
snapshot capabilities to the AgentSystem. Falls back to the existing
web_fetch/web_search tools when the browser is unavailable.

REQUIRES: Chromium installed (via npx playwright install chromium)
OPTIONAL: Set BROWSERBASE_API_KEY for cloud-powered search + stealth

Browser lifecycle:
  - Start: first tool call spawns Chromium headless + CDP on port 9222
  - Idle: stays running for 10 minutes after last call
  - Stop: killed when AgentSystem shuts down or timeout expires
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import signal
import subprocess
import sys
import textwrap
import time
from pathlib import Path
from typing import Annotated, Optional

from pydantic import Field

from .audit import audit_log

logger = logging.getLogger(__name__)

# ── Browse CLI path — try multiple locations since Path.home() differs ──
# between Windows-process-launched (C:\Users\tedch\) and WSL-native (/home/tedch/)

def _resolve_browse_bin() -> Optional[str]:
    """Find the browse CLI binary, trying every known location.

    Path.home() / ~ can resolve to C:\\Users\\tedch when the Python process
    is started from Windows, even inside WSL. We try both WSL and Windows
    paths explicitly.
    """
    candidates = [
        shutil.which("browse"),                                    # PATH lookup
        "/home/tedch/.npm-global/bin/browse",                      # WSL Linux home
        "/usr/local/bin/browse",                                   # system install
    ]
    # Also try the WSL home resolved via /mnt/c/Users mapping
    wsl_home = os.environ.get("HOME", "")
    if wsl_home:
        candidates.append(os.path.join(wsl_home, ".npm-global/bin/browse"))

    for c in candidates:
        if c and os.path.isfile(c):
            return c
    return None

_BROWSE_BIN = _resolve_browse_bin() or "/home/tedch/.npm-global/bin/browse"


def _find_chromium() -> Optional[Path]:
    """Find a usable Chromium binary. Checks in order:
    1. CHROME_PATH env var (Docker container)
    2. Playwright cache — both WSL Linux (/home/) and Windows-home paths
    3. Standard system paths
    """
    # 1. Explicit env override
    env_path = os.environ.get("CHROME_PATH") or os.environ.get("CHROMIUM_PATH")
    if env_path:
        p = Path(env_path)
        if p.exists():
            return p

    # 2. Playwright cache — try multiple home directories because
    #    Path.home() returns C:\Users\tedch when called from a Windows-started
    #    Python process, but the actual cache lives at /home/tedch/.cache/
    home_candidates = [
        Path("/home/tedch"),                     # WSL Linux home (hardcoded)
        Path(os.environ.get("HOME", "/home/tedch")),  # From $HOME env
        Path.home(),                             # Python's home (may be Windows path)
    ]

    playwright_patterns = [
        ".cache/ms-playwright/chromium_headless_shell-*/chrome-headless-shell-linux64/chrome-headless-shell",
        ".cache/ms-playwright/chromium-*/chrome-linux*/chrome",
    ]

    for home in home_candidates:
        try:
            for pattern in playwright_patterns:
                candidates = sorted(
                    home.glob(pattern),
                    reverse=True,
                )
                if candidates:
                    logger.info("Found Chromium via home=%s: %s", home, candidates[0])
                    return candidates[0]
        except Exception:
            continue

    # 3. Standard system paths
    for name in ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable"):
        p = shutil.which(name)
        if p:
            return Path(p)

    return None


_CDP_PORT = 9222
_CDP_URL = f"http://127.0.0.1:{_CDP_PORT}"
_IDLE_TIMEOUT = 600  # 10 minutes

# ── Global browser state ─────────────────────────────────────────────────
_browser_proc: Optional[subprocess.Popen] = None
_last_used: float = 0.0
_cleanup_task: Optional[asyncio.Task] = None
_lock = asyncio.Lock()  # prevent concurrent browser operations


def _get_chromium() -> Optional[Path]:
    """Dynamic Chromium lookup — re-checks on every call.

    Not using a module-level cache because Chromium may have been installed
    AFTER the AgentSystem process started, making the cached value stale.
    """
    return _find_chromium()


def _cmd(*args: str, timeout: int = 15) -> subprocess.CompletedProcess:
    """Run a browse CLI subcommand and return the completed process."""
    return subprocess.run(
        [_BROWSE_BIN, *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        env={
            **os.environ,
            "PATH": os.environ.get("PATH", ""),
            "NO_UPDATE_NOTIFIER": "1",  # suppress "Update available: X.Y.Z" messages
        },
    )


async def _ensure_browser() -> bool:
    """Start the Chromium CDP browser if not already running. Returns True if ready."""
    global _browser_proc, _last_used, _cleanup_task

    _last_used = time.time()

    # Already running?
    if _browser_proc is not None and _browser_proc.poll() is None:
        return True

    # Try to connect to an existing CDP instance
    session_was_external = False
    try:
        proc = await asyncio.create_subprocess_exec(
            "curl", "-s", "-f", f"{_CDP_URL}/json/version",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.communicate()
        if proc.returncode == 0:
            _browser_proc = None  # managed externally, but usable
            _last_used = time.time()
            session_was_external = True
            return True
    except Exception:
        pass

    # Clean up stale browse CLI sessions from a previous (now-dead) CDP instance.
    # When Chromium restarts on the same port, browse CLI sessions that were
    # attached to the old CDP instance become invalid and block new sessions.
    if not session_was_external:
        for session_name in ("agent-fetch", "agent-snap", "agent-interact"):
            try:
                proc = await asyncio.create_subprocess_exec(
                    _BROWSE_BIN, "stop", "--session", session_name,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                await asyncio.wait_for(proc.communicate(), timeout=5)
            except Exception:
                pass

    # Start Chromium
    chromium = _get_chromium()
    if chromium is None or not chromium.exists():
        logger.error(
            "Chromium not found. Install: apt-get install chromium (Docker) "
            "or npx playwright install chromium (local). "
            "Set CHROME_PATH env var to override."
        )
        return False

    logger.info("Launching Chromium CDP on port %d", _CDP_PORT)
    try:
        # Data directory for persistent cookies/sessions (avoids fresh-bot detection)
        user_data_dir = os.path.join(os.environ.get("HOME", "/tmp"), ".browse_chrome_profile")
        os.makedirs(user_data_dir, exist_ok=True)

        _browser_proc = subprocess.Popen(
            [
                str(chromium),
                "--headless=new",                         # New headless mode (harder to detect)
                f"--remote-debugging-port={_CDP_PORT}",
                "--no-sandbox",
                "--disable-gpu",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",  # Hide navigator.webdriver
                f"--window-size=1920,1080",
                f"--user-data-dir={user_data_dir}",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        # Wait for CDP to become available
        for _ in range(30):
            await asyncio.sleep(0.2)
            try:
                proc = await asyncio.create_subprocess_exec(
                    "curl", "-s", "-f", f"{_CDP_URL}/json/version",
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                await proc.communicate()
                if proc.returncode == 0:
                    _last_used = time.time()
                    return True
            except Exception:
                continue

        logger.error("Chromium did not start within 6 seconds")
        return False
    except Exception as exc:
        logger.exception("Failed to launch Chromium: %s", exc)
        return False


async def _run_browse(*args: str, timeout: int = 15) -> tuple[bool, str]:
    """Run a browse CLI command. Returns (success, output_text).

    The browse CLI path is resolved at call time — not cached at import.
    """
    global _last_used
    _last_used = time.time()

    # Resolve browse binary dynamically
    browse_bin = _resolve_browse_bin()
    if not browse_bin:
        return False, "Browse CLI not found in any expected location. Install: npm install -g @browseai/browse"

    # --cdp must come AFTER the subcommand (e.g., "browse open --cdp 9222" not "browse --cdp 9222 open")
    cmd = [browse_bin, args[0], "--cdp", str(_CDP_PORT), *args[1:]]
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={**os.environ, "NO_UPDATE_NOTIFIER": "1"},
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), timeout=timeout
        )
        if proc.returncode != 0:
            err = stderr.decode(errors="replace").strip() or stdout.decode(errors="replace").strip()
            return False, err
        return True, stdout.decode(errors="replace").strip()
    except asyncio.TimeoutError:
        return False, f"Browse command timed out after {timeout}s"
    except Exception as exc:
        return False, str(exc)


async def _run_browse_json(*args: str, timeout: int = 15) -> tuple[bool, dict]:
    """Run a browse CLI command that outputs JSON."""
    ok, output = await _run_browse(*args, timeout=timeout)
    if not ok:
        return False, {"error": output}
    try:
        return True, json.loads(output)
    except json.JSONDecodeError:
        return False, {"error": f"Invalid JSON from browse: {output[:200]}"}


def _sanitize_url(url: str) -> str:
    """Ensure URL has a scheme."""
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url


# ═══════════════════════════════════════════════════════════════════════════
#  Tool 1: browse_fetch — JS-rendered page extraction
# ═══════════════════════════════════════════════════════════════════════════

async def browse_fetch(
    url: Annotated[
        str,
        Field(description="The URL to fetch and extract text from (supports JS-rendered pages)"),
    ],
    max_chars: Annotated[
        int,
        Field(description="Maximum characters of body text to return (1000-50000)"),
    ] = 12000,
) -> str:
    """
    Fetch a web page using a real browser (Chrome CDP) and return its text.

    Unlike web_fetch (which uses httpx), this renders JavaScript — essential
    for modern SPAs, Microsoft docs, Azure portals, and any JS-heavy page.

    Returns markdown-formatted content truncated to max_chars.
    """
    url = _sanitize_url(url)
    max_chars = max(1000, min(50000, int(max_chars or 12000)))

    audit_id = audit_log(
        "BrowseFetch.fetch", "started",
        {"url": url, "max_chars": max_chars},
    )

    async with _lock:
        # Ensure browser is running
        browser_ready = await _ensure_browser()
        if not browser_ready:
            audit_log(
                "BrowseFetch.fetch", "browser_unavailable",
                {"url": url}, parent_id=audit_id,
            )
            return (
                "Browser is not available. Run `npx playwright install chromium` "
                "to install Chromium, or use web_fetch instead for simple pages."
            )

        try:
            # 1. Stop any prior session to avoid conflicts
            await _run_browse("stop", "--session", "agent-fetch", timeout=5)

            # 2. Navigate to URL
            ok, result = await _run_browse_json(
                "open", "--session", "agent-fetch",
                url,
                timeout=25,
            )
            if not ok:
                error_msg = result.get("error", str(result))
                audit_log(
                    "BrowseFetch.fetch", "navigation_failed",
                    {"url": url, "error": error_msg}, parent_id=audit_id,
                )
                return f"Failed to load page: {error_msg}"

            # 3. Take a compact snapshot
            ok, snapshot = await _run_browse(
                "snapshot", "--session", "agent-fetch",
                timeout=15,
            )
            if not ok:
                audit_log(
                    "BrowseFetch.fetch", "snapshot_failed",
                    {"url": url, "error": snapshot}, parent_id=audit_id,
                )
                return f"Page loaded but couldn't extract content: {snapshot}"

            # 4. Get full page snapshot
            ok, full_snapshot = await _run_browse(
                "snapshot", "--session", "agent-fetch", "--full",
                timeout=20,
            )
            # If full snapshot fails, use compact
            content = full_snapshot if ok else snapshot

            # 5. Get page title
            ok_title, title = await _run_browse(
                "get", "--session", "agent-fetch", "title",
                timeout=5,
            )

            # 6. Parse snapshot JSON and extract text
            try:
                data = json.loads(content)
                tree_text = data.get("tree", content)
            except json.JSONDecodeError:
                tree_text = content

            # Clean up: remove accessibility refs like [0-12] and flatten
            import re
            tree_text = re.sub(r"\[\d+-\d+\]", "", tree_text)
            tree_text = re.sub(r"\n+", "\n", tree_text)

            # Build output
            page_title = title if ok_title else url
            truncated = False
            if len(tree_text) > max_chars:
                tree_text = tree_text[:max_chars]
                truncated = True

            output = f"# {page_title}\n\n{url}\n\n{tree_text}"
            if truncated:
                output += "\n\n_…truncated_"

            audit_log(
                "BrowseFetch.fetch", "completed",
                {"url": url, "chars": len(tree_text), "truncated": truncated},
                parent_id=audit_id,
            )
            return output

        except Exception as exc:
            logger.exception("browse_fetch failed")
            audit_log(
                "BrowseFetch.fetch", "error",
                {"url": url, "error": str(exc)}, parent_id=audit_id,
            )
            return f"Browse fetch failed: {exc!s}"


# ═══════════════════════════════════════════════════════════════════════════
#  Tool 2: browse_snapshot — Interactive element tree
# ═══════════════════════════════════════════════════════════════════════════

async def browse_snapshot(
    url: Annotated[
        str,
        Field(description="URL to navigate to before taking the snapshot"),
    ] = "",
    compact: Annotated[
        bool,
        Field(description="True for compact (interactive elements only), False for full page"),
    ] = True,
) -> str:
    """
    Navigate to a URL (optional) and capture the page's interactive element tree.

    Each element is identified with a ref like @e5, @e12 that can be used
    with browse_click and browse_type. This is the gateway to interactive browsing.

    Use before browse_click/browse_type to identify target elements.
    """
    audit_id = audit_log(
        "BrowseSnapshot.capture", "started",
        {"url": url, "compact": compact},
    )

    async with _lock:
        browser_ready = await _ensure_browser()
        if not browser_ready:
            audit_log(
                "BrowseSnapshot.capture", "browser_unavailable",
                {}, parent_id=audit_id,
            )
            return "Browser not available. Install Chromium first."

        try:
            # Navigate if URL provided
            if url:
                url = _sanitize_url(url)
                ok, result = await _run_browse_json(
                    "open", "--session", "agent-snap",
                    url,
                    timeout=25,
                )
                if not ok:
                    return f"Failed to load {url}: {result.get('error', result)}"

            # Take snapshot
            args = ["snapshot", "--session", "agent-snap"]
            if compact:
                args.append("--compact")

            ok, output = await _run_browse(*args, timeout=15)
            if not ok:
                audit_log(
                    "BrowseSnapshot.capture", "failed",
                    {"error": output}, parent_id=audit_id,
                )
                return f"Snapshot failed: {output}"

            audit_log(
                "BrowseSnapshot.capture", "completed",
                {"url": url, "compact": compact},
                parent_id=audit_id,
            )
            return output

        except Exception as exc:
            logger.exception("browse_snapshot failed")
            return f"Snapshot failed: {exc!s}"


# ═══════════════════════════════════════════════════════════════════════════
#  Tool 3: browse_interact — Click, type, scroll
# ═══════════════════════════════════════════════════════════════════════════

async def browse_interact(
    action: Annotated[
        str,
        Field(
            description=textwrap.dedent("""\
                Interaction to perform. One of:
                - 'click @e5' — click element ref @e5 (from snapshot)
                - 'type @e7 text' — type text into input @e7
                - 'scroll down' or 'scroll up' — scroll the page
                - 'screenshot' — capture a screenshot (returns file path)
                """),
        ),
    ],
    url: Annotated[
        str,
        Field(description="Optional: URL to navigate to before interacting"),
    ] = "",
) -> str:
    """
    Interact with the current browser page: click elements, type text, scroll, or screenshot.

    Use browse_snapshot first to get element refs (@e5, @e12, etc.),
    then call browse_interact to interact with those elements.

    Example workflow:
      1. browse_snapshot(url="https://example.com")  → get @e refs
      2. browse_interact(action="click @e5")           → click login button
      3. browse_interact(action="type @e3 username")   → fill username field
      4. browse_interact(action="click @e7")           → submit
      5. browse_interact(action="screenshot")           → verify result
    """
    audit_id = audit_log(
        "BrowseInteract.action", "started",
        {"action": action, "url": url},
    )

    async with _lock:
        browser_ready = await _ensure_browser()
        if not browser_ready:
            return "Browser not available. Install Chromium first."

        try:
            # Navigate if URL provided
            if url:
                url = _sanitize_url(url)
                ok, result = await _run_browse_json(
                    "open", "--session", "agent-interact",
                    url,
                    timeout=25,
                )
                if not ok:
                    return f"Failed to load {url}: {result.get('error', result)}"

            action_lower = action.strip().lower()

            # Parse action
            if action_lower.startswith("click "):
                ref = action_lower.split("click ", 1)[1].strip()
                ok, output = await _run_browse(
                    "click", "--session", "agent-interact", ref,
                    timeout=10,
                )

            elif action_lower.startswith("type "):
                parts = action.split(None, 2)  # ['type', '@e7', 'the text']
                if len(parts) < 3:
                    return "Usage: type <ref> <text>"
                ref = parts[1]
                text = parts[2]
                ok, output = await _run_browse(
                    "fill", "--session", "agent-interact", ref, text,
                    timeout=10,
                )

            elif action_lower in ("scroll down", "scroll up"):
                direction = "down" if "down" in action_lower else "up"
                ok, output = await _run_browse(
                    "mouse", "scroll", direction,
                    "--session", "agent-interact",
                    timeout=10,
                )

            elif action_lower == "screenshot":
                path = f"/tmp/browse_screenshot_{int(time.time())}.png"
                ok, output = await _run_browse(
                    "screenshot", "--session", "agent-interact",
                    "--path", path,
                    timeout=10,
                )
                if ok:
                    output = f"Screenshot saved to: {path}"

            elif action_lower in ("enter", "tab", "escape"):
                key = action_lower
                ok, output = await _run_browse(
                    "press", "--session", "agent-interact", key,
                    timeout=10,
                )

            else:
                return f"Unknown action: {action}. Use: click @ref, type @ref text, scroll down/up, screenshot, enter, tab, escape"

            if not ok:
                audit_log(
                    "BrowseInteract.action", "failed",
                    {"action": action, "error": output}, parent_id=audit_id,
                )
                return f"Interaction failed: {output}"

            audit_log(
                "BrowseInteract.action", "completed",
                {"action": action}, parent_id=audit_id,
            )
            return output

        except Exception as exc:
            logger.exception("browse_interact failed")
            return f"Interaction failed: {exc!s}"


# ── Cleanup ──────────────────────────────────────────────────────────────

async def browse_shutdown():
    """Clean shutdown: kill Chromium, clear sessions."""
    global _browser_proc

    # Stop known browse sessions
    for session in ("agent-fetch", "agent-snap", "agent-interact"):
        await _run_browse("stop", "--session", session, timeout=5)

    if _browser_proc and _browser_proc.poll() is None:
        _browser_proc.terminate()
        try:
            _browser_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            _browser_proc.kill()
        _browser_proc = None
        logger.info("Chromium stopped")


def _idle_cleanup_handler():
    """Called on exit to ensure browser is cleaned up."""
    if _browser_proc and _browser_proc.poll() is None:
        _browser_proc.terminate()


# Register cleanup on exit
import atexit

atexit.register(_idle_cleanup_handler)

# ── Tool list for orchestrator import ────────────────────────────────────

async def browse_health() -> str:
    """Check whether the browser (Chromium CDP) is available.

    Call this BEFORE browse_fetch if you're unsure whether the browser
    can be launched. Returns availability status and setup instructions.
    """
    # Find browse CLI
    browse_bin = _resolve_browse_bin()
    if not browse_bin:
        return (
            "Browser: UNAVAILABLE\n"
            "Reason: browse CLI not found\n"
            f"Searched: $PATH, /home/tedch/.npm-global/bin/browse, $HOME/.npm-global/bin/browse, /usr/local/bin/browse\n"
            "Fix: npm install -g @browseai/browse\n"
            "Fallback: Use web_fetch for static pages instead."
        )

    # Check if Chromium can be launched (dynamic re-check)
    chromium = _get_chromium()
    if chromium and chromium.exists():
        try:
            proc = subprocess.run(
                [str(chromium), "--version"],
                capture_output=True, text=True, timeout=5,
            )
            version = proc.stdout.strip() or "(unknown version)"
            return f"Browser: AVAILABLE\nBrowse CLI: {browse_bin}\nChromium: {version}\nPath: {chromium}"
        except Exception as e:
            return (
                f"Browser: DEGRADED\nBrowse CLI: {browse_bin}\n"
                f"Chromium found at {chromium} but could not check version: {e}\n"
                f"Try: browse_fetch may still work. If not, fall back to web_fetch."
            )
    else:
        return (
            f"Browser: UNAVAILABLE\nBrowse CLI: {browse_bin}\n"
            f"Reason: Chromium not found\n"
            f"Fix: npx playwright install chromium\n"
            f"Fallback: Use web_fetch for static pages. Most sites work fine with it."
        )


BROWSE_TOOLS = [browse_health, browse_fetch, browse_snapshot, browse_interact]
