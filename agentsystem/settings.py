"""Explicit, fail-closed backend settings.

This module centralizes configuration for the durable backend: database, Redis,
Durable Task Scheduler, Blob artifact store, identity/auth mode, and environment
classification. It is deliberately separate from the legacy :mod:`config`
package so existing agent/tool behavior is untouched.

Design rules:

* **Explicit modes.** Every adapter has a ``*_MODE`` selecting a concrete
  backend. There is no implicit "try cloud, silently fall back to local".
* **Fail closed in production.** When ``APP_ENV=production`` and a selected
  cloud backend is not configured, readiness/startup must fail rather than
  degrade to a local stand-in.
* **Dev/test friendly.** Defaults resolve to SQLite + in-memory + local-file so
  the test suite needs no external services.
"""

from __future__ import annotations

import functools
import os
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

_TRUTHY = {"1", "true", "yes", "on"}


def _env(name: str, default: str = "") -> str:
    value = os.getenv(name, default)
    return value.strip() if value else default


def _bool(name: str, default: bool = False) -> bool:
    raw = _env(name, "true" if default else "false").lower()
    return raw in _TRUTHY


def _int(name: str, default: int) -> int:
    try:
        return int(_env(name, str(default)) or default)
    except (TypeError, ValueError):
        return default


def _running_in_container() -> bool:
    """Best-effort detection of a container / cloud runtime.

    Used only to HARDEN the sandbox default (never to relax it). Any positive
    signal means "treat host subprocess execution as forbidden".
    """
    if _bool("AGENTSYSTEM_IN_CONTAINER", False):
        return True
    # Azure Container Apps / Kubernetes inject these.
    for marker in ("CONTAINER_APP_NAME", "KUBERNETES_SERVICE_HOST", "K_SERVICE"):
        if os.getenv(marker):
            return True
    # The canonical Docker marker file.
    try:
        if Path("/.dockerenv").exists():
            return True
    except OSError:  # pragma: no cover - platform dependent
        pass
    return False


@dataclass(frozen=True, slots=True)
class Settings:
    """Immutable snapshot of backend configuration."""

    # ── Environment ─────────────────────────────────────────────────────────
    environment: str  # local | staging | production
    app_version: str
    revision: str

    # ── Database ────────────────────────────────────────────────────────────
    database_url: str
    database_use_entra: bool
    database_echo: bool

    # ── Redis ───────────────────────────────────────────────────────────────
    redis_enabled: bool
    redis_url: str
    redis_use_entra: bool
    redis_username: str
    redis_tls: bool
    redis_scope: str

    # ── Durable Task Scheduler ──────────────────────────────────────────────
    durable_mode: str  # local | dts
    durable_endpoint: str
    durable_taskhub: str

    # ── Blob artifact store ─────────────────────────────────────────────────
    artifact_mode: str  # local | blob
    artifact_local_root: str
    blob_account_url: str
    blob_container: str

    # ── Identity / auth ─────────────────────────────────────────────────────
    auth_mode: str  # easy_auth | entra_jwt | api_key | disabled
    easy_auth_enabled: bool
    entra_tenant_id: str
    entra_audience: str
    entra_authority: str
    api_key: str

    # ── Sandbox ─────────────────────────────────────────────────────────────
    sandbox_mode: str  # auto | dynamic_sessions | docker | subprocess | off
    dynamic_sessions_endpoint: str
    in_container: bool

    # ── Rate limiting ───────────────────────────────────────────────────────
    rate_limit_enabled: bool
    rate_limit_requests: int
    rate_limit_window: int

    # ── Derived predicates ──────────────────────────────────────────────────
    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @property
    def database_config_ready(self) -> bool:
        """Production requires explicit shared PostgreSQL durability."""
        return not self.is_production or self.database_url.startswith(
            "postgresql+asyncpg://"
        )

    @property
    def durable_is_dts(self) -> bool:
        return self.durable_mode == "dts"

    @property
    def redis_config_ready(self) -> bool:
        return not self.is_production or (
            self.redis_enabled and bool(self.redis_url)
        )

    @property
    def durable_config_ready(self) -> bool:
        return not self.is_production or (
            self.durable_is_dts and bool(self.durable_endpoint)
        )

    @property
    def artifact_is_blob(self) -> bool:
        return self.artifact_mode == "blob"

    @property
    def artifact_config_ready(self) -> bool:
        return not self.is_production or (
            self.artifact_is_blob and bool(self.blob_account_url)
        )

    @property
    def auth_config_ready(self) -> bool:
        return not self.is_production or self.auth_mode in {
            "easy_auth",
            "entra_jwt",
        }

    @property
    def sandbox_config_ready(self) -> bool:
        return not self.is_production or (
            self.sandbox_mode == "dynamic_sessions"
            and bool(self.dynamic_sessions_endpoint)
        )

    @property
    def model_config_ready(self) -> bool:
        """Whether a model credential (Entra or key) is configured.

        Readiness must NOT issue a live model request on every probe, so this
        only checks that configuration exists. Managed-identity deployments set
        ``AZURE_OPENAI_ENDPOINT`` plus ``AZURE_OPENAI_USE_ENTRA=true``; a
        key-based/local deployment sets ``AZURE_OPENAI_API_KEY`` or
        ``OPENAI_API_KEY``.
        """
        endpoint = _env("AZURE_OPENAI_ENDPOINT")
        if (
            endpoint
            and not endpoint.startswith("<")
            and _bool("AZURE_OPENAI_USE_ENTRA", False)
        ):
            return True
        for key in ("AZURE_OPENAI_API_KEY", "OPENAI_API_KEY"):
            val = _env(key)
            if val and not val.startswith("<"):
                return True
        return False


