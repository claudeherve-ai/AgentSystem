"""
AgentSystem — Durable Workflow Engine (PR5, MS Agent Framework Workflows)

A thin, fully-optional durable orchestration layer built on the **Microsoft
Agent Framework Workflows** runtime. It exposes a small, credential-free demo
pipeline (``demo-v1``) whose only purpose is to make the framework's
*checkpoint / resume* capability real, testable in CI, and drivable over REST —
**with no LLM keys and no external services**.

Design contract (deliberately conservative, mirrors ``tools/azure_search``):

  * The ``agent_framework`` SDK is imported behind a guarded ``try``. If it is
    not importable the module STILL imports cleanly and every public method
    degrades to a clean "disabled" answer instead of raising. The capability is
    therefore safe to register unconditionally in ``api/main``.
  * The demo pipeline is a fixed, acyclic chain of **pure, deterministic
    string transforms**. The same input always yields the same output, and a
    resumed run reproduces the original output byte-for-byte. No randomness, no
    clock, no network — so checkpoint round-trips are verifiable offline.
  * Durable state lives under ``WorkflowConfig.checkpoint_dir``. Every run gets
    its OWN subdirectory (``<checkpoint_dir>/<run_id>/``) so concurrent runs
    cannot cross-contaminate each other's checkpoints and retention can prune a
    whole run atomically.
  * Safety rails (from :class:`config.WorkflowConfig`) cap the blast radius of
    an enabled-by-default feature: input size, step count, and a retention cap
    on the number of persisted run directories.

Nothing here is cached: each ``run`` / ``resume`` rebuilds a fresh
``Workflow`` from the step definitions. The framework requires that a resumed
workflow share the SAME ``name`` + executor ids + checkpoint storage as the run
that produced the checkpoint, which this module guarantees by construction.
"""
from __future__ import annotations

import logging
import re
import shutil
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

# ── Guarded SDK import ───────────────────────────────────────────────────────
try:  # pragma: no cover - exercised only when the optional SDK is installed
    from typing import Never

    from agent_framework import (
        FileCheckpointStorage,
        WorkflowBuilder,
        WorkflowContext,
        executor,
    )

    _WORKFLOWS_AVAILABLE = True
except Exception:  # noqa: BLE001 - any import problem => feature simply off
    Never = None  # type: ignore[assignment,misc]
    FileCheckpointStorage = None  # type: ignore[assignment]
    WorkflowBuilder = None  # type: ignore[assignment]
    WorkflowContext = None  # type: ignore[assignment]
    executor = None  # type: ignore[assignment]
    _WORKFLOWS_AVAILABLE = False

# Stable identifier for the built-in pipeline. Part of every workflow name so a
# checkpoint can only ever be resumed by the same logical pipeline.
PIPELINE_ID = "demo-v1"

# A run id is a short, filesystem-safe token: it becomes a directory name.
_RUN_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
# Checkpoint ids produced by the framework are uuids; accept the same charset.
_CHECKPOINT_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")


# ── Errors ───────────────────────────────────────────────────────────────────
class WorkflowError(Exception):
    """Base class for all durable-workflow errors."""


class WorkflowUnavailableError(WorkflowError):
    """The workflow runtime is unavailable (SDK missing or feature disabled).

    Maps to HTTP 503 at the route layer.
    """


class WorkflowInputError(WorkflowError):
    """The caller supplied invalid input (bad run id, oversized text, …).

    Maps to HTTP 400.
    """


class WorkflowNotFoundError(WorkflowError):
    """No such run / no checkpoints for the run. Maps to HTTP 404."""


class WorkflowCheckpointNotFoundError(WorkflowError):
    """The requested checkpoint id does not belong to the run. HTTP 404."""


class WorkflowResumeError(WorkflowError):
    """The framework refused to resume the checkpoint. Maps to HTTP 409."""


# ── Value objects ────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class WorkflowStep:
    """A single pipeline stage: a name plus a pure ``str -> str`` transform."""

    name: str
    transform: Callable[[str], str]


@dataclass(frozen=True)
class CheckpointInfo:
    """A persisted superstep boundary for a run."""

    checkpoint_id: str
    iteration: int

    def to_dict(self) -> dict[str, Any]:
        return {"checkpoint_id": self.checkpoint_id, "iteration": self.iteration}


