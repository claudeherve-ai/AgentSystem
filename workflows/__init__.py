"""
AgentSystem — Durable Workflows package (PR5).

Public surface for the optional MS Agent Framework Workflows integration. Routes
use the process-wide singleton :func:`get_workflow_engine`; tests instantiate
:class:`WorkflowEngine` directly with an injected ``WorkflowConfig`` so they can
pin a ``tmp_path`` checkpoint directory.
"""
from __future__ import annotations

from typing import Optional

from .engine import (
    PIPELINE_ID,
    CheckpointInfo,
    WorkflowCheckpointNotFoundError,
    WorkflowEngine,
    WorkflowError,
    WorkflowInputError,
    WorkflowNotFoundError,
    WorkflowResumeError,
    WorkflowRunRecord,
    WorkflowStep,
    WorkflowUnavailableError,
)

__all__ = [
    "PIPELINE_ID",
    "CheckpointInfo",
    "WorkflowEngine",
    "WorkflowError",
    "WorkflowUnavailableError",
    "WorkflowInputError",
    "WorkflowNotFoundError",
    "WorkflowCheckpointNotFoundError",
    "WorkflowResumeError",
    "WorkflowRunRecord",
    "WorkflowStep",
    "get_workflow_engine",
]

_ENGINE: Optional[WorkflowEngine] = None


def get_workflow_engine() -> WorkflowEngine:
    """Return the lazily-created, process-wide :class:`WorkflowEngine`."""
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = WorkflowEngine()
    return _ENGINE
