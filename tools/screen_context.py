"""
Screen-context tools for the orchestrator.

Goal: let any agent see what the user is *actually* working on without the user
having to copy-paste it. Three pillars:

1. Clipboard — read what the user just copied (a stack trace, a Resource ID,
   a SQL query, a customer email).
2. Active window — the title of the foreground window (often contains a case
   number, a file path, or a customer name).
3. Active case — a sticky pointer to a case folder under
   `Work_cases\\Cases\\YYYY-MM-DD_SR_xxxxxxx\\`. Auto-detected from the active
   window title; persisted to `memory/active_case.json`; used to scope RAG
   searches and CLI commands.

Design rules:
- Stdlib only. No new pip packages.
- Windows-only at runtime. On non-Windows we degrade gracefully and return
  a clean explanatory string instead of raising — agents stay alive.
- All public functions are async, audit-logged, and never raise.
- Tool list is exposed via `SCREEN_CONTEXT_TOOLS` for orchestrator wiring.
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Annotated, Any

from pydantic import Field

from tools.audit import audit_log

logger = logging.getLogger(__name__)

# --- Constants ---------------------------------------------------------------

# Case folder convention from copilot-instructions.md:
#   Work_cases\Cases\YYYY-MM-DD_SR_xxxxxxx\
CASE_FOLDER_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}_SR_\d{7,}")

ACTIVE_CASE_FILE = Path("memory") / "active_case.json"

IS_WINDOWS = sys.platform == "win32"

# Hard cap clipboard reads so a 50 MB image-as-text paste cannot poison context.
_CLIPBOARD_MAX_CHARS = 200_000


# --- Data ---------------------------------------------------------------------


@dataclass(frozen=True)
class ActiveCase:
    """Sticky pointer to the case folder the user is currently working on."""

    case_id: str            # e.g. "2026-03-17_SR_1234567"
    folder: str             # absolute path to the case folder
    source: str             # "manual" | "active_window" | "clipboard"
    set_at: str             # ISO timestamp


# --- Internal helpers --------------------------------------------------------


def _now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _ensure_memory_dir() -> Path:
    """Make sure memory/ exists and return the active-case file path."""
    p = ACTIVE_CASE_FILE
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _platform_guard_reason() -> str | None:
    """Return a human-readable reason if the host can't run screen-context."""
    if not IS_WINDOWS:
        return (
            f"Screen-context tools are Windows-only "
            f"(detected platform: {sys.platform}). Tool returned no data."
        )
    return None


def _read_clipboard_windows() -> str:
    """
    Stdlib-only clipboard read on Windows via tkinter.

    tkinter ships with CPython on Windows, so this avoids pulling in pywin32
    or pyperclip just for one feature.
    """
    import tkinter as tk

    root = tk.Tk()
    root.withdraw()
    try:
        try:
            text = root.clipboard_get()
        except tk.TclError:
            # Empty clipboard or non-text content (e.g. an image).
            text = ""
    finally:
        try:
            root.update()
        except Exception:
            pass
        root.destroy()

    if len(text) > _CLIPBOARD_MAX_CHARS:
        text = (
            text[:_CLIPBOARD_MAX_CHARS]
            + f"\n\n... [truncated at {_CLIPBOARD_MAX_CHARS} chars] ..."
        )
    return text


def _write_clipboard_windows(text: str) -> None:
    """Stdlib-only clipboard write on Windows via tkinter."""
    import tkinter as tk

    root = tk.Tk()
    root.withdraw()
    try:
        root.clipboard_clear()
        root.clipboard_append(text)
        # `update()` is what actually flushes the X-style clipboard buffer
        # so it survives after the Tk root is destroyed.
        root.update()
    finally:
        root.destroy()


def _get_foreground_window_title_windows() -> str:
    """Active-window title on Windows via ctypes -> user32.dll."""
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32

    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return ""

    length = user32.GetWindowTextLengthW(hwnd)
    if length <= 0:
        return ""

    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    return buf.value or ""


