"""
AgentSystem — Shared API Dependencies
=====================================
Houses the lazily-initialised orchestrator singleton.

This module is intentionally free of any dependency on ``api.main`` so that the
route modules and the app factory can both import :func:`get_orchestrator`
without creating a circular import (``api.main`` imports the routers, and the
routers need the orchestrator accessor).
"""
from __future__ import annotations

import logging

logger = logging.getLogger("agentsystem.api")

# ── Orchestrator singleton (lazy init) ──────────────────────────────────────
_orchestrator = None


def get_orchestrator():
    """Lazy-load the orchestrator with all registered agents."""
    global _orchestrator
    if _orchestrator is None:
        from agents.factory import build_orchestrator

        _orchestrator = build_orchestrator()
        logger.info(
            "Orchestrator initialized with %d agents",
            len(_orchestrator.agent_names),
        )
    return _orchestrator


# ── Durable run service singleton (lazy init) ───────────────────────────────
_run_service = None


def get_run_service():
    """Lazy-load the durable run service.

    Wires the run service to the shared orchestrator and the configured durable
    executor. Tests inject their own :class:`agentsystem.services.RunService`.
    """
    global _run_service
    if _run_service is None:
        from agentsystem.services import RunService

        _run_service = RunService(orchestrator_provider=get_orchestrator)
        logger.info("Durable run service initialized")
    return _run_service


def set_run_service(service) -> None:
    """Inject/replace the run service (tests)."""
    global _run_service
    _run_service = service
