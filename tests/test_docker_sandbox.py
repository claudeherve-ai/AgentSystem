"""
Tests for tools.docker_sandbox — the hardened Docker code-execution sandbox.

The pure-logic tests (result model, argument vector, size guard) run anywhere.
The execution tests are skipped automatically when the Docker daemon is not
reachable, so the suite stays green on machines without Docker.
"""

import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools import docker_sandbox as sbx
from tools.docker_sandbox import SandboxResult, docker_available, run_in_sandbox

_SANDBOX_IMAGE = "python:3.12-slim"


def _sandbox_image_ready() -> bool:
    """True only when Docker is reachable AND the sandbox image is present.

    The live execution tests need the image locally; ``run_in_sandbox`` does not
    auto-pull by default. Probing here (instead of only checking the daemon)
    keeps the suite green on machines that have Docker but have not pulled the
    image, while still running the tests for real wherever the image exists
    (local dev, and CI after the pre-pull step).
    """
    if not docker_available():
        return False
    try:
        return asyncio.run(sbx.image_available(_SANDBOX_IMAGE))
    except Exception:
        return False


requires_sandbox = pytest.mark.skipif(
    not _sandbox_image_ready(),
    reason=f"Docker daemon or sandbox image '{_SANDBOX_IMAGE}' not available",
)


# ─── Pure logic (no Docker required) ─────────────────────────────────────────
def test_sandbox_result_ok_property():
    assert SandboxResult(exit_code=0).ok is True
    assert SandboxResult(exit_code=1).ok is False
    assert SandboxResult(exit_code=0, timed_out=True).ok is False
    assert SandboxResult(exit_code=0, error="boom").ok is False
    assert SandboxResult(exit_code=None).ok is False
    print("✅ SandboxResult.ok reflects exit/timeout/error")


def test_build_run_args_enforces_isolation():
    args = sbx._build_run_args(
        container_name="agentsys-sbx-test",
        image="python:3.12-slim",
        memory="256m",
        cpus="1",
        pids_limit=128,
        tmpfs_size="64m",
        max_output_bytes=32_000,
    )
    joined = " ".join(args)
    # Network egress disabled.
    assert "--network" in args and "none" in args
    # Immutable rootfs + non-root user + dropped caps + no-new-privs.
    assert "--read-only" in args
    assert "--cap-drop" in args and "ALL" in args
    assert "--security-opt" in args and "no-new-privileges" in args
    assert "--user" in args and "65534:65534" in args
    # Resource bounds present.
    assert "--memory" in args and "--cpus" in args and "--pids-limit" in args
    assert "--init" in args
    # Code is fed over stdin to an isolated interpreter (never a host path).
    assert args[-3:] == ["python", "-I", "-"]
    assert "agentsys.sandbox=true" in joined
    print("✅ docker run vector is hardened")


def test_oversized_code_rejected_without_docker():
    # Size guard runs before any docker call, so this works with no daemon.
    result = asyncio.run(run_in_sandbox("print('x')" * 100, max_code_bytes=10))
    assert result.error
    assert "too large" in result.error
    assert result.ok is False
    print("✅ Oversized code rejected pre-flight")


def test_docker_available_returns_bool():
    assert isinstance(docker_available(), bool)
    print("✅ docker_available() returns bool")


# ─── Live execution (skipped when Docker absent) ─────────────────────────────
@requires_sandbox
def test_run_in_sandbox_happy_path():
    result = asyncio.run(run_in_sandbox("print(40 + 2)", timeout=30))
    assert result.ok, f"expected ok, got: {result}"
    assert result.exit_code == 0
    assert "42" in result.stdout
    assert result.engine == "docker"
    print("✅ Sandbox executes trivial code")


@requires_sandbox
def test_run_in_sandbox_network_is_blocked():
    code = (
        "import socket\n"
        "socket.setdefaulttimeout(5)\n"
        "socket.create_connection(('1.1.1.1', 53))\n"
        "print('REACHED-NETWORK')\n"
    )
    result = asyncio.run(run_in_sandbox(code, timeout=30))
    assert "REACHED-NETWORK" not in result.stdout
    assert result.exit_code not in (0, None)  # network attempt fails
    print("✅ Sandbox blocks network egress")


@requires_sandbox
def test_run_in_sandbox_times_out():
    result = asyncio.run(run_in_sandbox("while True:\n    pass", timeout=3))
    assert result.timed_out is True
    assert result.ok is False
    print("✅ Sandbox enforces wall-clock timeout")
