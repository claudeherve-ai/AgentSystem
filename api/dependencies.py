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
