"""
tools.docker_sandbox — isolated, dependency-free Python execution via Docker.

This module runs untrusted Python inside a hardened, ephemeral Docker container.
It shells out to the Docker CLI (no SDK dependency), injecting code over stdin so
nothing is ever written to a host-visible path.

Isolation enforced on every run (validated live):
  --network none          no egress
  --read-only             immutable root filesystem
  --tmpfs /tmp            only writable surface, size-capped, mode 1777
  --user 65534:65534      run as "nobody"
  --cap-drop ALL          drop all Linux capabilities
  --security-opt no-new-privileges
  --pids-limit / --memory / --cpus / --ulimit  resource bounds
  --init                  reap zombies; clean signal handling

Windows note: ``docker.exe`` and its credential helper live in Docker Desktop's
``resources\\bin`` directory which is frequently NOT on the agent shell PATH. We
resolve the binary explicitly and augment the subprocess PATH so credential
lookups (needed for image pulls) succeed.

Everything degrades gracefully: if Docker is unavailable, callers can fall back
to subprocess execution (see ``tools.code_interpreter``).
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import time
import uuid
from dataclasses import dataclass

logger = logging.getLogger("agentsystem.sandbox")

# Label applied to every sandbox container so we can reap strays.
SANDBOX_LABEL = "agentsys.sandbox=true"
_CONTAINER_PREFIX = "agentsys-sbx-"

# Known Docker Desktop / Engine install locations to probe when docker is not
# already on PATH (Windows + common Linux/macOS paths).
_KNOWN_DOCKER_PATHS = (
    r"C:\Program Files\Docker\Docker\resources\bin\docker.exe",
    r"C:\ProgramData\DockerDesktop\version-bin\docker.exe",
    "/usr/bin/docker",
    "/usr/local/bin/docker",
    "/opt/homebrew/bin/docker",
)

# TTL (seconds) for the cached docker-availability probe.
_AVAIL_TTL = 30.0

_docker_bin_cache: str | None = None
_avail_cache: tuple[float, bool] | None = None
_pull_lock = asyncio.Lock()


@dataclass
class SandboxResult:
    """Outcome of a sandboxed execution."""

    stdout: str = ""
    stderr: str = ""
    exit_code: int | None = None
    timed_out: bool = False
    killed_for_output_limit: bool = False
    stdout_truncated: bool = False
    stderr_truncated: bool = False
    engine: str = "docker"
    container_name: str = ""
    error: str = ""
    duration_s: float = 0.0

    @property
    def ok(self) -> bool:
        return (
            self.exit_code == 0
            and not self.timed_out
            and not self.error
        )


# ---------------------------------------------------------------------------
# Docker binary / environment resolution
# ---------------------------------------------------------------------------
def _find_docker() -> str | None:
    """Locate the docker binary, caching the result."""
    global _docker_bin_cache
    if _docker_bin_cache:
        return _docker_bin_cache
    found = shutil.which("docker")
    if not found:
        for candidate in _KNOWN_DOCKER_PATHS:
            if os.path.isfile(candidate):
                found = candidate
                break
    if found:
        _docker_bin_cache = found
    return found


def _docker_env() -> dict[str, str]:
    """Return an environment whose PATH includes the docker bin directory.

    The Docker credential helper (``docker-credential-desktop``) lives beside
    ``docker.exe``; without it on PATH, image pulls fail. We prepend that
    directory while preserving the existing PATH.
    """
    env = dict(os.environ)
    docker_bin = _find_docker()
    if docker_bin:
        bin_dir = os.path.dirname(docker_bin)
        existing = env.get("PATH", "")
        parts = existing.split(os.pathsep) if existing else []
        if bin_dir and bin_dir not in parts:
            env["PATH"] = bin_dir + (os.pathsep + existing if existing else "")
    return env


async def _run_docker(
    args: list[str], *, timeout: float, stdin_data: bytes | None = None
) -> tuple[int | None, bytes, bytes, bool]:
    """Run ``docker <args>`` capturing output. Returns (rc, out, err, timed_out)."""
    docker_bin = _find_docker()
    if not docker_bin:
        return None, b"", b"docker binary not found", False
    try:
        proc = await asyncio.create_subprocess_exec(
            docker_bin,
            *args,
            stdin=asyncio.subprocess.PIPE if stdin_data is not None else asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=_docker_env(),
        )
    except OSError as exc:
        # e.g. docker binary vanished or isn't executable. Callers
        # (docker_available, reap, teardown) all assume this never raises.
        return None, b"", f"failed to spawn docker: {exc}".encode(), False
    try:
        out, err = await asyncio.wait_for(
            proc.communicate(input=stdin_data), timeout=timeout
        )
        return proc.returncode, out, err, False
    except asyncio.TimeoutError:
        with _suppress():
            proc.kill()
        with _suppress():
            await proc.wait()
        return None, b"", b"", True


class _suppress:
    """Tiny context manager that swallows all exceptions (cleanup paths)."""

    def __enter__(self) -> "_suppress":
        return self

    def __exit__(self, *_exc: object) -> bool:
        return True


# ---------------------------------------------------------------------------
# Availability + image readiness
# ---------------------------------------------------------------------------
def docker_available() -> bool:
    """Cheap, TTL-cached check that the Docker daemon is reachable."""
    global _avail_cache
    now = time.time()
    if _avail_cache and (now - _avail_cache[0]) < _AVAIL_TTL:
        return _avail_cache[1]
    available = _probe_docker()
    _avail_cache = (now, available)
    return available


def _probe_docker() -> bool:
    docker_bin = _find_docker()
    if not docker_bin:
        return False
    try:
        import subprocess

        result = subprocess.run(  # noqa: S603 - fixed binary, fixed args
            [docker_bin, "version", "--format", "{{.Server.Version}}"],
            capture_output=True,
            text=True,
            timeout=5.0,
            env=_docker_env(),
        )
        return result.returncode == 0 and bool(result.stdout.strip())
    except (OSError, ValueError):
        return False
    except Exception:  # noqa: BLE001 - subprocess.TimeoutExpired etc.
        return False


def invalidate_caches() -> None:
    """Clear cached docker binary / availability (used by tests)."""
    global _docker_bin_cache, _avail_cache
    _docker_bin_cache = None
    _avail_cache = None


async def image_available(image: str) -> bool:
    """True if the image is already present locally (no pull)."""
    rc, _out, _err, timed_out = await _run_docker(
        ["image", "inspect", image], timeout=10.0
    )
    return rc == 0 and not timed_out


async def ensure_image(image: str, *, auto_pull: bool, pull_timeout: float = 300.0) -> bool:
    """Ensure ``image`` exists locally, optionally pulling it (serialized)."""
    if await image_available(image):
        return True
    if not auto_pull:
        return False
    async with _pull_lock:
        # Re-check inside the lock — another coroutine may have pulled it.
        if await image_available(image):
            return True
        logger.info("Pulling sandbox image %s (this may take a while)...", image)
        rc, _out, err, timed_out = await _run_docker(
            ["pull", image], timeout=pull_timeout
        )
        if timed_out or rc != 0:
            logger.warning(
                "Image pull failed for %s: %s",
                image,
                err.decode("utf-8", "replace")[:200],
            )
            return False
        return True


# ---------------------------------------------------------------------------
# Stale container reaper
# ---------------------------------------------------------------------------
async def reap_stale_sandboxes() -> int:
    """Force-remove any leftover sandbox containers. Best-effort."""
    rc, out, _err, timed_out = await _run_docker(
        ["ps", "-aq", "--filter", f"label={SANDBOX_LABEL}"], timeout=10.0
    )
    if timed_out or rc != 0:
        return 0
    ids = [line.strip() for line in out.decode("utf-8", "replace").splitlines() if line.strip()]
    if not ids:
        return 0
    await _run_docker(["rm", "-f", *ids], timeout=20.0)
    return len(ids)


# ---------------------------------------------------------------------------
# Core execution
# ---------------------------------------------------------------------------
def _build_run_args(
    *,
    container_name: str,
    image: str,
    memory: str,
    cpus: str,
    pids_limit: int,
    tmpfs_size: str,
    max_output_bytes: int,
) -> list[str]:
    """Assemble the hardened ``docker run`` argument vector."""
    fsize = max(max_output_bytes * 4, 1_000_000)
    return [
        "run",
        "--rm",
        "-i",
        "--name",
        container_name,
        "--label",
        SANDBOX_LABEL,
        "--network",
        "none",
        "--memory",
        memory,
        "--memory-swap",
        memory,
        "--cpus",
        cpus,
        "--pids-limit",
        str(pids_limit),
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--read-only",
        "--tmpfs",
        f"/tmp:rw,size={tmpfs_size},mode=1777",
        "--user",
        "65534:65534",
        "--workdir",
        "/tmp",
        "--ulimit",
        "nofile=256:256",
        "--ulimit",
        f"fsize={fsize}:{fsize}",
        "--init",
        "--env",
        "PYTHONDONTWRITEBYTECODE=1",
        "--env",
        "PYTHONIOENCODING=utf-8",
        "--env",
        "PYTHONUTF8=1",
        image,
        "python",
        "-I",
        "-",
    ]


async def _teardown(container_name: str) -> None:
    """Kill + remove a container, ignoring 'no such container' noise."""
    with _suppress():
        await _run_docker(["kill", container_name], timeout=10.0)
    with _suppress():
        await _run_docker(["rm", "-f", container_name], timeout=10.0)


async def run_in_sandbox(
    code: str,
    *,
    timeout: int = 30,
    image: str = "python:3.12-slim",
    memory: str = "256m",
    cpus: str = "1",
    pids_limit: int = 128,
    tmpfs_size: str = "64m",
    max_code_bytes: int = 1_000_000,
    max_output_bytes: int = 32_000,
    auto_pull: bool = False,
) -> SandboxResult:
    """Execute ``code`` inside a hardened, ephemeral Docker container.

    Output from each stream is streamed and capped independently; on timeout or
    output overflow the container is force-killed and removed. Never raises —
    failures are reported via :class:`SandboxResult`.
    """
    started = time.monotonic()
    container_name = _CONTAINER_PREFIX + uuid.uuid4().hex[:12]

    code_bytes = code.encode("utf-8", "replace")
    if len(code_bytes) > max_code_bytes:
        return SandboxResult(
            engine="docker",
            container_name=container_name,
            error=f"code too large ({len(code_bytes)} bytes > {max_code_bytes} limit)",
            duration_s=round(time.monotonic() - started, 3),
        )

    docker_bin = _find_docker()
    if not docker_bin:
        return SandboxResult(
            engine="docker",
            error="docker binary not found on PATH",
            duration_s=round(time.monotonic() - started, 3),
        )

    if not await ensure_image(image, auto_pull=auto_pull):
        return SandboxResult(
            engine="docker",
            container_name=container_name,
            error=(
                f"sandbox image '{image}' not available locally. "
                f"Pull it with `docker pull {image}` or set CODE_SANDBOX_AUTO_PULL=true."
            ),
            duration_s=round(time.monotonic() - started, 3),
        )

    args = _build_run_args(
        container_name=container_name,
        image=image,
        memory=memory,
        cpus=cpus,
        pids_limit=pids_limit,
        tmpfs_size=tmpfs_size,
        max_output_bytes=max_output_bytes,
    )

    try:
        proc = await asyncio.create_subprocess_exec(
            docker_bin,
            *args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=_docker_env(),
        )
    except OSError as exc:
        return SandboxResult(
            engine="docker",
            container_name=container_name,
            error=f"failed to launch docker: {exc}",
            duration_s=round(time.monotonic() - started, 3),
        )

    # Feed code via stdin, then close so the in-container `python -` runs.
    overflow = asyncio.Event()
    state: dict[str, object] = {
        "stdout": bytearray(),
        "stderr": bytearray(),
        "stdout_trunc": False,
        "stderr_trunc": False,
    }

    async def _feed_stdin() -> None:
        assert proc.stdin is not None
        try:
            proc.stdin.write(code_bytes)
            await proc.stdin.drain()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            with _suppress():
                proc.stdin.close()

    async def _pump(stream: asyncio.StreamReader, key: str, trunc_key: str) -> None:
        buf: bytearray = state[key]  # type: ignore[assignment]
        while True:
            chunk = await stream.read(4096)
            if not chunk:
                break
            if len(buf) < max_output_bytes:
                room = max_output_bytes - len(buf)
                buf.extend(chunk[:room])
                if len(chunk) > room:
                    state[trunc_key] = True
                    overflow.set()
            else:
                state[trunc_key] = True
                overflow.set()

    assert proc.stdout is not None and proc.stderr is not None
    feeder = asyncio.create_task(_feed_stdin())
    pump_out = asyncio.create_task(_pump(proc.stdout, "stdout", "stdout_trunc"))
    pump_err = asyncio.create_task(_pump(proc.stderr, "stderr", "stderr_trunc"))
    waiter = asyncio.create_task(proc.wait())
    overflow_waiter = asyncio.create_task(overflow.wait())

    timed_out = False
    killed_for_output = False

    done, _pending = await asyncio.wait(
        {waiter, overflow_waiter},
        timeout=float(timeout),
        return_when=asyncio.FIRST_COMPLETED,
    )

    if waiter not in done:
        # Either timed out or output overflow tripped first -> tear down.
        if overflow_waiter in done:
            killed_for_output = True
        else:
            timed_out = True
        await _teardown(container_name)

    # Ensure the process is reaped, then let the output pumps drain to EOF so we
    # don't drop buffered tail output. Once the process exits (or the container
    # is torn down) its pipes close, so the pumps finish quickly; the timeouts
    # bound a wedged pipe so this can never hang the request.
    with _suppress():
        await asyncio.wait_for(waiter, timeout=10.0)
    with _suppress():
        await asyncio.wait_for(
            asyncio.gather(pump_out, pump_err, return_exceptions=True),
            timeout=5.0,
        )
    for task in (feeder, pump_out, pump_err, overflow_waiter):
        task.cancel()
    with _suppress():
        await asyncio.gather(feeder, pump_out, pump_err, overflow_waiter,
                             return_exceptions=True)

    exit_code = proc.returncode
    return SandboxResult(
        stdout=bytes(state["stdout"]).decode("utf-8", "replace"),  # type: ignore[arg-type]
        stderr=bytes(state["stderr"]).decode("utf-8", "replace"),  # type: ignore[arg-type]
        exit_code=exit_code,
        timed_out=timed_out,
        killed_for_output_limit=killed_for_output,
        stdout_truncated=bool(state["stdout_trunc"]),
        stderr_truncated=bool(state["stderr_trunc"]),
        engine="docker",
        container_name=container_name,
        duration_s=round(time.monotonic() - started, 3),
    )