@dataclass
class WorkflowRunRecord:
    """The outcome of a ``run`` / ``resume`` call."""

    run_id: str
    pipeline_id: str
    status: str
    output: str
    checkpoints: list[dict[str, Any]] = field(default_factory=list)
    superstep_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "pipeline_id": self.pipeline_id,
            "status": self.status,
            "output": self.output,
            "checkpoints": self.checkpoints,
            "superstep_count": self.superstep_count,
        }


# ── Demo pipeline (pure, deterministic, credential-free) ─────────────────────
def _demo_steps() -> list[WorkflowStep]:
    """The built-in ``demo-v1`` pipeline: a 4-stage deterministic chain.

    Each stage appends a labelled marker so the final output encodes the full
    path taken. Because every transform is a pure function of its input, the
    chain is perfectly reproducible — which is exactly what makes checkpoint /
    resume verifiable without any model or service.
    """

    def intake(text: str) -> str:
        return f"intake({text.strip()})"

    def plan(text: str) -> str:
        return f"plan[{text}]"

    def synthesize(text: str) -> str:
        return f"synthesize<{text}>"

    def finalize(text: str) -> str:
        return f"final::{text}"

    return [
        WorkflowStep("intake", intake),
        WorkflowStep("plan", plan),
        WorkflowStep("synthesize", synthesize),
        WorkflowStep("finalize", finalize),
    ]


# ── Executor factory ─────────────────────────────────────────────────────────
def _make_executor(step: WorkflowStep, *, terminal: bool):
    """Build a framework function-executor from a pure step.

    A terminal executor *yields* the workflow output; a non-terminal executor
    *sends* its transformed message to the next edge. Only ever called when the
    SDK is importable, so ``WorkflowContext`` / ``Never`` are real types here.
    """
    if terminal:

        async def _run_terminal(
            message: str, ctx: "WorkflowContext[Never, str]"
        ) -> None:
            await ctx.yield_output(step.transform(message))

        return executor(_run_terminal, id=step.name)

    async def _run_step(message: str, ctx: "WorkflowContext[str]") -> None:
        await ctx.send_message(step.transform(message))

    return executor(_run_step, id=step.name)


def _build_workflow(steps: list[WorkflowStep], *, name: str, storage):
    """Assemble (and ``build``) a fresh ``Workflow`` from ``steps``.

    A new graph is constructed on every call — never cached — so the engine
    stays stateless and a resumed run rebuilds an identical topology.
    """
    last = len(steps) - 1
    execs = [
        _make_executor(step, terminal=(i == last)) for i, step in enumerate(steps)
    ]
    builder = WorkflowBuilder(
        name=name,
        start_executor=execs[0],
        checkpoint_storage=storage,
        output_from="all",
    )
    for src, tgt in zip(execs, execs[1:]):
        builder.add_edge(src, tgt)
    return builder.build()