def _cases_root() -> Path:
    """
    Resolve the Work_cases\\Cases root the same way RAG does:
    1) $env:CASES_ROOT
    2) ~/OneDrive - Microsoft/Work_cases/Cases
    3) ~/Work_cases/Cases
    """
    override = os.environ.get("CASES_ROOT", "").strip()
    if override:
        return Path(override).expanduser().resolve()

    home = Path.home()
    candidates = [
        home / "OneDrive - Microsoft" / "Work_cases" / "Cases",
        home / "Work_cases" / "Cases",
    ]
    for c in candidates:
        if c.exists():
            return c
    # Sensible default even if the folder doesn't exist yet.
    return candidates[0]


def _resolve_case_folder(case_id: str) -> Path | None:
    """
    Try to resolve `case_id` (e.g. "2026-03-17_SR_1234567") to a real folder
    under the Cases root. Returns None if the folder doesn't exist.
    """
    if not case_id:
        return None
    root = _cases_root()
    candidate = root / case_id
    if candidate.exists() and candidate.is_dir():
        return candidate.resolve()
    return None


def _scan_text_for_case_id(text: str) -> str | None:
    """Find the first case-id in a string, or None."""
    if not text:
        return None
    m = CASE_FOLDER_PATTERN.search(text)
    return m.group(0) if m else None


def _save_active_case(case: ActiveCase) -> None:
    p = _ensure_memory_dir()
    p.write_text(json.dumps(asdict(case), indent=2), encoding="utf-8")


def _load_active_case() -> ActiveCase | None:
    p = ACTIVE_CASE_FILE
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return ActiveCase(**data)
    except Exception as e:
        logger.warning(f"Could not load active_case.json: {e}")
        return None


def _format_active_case(case: ActiveCase | None, prefix: str = "") -> str:
    if case is None:
        return f"{prefix}No active case is set."
    return (
        f"{prefix}Active case: {case.case_id}\n"
        f"  Folder:   {case.folder}\n"
        f"  Source:   {case.source}\n"
        f"  Set at:   {case.set_at}"
    )


# --- Tools (async, audit-logged, never raise) --------------------------------


async def read_clipboard() -> str:
    """
    Read the user's current clipboard contents (text only).

    Use this when the user pastes-by-reference ("look at what I just copied"),
    when an error mentions an artifact you don't have, or when the user says
    "use this" without supplying inline text. Truncated to 200,000 chars.
    """
    audit_id = audit_log("ScreenContext.read_clipboard", "started", {})
    guard = _platform_guard_reason()
    if guard:
        audit_log(
            "ScreenContext.read_clipboard",
            "skipped",
            {"reason": "non-windows"},
            parent_id=audit_id,
        )
        return guard
    try:
        text = _read_clipboard_windows()
        n = len(text)
        audit_log(
            "ScreenContext.read_clipboard",
            "completed",
            {"chars": n},
            parent_id=audit_id,
        )
        if not text:
            return "Clipboard is empty (or contains non-text content)."
        return text
    except Exception as e:
        audit_log(
            "ScreenContext.read_clipboard",
            "error",
            {"error": str(e)},
            parent_id=audit_id,
        )
        return f"Could not read clipboard: {e}"


async def paste_to_clipboard(
    text: Annotated[
        str,
        Field(description="Text to place on the user's clipboard."),
    ],
) -> str:
    """
    Replace the user's clipboard contents with the supplied text.

    Use sparingly — the user did not consent to losing whatever was already
    on their clipboard. Good for "copy this command for me" or
    "I prepared the email body — paste it for the user."
    """
    audit_id = audit_log(
        "ScreenContext.paste_to_clipboard",
        "started",
        {"chars": len(text or "")},
    )
    guard = _platform_guard_reason()
    if guard:
        audit_log(
            "ScreenContext.paste_to_clipboard",
            "skipped",
            {"reason": "non-windows"},
            parent_id=audit_id,
        )
        return guard
    if text is None:
        return "Refused to clear clipboard: no text supplied."
    try:
        _write_clipboard_windows(text)
        audit_log(
            "ScreenContext.paste_to_clipboard",
            "completed",
            {"chars": len(text)},
            parent_id=audit_id,
        )
        return f"Copied {len(text)} chars to the clipboard."
    except Exception as e:
        audit_log(
            "ScreenContext.paste_to_clipboard",
            "error",
            {"error": str(e)},
            parent_id=audit_id,
        )
        return f"Could not write to clipboard: {e}"


