"""
Code interpreter tool — Python execution with selectable isolation.

By default (``CODE_SANDBOX_MODE=auto``) code runs inside a hardened, ephemeral
Docker container (no network, read-only root filesystem, non-root user, CPU /
memory / pids capped) when Docker is available. When Docker is not available the
tool falls back to a local subprocess and emits a LOUD warning — the subprocess
path is NOT a security boundary.

Modes (env ``CODE_SANDBOX_MODE``):
    auto        Docker if available, else subprocess with a visible warning (default)
    docker      Docker only; refuse if Docker/image is unavailable
    subprocess  Legacy local subprocess (no isolation)
    off         Refuse to execute code at all

Every run is audited (``tools.audit``) and traced (``telemetry``). The returned
Markdown keeps a stable shape: a header line, then ``## STDOUT`` / ``## STDERR``
fenced sections.
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

from config import get_sandbox_config
from telemetry import get_tracer

from . import docker_sandbox
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
    Execute a snippet of Python and return stdout/stderr as a Markdown report.

    Isolation depends on ``CODE_SANDBOX_MODE`` (default ``auto``): a hardened,
    ephemeral Docker container when Docker is available, otherwise a local
    subprocess with a visible warning. In Docker mode the container is destroyed
    after each run, so files written by the snippet do NOT persist between calls.
    """
    cfg = get_sandbox_config()
    timeout = max(1, min(cfg.timeout_max, int(timeout or cfg.timeout_default)))
    audit_id = audit_log(
        "CodeInterpreter.run_python",
        "started",
        {"chars": len(code), "timeout": timeout, "mode": cfg.mode},
    )

    tracer = get_tracer()
    async with tracer.span(
        "tool.run_python",
        kind="tool",
        attributes={"sandbox.mode": cfg.mode, "code.bytes": len(code)},
    ) as span:
        engine, isolated, fallback, body = await _dispatch_run_python(
            code, timeout, cfg, audit_id
        )
        span.set_attribute("sandbox.engine", engine)
        span.set_attribute("sandbox.isolated", isolated)
        if fallback:
            span.set_attribute("sandbox.fallback", True)
        return body


async def _dispatch_run_python(code, timeout, cfg, audit_id):
    """Pick an execution engine per ``cfg.mode`` and return a Markdown report.

    Returns ``(engine, isolated, fallback, markdown)``.
    """
    mode = cfg.mode

    if mode == "off":
        audit_log("CodeInterpreter.run_python", "refused",
                  {"reason": "sandbox disabled"}, parent_id=audit_id)
        return ("none", False, False,
                "# Code execution refused\n\n"
                "Code execution is disabled (`CODE_SANDBOX_MODE=off`).")

    docker_ok = mode in ("auto", "docker") and docker_sandbox.docker_available()

    if mode == "docker" and not docker_ok:
        audit_log("CodeInterpreter.run_python", "refused",
                  {"reason": "docker unavailable in strict mode"}, parent_id=audit_id)
        return ("docker", False, False,
                "# Code execution refused\n\n"
                "`CODE_SANDBOX_MODE=docker` requires Docker, but the Docker "
                "daemon is not reachable. Start Docker or switch to "
                "`CODE_SANDBOX_MODE=auto`.")

    if docker_ok:
        return await _run_python_docker(code, timeout, cfg, audit_id)

    # subprocess (legacy) or auto-fallback
    fallback = mode == "auto"
    return await _run_python_subprocess(code, timeout, audit_id, fallback=fallback)


async def _run_python_docker(code, timeout, cfg, audit_id):
    """Execute inside Docker; format the result. Returns the dispatch tuple."""
    result = await docker_sandbox.run_in_sandbox(
        code,
        timeout=timeout,
        image=cfg.image,
        memory=cfg.memory,
        cpus=cfg.cpus,
        pids_limit=cfg.pids_limit,
        tmpfs_size=cfg.tmpfs_size,
        max_code_bytes=cfg.max_code_bytes,
        max_output_bytes=cfg.max_output_bytes,
        auto_pull=cfg.auto_pull,
    )

    if result.error:
        audit_log("CodeInterpreter.run_python", "error",
                  {"engine": "docker", "error": result.error}, parent_id=audit_id)
        return ("docker", True, False,
                f"# Code execution failed (sandbox)\n\n{result.error}")

    if result.timed_out:
        audit_log("CodeInterpreter.run_python", "timeout",
                  {"engine": "docker", "timeout": timeout}, parent_id=audit_id)
        header = (
            f"# Code execution (engine: docker · isolated · TIMEOUT after {timeout}s)"
        )
    elif result.killed_for_output_limit:
        audit_log("CodeInterpreter.run_python", "output_limit",
                  {"engine": "docker"}, parent_id=audit_id)
        header = "# Code execution (engine: docker · isolated · OUTPUT LIMIT — killed)"
    else:
        audit_log(
            "CodeInterpreter.run_python", "completed",
            {"engine": "docker", "return_code": result.exit_code,
             "stdout_chars": len(result.stdout), "stderr_chars": len(result.stderr)},
            parent_id=audit_id,
        )
        header = f"# Code execution (engine: docker · isolated · exit code: {result.exit_code})"

    out = _truncate(result.stdout)
    err = _truncate(result.stderr)
    if result.stdout_truncated and "[…truncated" not in out:
        out += "\n[…output truncated at sandbox limit]"
    if result.stderr_truncated and "[…truncated" not in err:
        err += "\n[…output truncated at sandbox limit]"
    body = (
        f"{header}\n\n"
        f"## STDOUT\n```\n{out or '(empty)'}\n```\n\n"
        f"## STDERR\n```\n{err or '(empty)'}\n```"
    )
    return ("docker", True, False, body)


async def _run_python_subprocess(code, timeout, audit_id, *, fallback):
    """Legacy subprocess execution (NOT isolated). Returns the dispatch tuple."""
    warning = ""
    if fallback:
        warning = (
            "> ⚠️ **Docker sandbox unavailable — ran on the host with NO isolation.**\n"
            "> Code had host filesystem/network access. Start Docker for a real "
            "sandbox, or set `CODE_SANDBOX_MODE=docker` to refuse unsandboxed runs.\n\n"
        )

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False, dir=str(WORKSPACE_DIR), encoding="utf-8",
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
            audit_log("CodeInterpreter.run_python", "timeout",
                      {"engine": "subprocess", "timeout": timeout}, parent_id=audit_id)
            return ("subprocess", False, fallback,
                    f"{warning}# Code execution (engine: subprocess · NOT isolated · "
                    f"TIMEOUT after {timeout}s)")
        rc = proc.returncode
        out = stdout.decode("utf-8", errors="replace")
        err = stderr.decode("utf-8", errors="replace")
        audit_log(
            "CodeInterpreter.run_python", "completed",
            {"engine": "subprocess", "return_code": rc,
             "stdout_chars": len(out), "stderr_chars": len(err)},
            parent_id=audit_id,
        )
        body = (
            f"{warning}# Code execution (engine: subprocess · NOT isolated · exit code: {rc})\n\n"
            f"## STDOUT\n```\n{_truncate(out) or '(empty)'}\n```\n\n"
            f"## STDERR\n```\n{_truncate(err) or '(empty)'}\n```"
        )
        return ("subprocess", False, fallback, body)
    except Exception as exc:  # noqa: BLE001
        logger.exception("run_python (subprocess) failed")
        audit_log("CodeInterpreter.run_python", "error",
                  {"engine": "subprocess", "error": str(exc)}, parent_id=audit_id)
        return ("subprocess", False, fallback, f"Code execution failed: {exc!s}")
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