def _default_database_url(environment: str) -> str:
    """Resolve the default DB URL.

    Production may still import with the local default, but startup/readiness
    explicitly reject it. This permits configuration inspection without ever
    reporting a production replica ready on ephemeral SQLite.
    """
    explicit = _env("DATABASE_URL")
    if explicit:
        return _normalize_async_url(explicit)
    default_path = PROJECT_ROOT / "memory" / "agentsystem.db"
    return f"sqlite+aiosqlite:///{default_path.as_posix()}"


def _normalize_async_url(url: str) -> str:
    """Ensure a URL uses an async driver SQLAlchemy can open.

    ``postgresql://`` → ``postgresql+asyncpg://``; ``sqlite://`` →
    ``sqlite+aiosqlite://``. Already-async URLs pass through unchanged.
    """
    if url.startswith("postgresql+"):
        return url
    if url.startswith("postgres://"):
        return "postgresql+asyncpg://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        return "postgresql+asyncpg://" + url[len("postgresql://"):]
    if url.startswith("sqlite+"):
        return url
    if url.startswith("sqlite://"):
        return "sqlite+aiosqlite://" + url[len("sqlite://"):]
    return url


@functools.lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Load and cache backend settings from the environment.

    Cached for process lifetime; tests clear it via :func:`reset_settings_cache`.
    """
    environment = _env("APP_ENV", _env("ENVIRONMENT", "local")).lower() or "local"
    in_container = _running_in_container()

    # Auth mode defaults: prefer Easy Auth when its marker is set, otherwise
    # fall back to key/disabled. Production never runs unauthenticated.
    easy_auth_enabled = _bool("EASY_AUTH_ENABLED", False)
    explicit_auth_mode = _env("AUTH_MODE").lower()
    if explicit_auth_mode:
        auth_mode = explicit_auth_mode
    elif easy_auth_enabled:
        auth_mode = "easy_auth"
    elif _env("ENTRA_TENANT_ID") and _env("ENTRA_AUDIENCE"):
        auth_mode = "entra_jwt"
    elif _env("AGENTSYSTEM_API_KEY"):
        auth_mode = "api_key"
    else:
        auth_mode = "disabled"

    entra_tenant = _env("ENTRA_TENANT_ID") or _env("AZURE_TENANT_ID")
    authority = _env(
        "ENTRA_AUTHORITY",
        f"https://login.microsoftonline.com/{entra_tenant}" if entra_tenant else "",
    )

    return Settings(
        environment=environment,
        app_version=_env("APP_VERSION", "0.0.0"),
        revision=_env("CONTAINER_APP_REVISION", _env("GIT_SHA", "unknown")),
        database_url=_default_database_url(environment),
        database_use_entra=_bool("DATABASE_USE_ENTRA", False),
        database_echo=_bool("DATABASE_ECHO", False),
        redis_enabled=_bool("REDIS_ENABLED", False),
        redis_url=_env("REDIS_URL"),
        redis_use_entra=_bool("REDIS_USE_ENTRA", False),
        redis_username=_env("REDIS_USERNAME"),
        redis_tls=_bool("REDIS_TLS", True),
        redis_scope=_env("REDIS_ENTRA_SCOPE", "https://redis.azure.com/.default"),
        durable_mode=(_env("DURABLE_MODE", "local").lower() or "local"),
        durable_endpoint=_env("DURABLE_TASK_ENDPOINT"),
        durable_taskhub=_env("DURABLE_TASK_HUB", "agentsystem"),
        artifact_mode=(_env("ARTIFACT_MODE", "local").lower() or "local"),
        artifact_local_root=_env(
            "ARTIFACT_LOCAL_ROOT",
            str(PROJECT_ROOT / "memory" / "artifacts"),
        ),
        blob_account_url=_env("BLOB_ACCOUNT_URL"),
        blob_container=_env("BLOB_CONTAINER", "artifacts"),
        auth_mode=auth_mode,
        easy_auth_enabled=easy_auth_enabled,
        entra_tenant_id=entra_tenant,
        entra_audience=_env("ENTRA_AUDIENCE"),
        entra_authority=authority,
        api_key=_env("AGENTSYSTEM_API_KEY"),
        sandbox_mode=(_env("CODE_SANDBOX_MODE", "auto").lower() or "auto"),
        dynamic_sessions_endpoint=_env("DYNAMIC_SESSIONS_ENDPOINT"),
        in_container=in_container,
        rate_limit_enabled=_bool("RATE_LIMIT_ENABLED", True),
        rate_limit_requests=_int("RATE_LIMIT_REQUESTS", 60),
        rate_limit_window=_int("RATE_LIMIT_WINDOW", 60),
    )


def reset_settings_cache() -> None:
    """Clear the cached settings (tests mutate the environment between cases)."""
    get_settings.cache_clear()


__all__ = ["Settings", "get_settings", "reset_settings_cache"]