async def get_active_window_title() -> str:
    """
    Return the title of the foreground (active) window on Windows.

    Useful as a "what is the user looking at right now" signal — many apps
    embed file paths, customer names, ticket numbers, or case folder names
    in their window title.
    """
    audit_id = audit_log("ScreenContext.active_window_title", "started", {})
    guard = _platform_guard_reason()
    if guard:
        audit_log(
            "ScreenContext.active_window_title",
            "skipped",
            {"reason": "non-windows"},
            parent_id=audit_id,
        )
        return guard
    try:
        title = _get_foreground_window_title_windows()
        audit_log(
            "ScreenContext.active_window_title",
            "completed",
            {"chars": len(title)},
            parent_id=audit_id,
        )
        return title or "(active window has no title)"
    except Exception as e:
        audit_log(
            "ScreenContext.active_window_title",
            "error",
            {"error": str(e)},
            parent_id=audit_id,
        )
        return f"Could not read active window title: {e}"


async def detect_active_case() -> str:
    """
    Try to auto-detect the user's current case folder by scanning the active
    window title and the clipboard for a `YYYY-MM-DD_SR_xxxxxxx` token.

    On hit, persists the detection to `memory/active_case.json` and returns
    a human-readable summary. On miss, returns a clear explanation and does
    not change the saved active case.
    """
    audit_id = audit_log("ScreenContext.detect_active_case", "started", {})
    guard = _platform_guard_reason()
    if guard:
        audit_log(
            "ScreenContext.detect_active_case",
            "skipped",
            {"reason": "non-windows"},
            parent_id=audit_id,
        )
        return guard

    # Look at active window first (lower invasiveness than reading clipboard).
    case_id: str | None = None
    source: str = ""

    try:
        title = _get_foreground_window_title_windows()
    except Exception as e:
        title = ""
        logger.debug(f"active-window read failed during detect: {e}")
    case_id = _scan_text_for_case_id(title)
    if case_id:
        source = "active_window"

    if not case_id:
        try:
            clip = _read_clipboard_windows()
        except Exception as e:
            clip = ""
            logger.debug(f"clipboard read failed during detect: {e}")
        case_id = _scan_text_for_case_id(clip)
        if case_id:
            source = "clipboard"

    if not case_id:
        audit_log(
            "ScreenContext.detect_active_case",
            "completed",
            {"hit": False},
            parent_id=audit_id,
        )
        existing = _load_active_case()
        if existing:
            return (
                "No case-id token found in active window or clipboard. "
                "Existing active case kept.\n\n"
                + _format_active_case(existing)
            )
        return (
            "No case-id token found in active window or clipboard. "
            "Tip: case folders look like '2026-03-17_SR_1234567'."
        )

    folder = _resolve_case_folder(case_id)
    if folder is None:
        audit_log(
            "ScreenContext.detect_active_case",
            "completed",
            {"hit": True, "case_id": case_id, "folder_exists": False},
            parent_id=audit_id,
        )
        return (
            f"Detected case-id '{case_id}' in {source}, but no folder by that "
            f"name exists under the Cases root ({_cases_root()}). "
            f"Active case not changed."
        )

    case = ActiveCase(
        case_id=case_id,
        folder=str(folder),
        source=source,
        set_at=_now_iso(),
    )
    try:
        _save_active_case(case)
        audit_log(
            "ScreenContext.detect_active_case",
            "completed",
            {
                "hit": True,
                "case_id": case_id,
                "folder": str(folder),
                "source": source,
            },
            parent_id=audit_id,
        )
        return _format_active_case(case, prefix="Detected and saved.\n")
    except Exception as e:
        audit_log(
            "ScreenContext.detect_active_case",
            "error",
            {"error": str(e)},
            parent_id=audit_id,
        )
        return (
            f"Detected case-id '{case_id}' but could not persist it: {e}\n"
            f"Folder: {folder}"
        )


