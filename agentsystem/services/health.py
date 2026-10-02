"""Truthful health / readiness reporting.

Readiness reflects the ACTUAL state of each dependency. It never issues a model
request on every probe — it only checks that the model dependency is configured
(``settings.model_config_ready``). Each dependency check is fail-safe: a probe
error yields an unhealthy status, never an exception.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from agentsystem.db.session import ping as db_ping
from agentsystem.durable import get_durable_executor
from agentsystem.sandbox import build_dynamic_sessions_interpreter
from agentsystem.services.artifacts import get_artifact_store
from agentsystem.services.rate_limit import get_rate_limiter
from agentsystem.settings import Settings, get_settings

logger = logging.getLogger("agentsystem.health")


@dataclass(slots=True)
class DependencyStatus:
    name: str
    healthy: bool
    required: bool
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "healthy": self.healthy,
            "required": self.required,
            "detail": self.detail,
        }


@dataclass(slots=True)
class HealthReport:
    ready: bool
    dependencies: list[DependencyStatus] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ready": self.ready,
            "status": "ready" if self.ready else "degraded",
            "dependencies": {d.name: d.to_dict() for d in self.dependencies},
        }


async def _check_database() -> DependencyStatus:
    ok = await db_ping()
    return DependencyStatus(
        "database", ok, required=True,
        detail="" if ok else "connectivity check failed",
    )

def _check_database_config(settings: Settings) -> DependencyStatus:
    ok = settings.database_config_ready
    return DependencyStatus(
        "database_config",
        ok,
        required=settings.is_production,
        detail="" if ok else "production requires PostgreSQL DATABASE_URL",
    )

def _configuration_checks(settings: Settings) -> list[DependencyStatus]:
    checks = (
        ("redis_config", settings.redis_config_ready, "production requires Redis"),
        (
            "durable_config",
            settings.durable_config_ready,
            "production requires Durable Task Scheduler",
        ),
        (
            "artifact_config",
            settings.artifact_config_ready,
            "production requires Blob artifact storage",
        ),
        (
            "auth_config",
            settings.auth_config_ready,
            "production requires Entra or Easy Auth",
        ),
        (
            "sandbox_config",
            settings.sandbox_config_ready,
            "production requires Dynamic Sessions",
        ),
    )
    return [
        DependencyStatus(
            name,
            healthy,
            required=settings.is_production,
            detail="" if healthy else detail,
        )
        for name, healthy, detail in checks
    ]


async def _check_redis(settings: Settings) -> DependencyStatus:
    if not settings.redis_enabled:
        return DependencyStatus(
            "redis", True, required=False, detail="disabled"
        )
    try:
        ok = await get_rate_limiter().health()
    except Exception as exc:  # noqa: BLE001 - health must not raise
        logger.warning("Redis health probe error: %s", type(exc).__name__)
        ok = False
    return DependencyStatus(
        "redis", ok, required=True,
        detail="" if ok else "ping failed",
    )


async def _check_durable(settings: Settings) -> DependencyStatus:
    required = settings.durable_is_dts
    try:
        ok = await get_durable_executor().health()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Durable health probe error: %s", type(exc).__name__)
        ok = False
    return DependencyStatus(
        "durable_task", ok, required=required,
        detail="" if ok else "scheduler unavailable",
    )


async def _check_blob(settings: Settings) -> DependencyStatus:
    if not settings.artifact_is_blob:
        return DependencyStatus(
            "blob_artifacts", True, required=False, detail="local mode"
        )
    try:
        ok = await get_artifact_store().health()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Blob health probe error: %s", type(exc).__name__)
        ok = False
    return DependencyStatus(
        "blob_artifacts", ok, required=True,
        detail="" if ok else "container unavailable",
    )


async def _check_sandbox(settings: Settings) -> DependencyStatus:
    required = settings.sandbox_mode == "dynamic_sessions"
    interpreter = build_dynamic_sessions_interpreter(settings)
    if interpreter is None:
        return DependencyStatus(
            "dynamic_sessions",
            not required,
            required=required,
            detail="not configured" if required else "disabled",
        )
    try:
        ok = await interpreter.health()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Dynamic Sessions health probe error: %s", type(exc).__name__)
        ok = False
    return DependencyStatus(
        "dynamic_sessions",
        ok,
        required=required,
        detail="" if ok else "session pool unavailable",
    )


def _check_model(settings: Settings) -> DependencyStatus:
    ok = settings.model_config_ready
    return DependencyStatus(
        "model_config", ok, required=True,
        detail="" if ok else "no model credential configured",
    )


async def build_readiness_report() -> HealthReport:
    """Assemble a truthful readiness report across all dependencies."""
    settings = get_settings()
    deps = [
        _check_database_config(settings),
        *_configuration_checks(settings),
        await _check_database(),
        await _check_redis(settings),
        await _check_durable(settings),
        await _check_blob(settings),
        await _check_sandbox(settings),
        _check_model(settings),
    ]
    ready = all(d.healthy for d in deps if d.required)
    return HealthReport(ready=ready, dependencies=deps)


async def build_startup_report() -> HealthReport:
    """Startup gate: database must be reachable and the model configured.

    Redis/DTS/Blob may still be warming up; they are surfaced but only the
    database + model config block cold start so the process can bind and then
    converge to ready.
    """
    settings = get_settings()
    db_config = _check_database_config(settings)
    config = _configuration_checks(settings)
    db = await _check_database()
    model = _check_model(settings)
    deps = [db_config, *config, db, model]
    ready = all(d.healthy for d in deps if d.required)
    return HealthReport(ready=ready, dependencies=deps)


__all__ = [
    "DependencyStatus",
    "HealthReport",
    "build_readiness_report",
    "build_startup_report",
]