# ── Engine ───────────────────────────────────────────────────────────────────
class WorkflowEngine:
    """Durable workflow facade over the MS Agent Framework runtime.

    Construct with no arguments for the production singleton (reads live config
    from the environment) or pass an explicit :class:`config.WorkflowConfig` in
    tests to pin a ``tmp_path`` checkpoint dir and bounds.
    """

    def __init__(self, config: Optional[Any] = None) -> None:
        self._injected = config

    # -- config (read live, like azure_search) --------------------------------
    def _cfg(self):
        if self._injected is not None:
            return self._injected
        from config import get_workflow_config

        return get_workflow_config()

    # -- introspection --------------------------------------------------------
    def enabled(self) -> bool:
        """True only when the SDK is importable AND config enables workflows."""
        if not _WORKFLOWS_AVAILABLE:
            return False
        try:
            return bool(self._cfg().enabled)
        except Exception as exc:  # noqa: BLE001 - config issues => disabled
            logger.debug("WorkflowEngine.enabled: config load failed (%s)", exc)
            return False

    def status(self) -> dict[str, Any]:
        """Always-200-safe diagnostic snapshot for the ``/status`` route."""
        snapshot: dict[str, Any] = {
            "sdk_available": _WORKFLOWS_AVAILABLE,
            "enabled": False,
            "pipeline_id": PIPELINE_ID,
            "checkpoint_dir": None,
            "max_iterations": None,
            "max_runs": None,
            "max_input_chars": None,
            "steps": [s.name for s in _demo_steps()],
        }
        try:
            cfg = self._cfg()
            snapshot["enabled"] = bool(cfg.enabled and _WORKFLOWS_AVAILABLE)
            snapshot["checkpoint_dir"] = cfg.checkpoint_dir
            snapshot["max_iterations"] = cfg.max_iterations
            snapshot["max_runs"] = cfg.max_runs
            snapshot["max_input_chars"] = cfg.max_input_chars
        except Exception as exc:  # noqa: BLE001
            logger.debug("WorkflowEngine.status: config load failed (%s)", exc)
        return snapshot

    # -- validation helpers ---------------------------------------------------
    def _require_available(self) -> None:
        if not self.enabled():
            raise WorkflowUnavailableError(
                "Durable workflows are unavailable. Install "
                "'agent-framework-core' and set WORKFLOW_ENABLED=true."
            )

    def _resolve_steps(
        self, steps: Optional[list[WorkflowStep]], cfg
    ) -> list[WorkflowStep]:
        resolved = list(steps) if steps else _demo_steps()
        if not resolved:
            raise WorkflowInputError("A workflow must have at least one step.")
        if len(resolved) > cfg.max_iterations:
            raise WorkflowInputError(
                f"Pipeline has {len(resolved)} steps, which exceeds the "
                f"configured max_iterations ({cfg.max_iterations})."
            )
        names = [s.name for s in resolved]
        if len(set(names)) != len(names):
            raise WorkflowInputError("Workflow step names must be unique.")
        for name in names:
            if not _RUN_ID_RE.match(name):
                raise WorkflowInputError(
                    f"Invalid step name '{name}'. Use 1-64 chars [A-Za-z0-9_-]."
                )
        return resolved

    @staticmethod
    def _coerce_run_id(run_id: Optional[str]) -> str:
        if run_id is None:
            return uuid.uuid4().hex
        candidate = run_id.strip()
        if not _RUN_ID_RE.match(candidate):
            raise WorkflowInputError(
                f"Invalid run_id '{run_id}'. Use 1-64 chars [A-Za-z0-9_-]."
            )
        return candidate

    @staticmethod
    def _validate_checkpoint_id(checkpoint_id: str) -> str:
        candidate = (checkpoint_id or "").strip()
        if not _CHECKPOINT_ID_RE.match(candidate):
            raise WorkflowInputError(
                f"Invalid checkpoint_id '{checkpoint_id}'."
            )
        return candidate

    def _validate_input(self, input_text: str, cfg) -> str:
        if input_text is None or not str(input_text).strip():
            raise WorkflowInputError("Input text must be a non-empty string.")
        text = str(input_text)
        if len(text) > cfg.max_input_chars:
            raise WorkflowInputError(
                f"Input is {len(text)} chars, exceeding the configured "
                f"max_input_chars ({cfg.max_input_chars})."
            )
        return text

    # -- filesystem helpers ---------------------------------------------------
    def _root(self, cfg) -> Path:
        root = Path(cfg.checkpoint_dir)
        root.mkdir(parents=True, exist_ok=True)
        return root

    def _run_dir(self, cfg, run_id: str) -> Path:
        run_dir = self._root(cfg) / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        return run_dir

    def _enforce_retention(self, cfg) -> None:
        """Prune the oldest run directories beyond ``max_runs`` (best effort)."""
        try:
            root = self._root(cfg)
            subdirs = [p for p in root.iterdir() if p.is_dir()]
            if len(subdirs) <= cfg.max_runs:
                return
            subdirs.sort(key=lambda p: p.stat().st_mtime)
            for stale in subdirs[: len(subdirs) - cfg.max_runs]:
                shutil.rmtree(stale, ignore_errors=True)
        except Exception as exc:  # noqa: BLE001 - retention must never fail a run
            logger.debug("retention prune skipped (%s)", exc)

    # -- checkpoint collection ------------------------------------------------
    @staticmethod
    async def _collect_checkpoints(storage, name: str) -> list[CheckpointInfo]:
        raw = await storage.list_checkpoints(workflow_name=name)
        infos = [
            CheckpointInfo(
                checkpoint_id=str(getattr(c, "checkpoint_id", "")),
                iteration=int(getattr(c, "iteration_count", 0) or 0),
            )
            for c in (raw or [])
            if getattr(c, "checkpoint_id", None)
        ]
        infos.sort(key=lambda c: c.iteration)
        return infos

    @staticmethod
    def _extract_output(result) -> str:
        outs = result.get_outputs() if result is not None else None
        return str(outs[-1]) if outs else ""

    def _workflow_name(self, run_id: str) -> str:
        return f"{PIPELINE_ID}:{run_id}"

    # -- public API -----------------------------------------------------------
    async def run(
        self,
        input_text: str,
        *,
        steps: Optional[list[WorkflowStep]] = None,
        run_id: Optional[str] = None,
    ) -> WorkflowRunRecord:
        """Execute the pipeline durably, persisting a checkpoint per superstep."""
        self._require_available()
        cfg = self._cfg()
        text = self._validate_input(input_text, cfg)
        resolved = self._resolve_steps(steps, cfg)
        rid = self._coerce_run_id(run_id)
        name = self._workflow_name(rid)

        run_dir = self._run_dir(cfg, rid)
        storage = FileCheckpointStorage(str(run_dir))
        workflow = _build_workflow(resolved, name=name, storage=storage)

        result = await workflow.run(text)
        output = self._extract_output(result)
        checkpoints = await self._collect_checkpoints(storage, name)

        self._enforce_retention(cfg)
        return WorkflowRunRecord(
            run_id=rid,
            pipeline_id=PIPELINE_ID,
            status="completed",
            output=output,
            checkpoints=[c.to_dict() for c in checkpoints],
            superstep_count=len(checkpoints),
        )

    async def list_checkpoints(self, run_id: str) -> list[CheckpointInfo]:
        """Return persisted checkpoints for a prior run (404 if unknown)."""
        self._require_available()
        cfg = self._cfg()
        rid = self._coerce_run_id(run_id)
        run_dir = self._root(cfg) / rid
        if not run_dir.is_dir():
            raise WorkflowNotFoundError(f"No such run '{rid}'.")
        storage = FileCheckpointStorage(str(run_dir))
        name = self._workflow_name(rid)
        infos = await self._collect_checkpoints(storage, name)
        if not infos:
            raise WorkflowNotFoundError(f"Run '{rid}' has no checkpoints.")
        return infos

    async def resume(
        self,
        run_id: str,
        checkpoint_id: str,
        *,
        steps: Optional[list[WorkflowStep]] = None,
    ) -> WorkflowRunRecord:
        """Resume a prior run from a persisted checkpoint.

        Preflight is strict: an unknown run or an unknown checkpoint yields 404
        BEFORE the framework is invoked, and a framework-level resume failure is
        surfaced as 409 rather than a raw 500.
        """
        self._require_available()
        cfg = self._cfg()
        rid = self._coerce_run_id(run_id)
        cid = self._validate_checkpoint_id(checkpoint_id)
        resolved = self._resolve_steps(steps, cfg)

        run_dir = self._root(cfg) / rid
        if not run_dir.is_dir():
            raise WorkflowNotFoundError(f"No such run '{rid}'.")

        storage = FileCheckpointStorage(str(run_dir))
        name = self._workflow_name(rid)
        existing = await self._collect_checkpoints(storage, name)
        if not existing:
            raise WorkflowNotFoundError(f"Run '{rid}' has no checkpoints.")
        if cid not in {c.checkpoint_id for c in existing}:
            raise WorkflowCheckpointNotFoundError(
                f"Checkpoint '{cid}' does not belong to run '{rid}'."
            )

        workflow = _build_workflow(resolved, name=name, storage=storage)
        try:
            result = await workflow.run(checkpoint_id=cid)
        except WorkflowError:
            raise
        except Exception as exc:  # noqa: BLE001 - framework refusal => 409
            raise WorkflowResumeError(
                f"Failed to resume run '{rid}' from checkpoint '{cid}': {exc}"
            ) from exc

        output = self._extract_output(result)
        checkpoints = await self._collect_checkpoints(storage, name)
        return WorkflowRunRecord(
            run_id=rid,
            pipeline_id=PIPELINE_ID,
            status="resumed",
            output=output,
            checkpoints=[c.to_dict() for c in checkpoints],
            superstep_count=len(checkpoints),
        )
