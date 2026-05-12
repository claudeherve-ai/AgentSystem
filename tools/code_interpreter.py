"""
Code interpreter tool — sandboxed Python execution with timeout and capture.

Executes user/agent-provided Python code in a *separate* subprocess using the
current venv's Python interpreter. Captures stdout, stderr, return code; kills
the process on timeout.

This is a lightweight sandbox — it is NOT a security boundary. Treat it like
a developer terminal: useful for analysis, calculation, debugging, validating
queries, generating quick visualizations as text. Do NOT run untrusted code
from the public internet through it.
"""

from __future__ import annotations

import asyncio
import logging
import os
import shlex
import sys
import tempfile
from pathlib import Path
from typing import Annotated

from pydantic import Field

from .audit import audit_log

logger = logging.getLogger(__name__)

WORKSPACE_DIR = Path(__file__).resolve().parent.parent / "memory" / "workspace"
WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)

_DENYLIST_SHELL_TOKENS = {
    "rm", "del", "format", "shutdown", "reboot", "mkfs", "dd",
    "diskpart", "Stop-Computer", "Restart-Computer", "Remove-Item",
    "shred", "fdisk", "halt", "poweroff",
}
_MAX_OUTPUT = 32_000


def _truncate(text: str) -> str:
    if len(text) > _MAX_OUTPUT:
        return text[:_MAX_OUTPUT] + f"\n[…truncated, {len(text) - _MAX_OUTPUT} more chars]"
    return text


async def run_python(
    code: Annotated[str, Field(description="Python source to execute")],
    timeout: Annotated[int, Field(description="Seconds before the run is killed (1-120)")] = 30,
) -> str:
    """
    Execute a snippet of Python in the venv interpreter and return stdout/stderr.

    Returns a Markdown report with separate STDOUT / STDERR / EXIT sections.
    The script's working directory is `memory/workspace/` so it can write files
    that persist across calls (great for plots, csv exports, etc.).
    """
    audit_id = audit_log("CodeInterpreter.run_python", "started", {"chars": len(code), "timeout": timeout})
    timeout = max(1, min(120, int(timeout or 30)))

    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".py",
        delete=False,
        dir=str(WORKSPACE_DIR),
        encoding="utf-8",
    ) as fh:
        fh.write(code)
        script_path = Path(fh.name)

    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable,
            str(script_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(WORKSPACE_DIR),
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            audit_log("CodeInterpreter.run_python", "timeout", {"timeout": timeout}, parent_id=audit_id)
            return f"# Code execution\n\n**TIMEOUT** after {timeout}s. Process killed."
        rc = proc.returncode
        out = stdout.decode("utf-8", errors="replace")
        err = stderr.decode("utf-8", errors="replace")
        audit_log(
            "CodeInterpreter.run_python",
            "completed",
            {"return_code": rc, "stdout_chars": len(out), "stderr_chars": len(err)},
            parent_id=audit_id,
        )
        return (
            f"# Code execution (exit code: {rc})\n\n"
            f"## STDOUT\n```\n{_truncate(out) or '(empty)'}\n```\n\n"
            f"## STDERR\n```\n{_truncate(err) or '(empty)'}\n```"
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("run_python failed")
        audit_log("CodeInterpreter.run_python", "error", {"error": str(exc)}, parent_id=audit_id)
        return f"Code execution failed: {exc!s}"
    finally:
        try:
            script_path.unlink(missing_ok=True)
        except Exception:  # noqa: BLE001
            pass


async def run_shell(
    command: Annotated[str, Field(description="Shell command to run (read-only / inspection only)")],
    timeout: Annotated[int, Field(description="Seconds before the run is killed (1-60)")] = 30,
) -> str:
    """
    Run a non-destructive shell command for inspection (e.g. dir, where, ipconfig).

    Destructive tokens (rm, del, shutdown, format, Remove-Item, etc.) are blocked.
    Output is captured and truncated.
    """
    audit_id = audit_log("CodeInterpreter.run_shell", "started", {"command": command[:200]})
    timeout = max(1, min(60, int(timeout or 30)))
    try:
        tokens = shlex.split(command, posix=False)
    except ValueError:
        tokens = command.split()
    for tok in tokens:
        if tok in _DENYLIST_SHELL_TOKENS:
            audit_log("CodeInterpreter.run_shell", "denied", {"token": tok}, parent_id=audit_id)
            return f"Refused: command contains destructive token {tok!r}."

    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(WORKSPACE_DIR),
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return f"# Shell\n\n**TIMEOUT** after {timeout}s."
        rc = proc.returncode
        audit_log(
            "CodeInterpreter.run_shell",
            "completed",
            {"return_code": rc},
            parent_id=audit_id,
        )
        return (
            f"# Shell (exit code: {rc})\n\n"
            f"## STDOUT\n```\n{_truncate(stdout.decode('utf-8', errors='replace')) or '(empty)'}\n```\n\n"
            f"## STDERR\n```\n{_truncate(stderr.decode('utf-8', errors='replace')) or '(empty)'}\n```"
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("run_shell failed")
        audit_log("CodeInterpreter.run_shell", "error", {"error": str(exc)}, parent_id=audit_id)
        return f"Shell execution failed: {exc!s}"


CODE_INTERPRETER_TOOLS = [run_python, run_shell]