async def set_active_case(
    case_id_or_folder: Annotated[
        str,
        Field(
            description=(
                "Either a case-id like '2026-03-17_SR_1234567' or a full path "
                "to the case folder."
            )
        ),
    ],
) -> str:
    """
    Manually set the active case. Accepts a case-id under the Cases root, or
    a full folder path containing a case-id token in its name.

    Persists the choice to `memory/active_case.json` so it survives restarts.
    """
    audit_id = audit_log(
        "ScreenContext.set_active_case",
        "started",
        {"input": case_id_or_folder[:200] if case_id_or_folder else ""},
    )
    if not case_id_or_folder or not case_id_or_folder.strip():
        audit_log(
            "ScreenContext.set_active_case",
            "error",
            {"error": "empty input"},
            parent_id=audit_id,
        )
        return "Usage: set_active_case '<case-id>' OR '<full-folder-path>'."

    raw = case_id_or_folder.strip().strip('"').strip("'")

    # Path mode: a real existing directory wins, even on non-Windows.
    p = Path(raw).expanduser()
    folder: Path | None = None
    case_id: str | None = None

    if p.exists() and p.is_dir():
        folder = p.resolve()
        case_id = _scan_text_for_case_id(folder.name) or folder.name
    else:
        # Bare case-id mode.
        token = _scan_text_for_case_id(raw) or raw
        case_id = token
        folder = _resolve_case_folder(token)

    if folder is None or case_id is None:
        audit_log(
            "ScreenContext.set_active_case",
            "completed",
            {"set": False, "reason": "no folder resolved"},
            parent_id=audit_id,
        )
        return (
            f"Could not resolve '{raw}' to an existing case folder. "
            f"Looked under: {_cases_root()}"
        )

    case = ActiveCase(
        case_id=case_id,
        folder=str(folder),
        source="manual",
        set_at=_now_iso(),
    )
    try:
        _save_active_case(case)
        audit_log(
            "ScreenContext.set_active_case",
            "completed",
            {"set": True, "case_id": case_id, "folder": str(folder)},
            parent_id=audit_id,
        )
        return _format_active_case(case, prefix="Set.\n")
    except Exception as e:
        audit_log(
            "ScreenContext.set_active_case",
            "error",
            {"error": str(e)},
            parent_id=audit_id,
        )
        return f"Could not save active case: {e}"


async def get_active_case() -> str:
    """
    Show the currently-saved active case (case-id + folder + when it was set).

    Use this at the start of any case-scoped task to check that you're
    operating on the right case.
    """
    audit_id = audit_log("ScreenContext.get_active_case", "started", {})
    case = _load_active_case()
    audit_log(
        "ScreenContext.get_active_case",
        "completed",
        {"set": case is not None, "case_id": case.case_id if case else ""},
        parent_id=audit_id,
    )
    return _format_active_case(case)


async def clear_active_case() -> str:
    """Clear the saved active case (delete `memory/active_case.json`)."""
    audit_id = audit_log("ScreenContext.clear_active_case", "started", {})
    p = ACTIVE_CASE_FILE
    if not p.exists():
        audit_log(
            "ScreenContext.clear_active_case",
            "completed",
            {"cleared": False},
            parent_id=audit_id,
        )
        return "No active case was set."
    try:
        p.unlink()
        audit_log(
            "ScreenContext.clear_active_case",
            "completed",
            {"cleared": True},
            parent_id=audit_id,
        )
        return "Active case cleared."
    except Exception as e:
        audit_log(
            "ScreenContext.clear_active_case",
            "error",
            {"error": str(e)},
            parent_id=audit_id,
        )
        return f"Could not clear active case: {e}"


# --- Public exports for orchestrator wiring ----------------------------------

SCREEN_CONTEXT_TOOLS: list[Any] = [
    read_clipboard,
    paste_to_clipboard,
    get_active_window_title,
    detect_active_case,
    set_active_case,
    get_active_case,
    clear_active_case,
]


__all__ = [
    "SCREEN_CONTEXT_TOOLS",
    "ActiveCase",
    "read_clipboard",
    "paste_to_clipboard",
    "get_active_window_title",
    "detect_active_case",
    "set_active_case",
    "get_active_case",
    "clear_active_case",
]
