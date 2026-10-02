"""Async SQLAlchemy engine and session management.

Supports two explicit modes:

* **SQLite (dev/test).** Default. Zero external services; the test suite runs
  entirely against a local file or a shared in-memory database.
* **PostgreSQL (production).** ``DATABASE_URL`` points at PostgreSQL; when
  ``DATABASE_USE_ENTRA=true`` the connection password is a freshly-minted
  Microsoft Entra access token (managed identity), refreshed per connection.

The engine and sessionmaker are process-cached. Async clients created for Entra
token acquisition are closed after use.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from agentsystem.db.base import Base
from agentsystem.settings import Settings, get_settings

logger = logging.getLogger("agentsystem.db")

# PostgreSQL Entra token scope (Azure Database for PostgreSQL — Entra auth).
_PG_ENTRA_SCOPE = "https://ossrdbms-aad.database.windows.net/.default"

_engine: Optional[AsyncEngine] = None
_sessionmaker: Optional[async_sessionmaker[AsyncSession]] = None


def _enable_sqlite_fks(engine: AsyncEngine) -> None:
    """Turn on ``PRAGMA foreign_keys`` for every SQLite connection."""

    @event.listens_for(engine.sync_engine, "connect")
    def _set_pragma(dbapi_connection, _record):  # pragma: no cover - trivial
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys=ON;")
        finally:
            cursor.close()


async def _entra_token_provider() -> str:
    """Fetch a PostgreSQL Entra access token via managed identity.

    Uses ``DefaultAzureCredential`` so the same code works locally (developer
    login) and in Azure (managed identity). The async credential is always
    closed. Raises on failure — callers must fail closed, never fall back to a
    password we do not have.
    """
    from azure.identity.aio import DefaultAzureCredential

    credential = DefaultAzureCredential()
    try:
        token = await credential.get_token(_PG_ENTRA_SCOPE)
        return token.token
    finally:
        await credential.close()


def build_engine(settings: Optional[Settings] = None) -> AsyncEngine:
    """Create an :class:`AsyncEngine` for the configured database URL."""
    settings = settings or get_settings()
    url = settings.database_url
    kwargs: dict = {"echo": settings.database_echo, "future": True}

    if url.startswith("sqlite"):
        # A shared in-memory DB needs a StaticPool so every session sees the
        # same tables; file-based SQLite uses the default pool.
        if ":memory:" in url or "mode=memory" in url:
            kwargs["poolclass"] = StaticPool
            kwargs["connect_args"] = {"check_same_thread": False}
        engine = create_async_engine(url, **kwargs)
        _enable_sqlite_fks(engine)
        return engine

    if settings.database_use_entra:
        # Inject a fresh Entra token as the connection password. asyncpg reads
        # ``password`` from connect args; we refresh it on each new connection.
        async def _provide_token(*_args, **_kwargs):
            return await _entra_token_provider()

        kwargs["connect_args"] = {"password": _provide_token}
    engine = create_async_engine(url, **kwargs)
    return engine


def get_engine() -> AsyncEngine:
    """Return the process-cached engine, creating it on first use."""
    global _engine
    if _engine is None:
        _engine = build_engine()
    return _engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    """Return the process-cached async sessionmaker."""
    global _sessionmaker
    if _sessionmaker is None:
        _sessionmaker = async_sessionmaker(
            get_engine(), expire_on_commit=False, class_=AsyncSession
        )
    return _sessionmaker


def configure_engine(engine: AsyncEngine) -> None:
    """Install an explicit engine + sessionmaker (used by tests)."""
    global _engine, _sessionmaker
    _engine = engine
    _sessionmaker = async_sessionmaker(
        engine, expire_on_commit=False, class_=AsyncSession
    )


async def reset_engine() -> None:
    """Dispose and clear the cached engine (tests / graceful shutdown)."""
    global _engine, _sessionmaker
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _sessionmaker = None


async def init_models(engine: Optional[AsyncEngine] = None) -> None:
    """Create all tables. Used for SQLite dev/test bootstrap.

    Production schema is owned by Alembic migrations; this is a convenience for
    ephemeral SQLite databases.
    """
    engine = engine or get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """Yield a transactional :class:`AsyncSession`.

    Commits on clean exit, rolls back on exception, and always closes.
    """
    maker = get_sessionmaker()
    session = maker()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


async def ping() -> bool:
    """Lightweight connectivity check for readiness probes.

    Returns ``True`` when a trivial ``SELECT 1`` succeeds. Never raises — a
    failure returns ``False`` so the caller can render a truthful health status.
    """
    from sqlalchemy import text

    try:
        async with session_scope() as session:
            await session.execute(text("SELECT 1"))
        return True
    except Exception as exc:  # noqa: BLE001 - health check must not raise
        logger.warning("Database ping failed: %s", type(exc).__name__)
        return False


__all__ = [
    "build_engine",
    "configure_engine",
    "get_engine",
    "get_sessionmaker",
    "init_models",
    "ping",
    "reset_engine",
    "session_scope",
]
