"""
Code interpreter tool — Python execution with selectable, fail-closed isolation.

Execution engine is chosen by :func:`agentsystem.sandbox.resolve_sandbox_engine`,
which is fail-closed by design:

* In a container / production runtime, generated code NEVER runs in a host
  subprocess. ``CODE_SANDBOX_MODE=auto`` prefers Azure Container Apps Dynamic
  Sessions, then a local Docker sandbox, and otherwise **refuses**.
* A local Docker sandbox is used only when Docker is available.
* The explicit ``subprocess`` mode is permitted only for local development
  outside a container; it is refused in a container / production.

Modes (env ``CODE_SANDBOX_MODE``):
    auto              Dynamic Sessions if configured, else Docker if available,
                      else REFUSE (never a host subprocess) — default
    dynamic_sessions  Azure Container Apps Dynamic Sessions only; refuse if unset
    docker            Docker only; refuse if the daemon is unavailable
    subprocess        Local host subprocess (dev only; refused in container/prod)
    off               Refuse to execute code at all

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
    """Pick an execution engine and return a Markdown report.

    Engine selection is centralized in :func:`agentsystem.sandbox.resolve_sandbox_engine`
    which fails closed: ``auto`` never runs a host subprocess in a container /
    production, and unsupported runtimes are refused with a user-safe message.

    Returns ``(engine, isolated, fallback, markdown)``.
    """
    from agentsystem.sandbox import (
        ENGINE_DOCKER,
        ENGINE_DYNAMIC_SESSIONS,
        ENGINE_OFF,
        ENGINE_REFUSE,
        ENGINE_SUBPROCESS,
        build_dynamic_sessions_interpreter,
        resolve_sandbox_engine,
    )
    from agentsystem.settings import get_settings

    settings = get_settings()
    docker_ok = docker_sandbox.docker_available()
    try:
        ds_interpreter = build_dynamic_sessions_interpreter(settings)
    except Exception:  # noqa: BLE001 - unconfigured/adapter error → not available
        ds_interpreter = None

    engine = resolve_sandbox_engine(
        cfg.mode,
        in_container=settings.in_container,
        is_production=settings.is_production,
        docker_available=docker_ok,
        dynamic_sessions_configured=ds_interpreter is not None,
    )

    if engine == ENGINE_OFF:
        audit_log("CodeInterpreter.run_python", "refused",
                  {"reason": "sandbox disabled"}, parent_id=audit_id)
        return ("none", False, False,
                "# Code execution refused\n\n"
                "Code execution is disabled (`CODE_SANDBOX_MODE=off`).")

    if engine == ENGINE_REFUSE:
        reason = _refuse_reason(cfg.mode, settings, docker_ok)
        audit_log("CodeInterpreter.run_python", "refused",
                  {"reason": reason, "mode": cfg.mode}, parent_id=audit_id)
        return ("none", False, False,
                "# Code execution refused (fail-closed)\n\n" + reason)

    if engine == ENGINE_DYNAMIC_SESSIONS:
        return await _run_python_dynamic_sessions(
            ds_interpreter, code, timeout, audit_id
        )

    if engine == ENGINE_DOCKER:
        return await _run_python_docker(code, timeout, cfg, audit_id)

    # engine == ENGINE_SUBPROCESS — only reachable via the EXPLICIT subprocess
    # mode outside a container/production. It is not an implicit fallback.
    return await _run_python_subprocess(code, timeout, audit_id, fallback=False)


def _refuse_reason(mode: str, settings, docker_ok: bool) -> str:
    """Human-safe explanation for a fail-closed refusal."""
    if mode == "dynamic_sessions":
        return (
            "`CODE_SANDBOX_MODE=dynamic_sessions` requires a configured Azure "
            "Container Apps Dynamic Sessions pool (`DYNAMIC_SESSIONS_ENDPOINT`)."
        )
    if mode == "docker":
        return (
            "`CODE_SANDBOX_MODE=docker` requires a reachable Docker daemon, but "
            "none is available."
        )
    if mode == "subprocess":
        return (
            "Host subprocess execution is not permitted in a container or "
            "production runtime. Use Dynamic Sessions (`DYNAMIC_SESSIONS_ENDPOINT`) "
            "or a Docker sandbox."
        )
    # auto with nothing available
    return (
        "No isolated code sandbox is available. Configure Azure Container Apps "
        "Dynamic Sessions (`DYNAMIC_SESSIONS_ENDPOINT`) or start Docker. Host "
        "subprocess execution is never used automatically."
    )


async def _run_python_dynamic_sessions(interpreter, code, timeout, audit_id):
    """Execute inside Azure Container Apps Dynamic Sessions."""
    result = await interpreter.run_python(code, timeout=timeout)
    if result.error:
        audit_log("CodeInterpreter.run_python", "error",
                  {"engine": "dynamic_sessions", "error": result.error},
                  parent_id=audit_id)
        return ("dynamic_sessions", True, False,
                f"# Code execution failed (dynamic sessions)\n\n{result.error}")
    audit_log(
        "CodeInterpreter.run_python", "completed",
        {"engine": "dynamic_sessions", "exit_code": result.exit_code},
        parent_id=audit_id,
    )
    header = (
        f"# Code execution (engine: dynamic_sessions · isolated · "
        f"exit code: {result.exit_code})"
    )
    body = (
        f"{header}\n\n"
        f"## STDOUT\n```\n{_truncate(result.stdout) or '(empty)'}\n```\n\n"
        f"## STDERR\n```\n{_truncate(result.stderr) or '(empty)'}\n```"
    )
    return ("dynamic_sessions", True, False, body)


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
