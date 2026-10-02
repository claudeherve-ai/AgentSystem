"""Alembic migration environment.

The target metadata is :data:`agentsystem.db.base.Base.metadata` (all models).
The database URL is resolved from :func:`agentsystem.settings.get_settings` at
runtime — nothing is hardcoded and no secret is stored in ``alembic.ini``.

Supports both offline (SQL script) and online (async engine) migration runs, so
the same migrations apply to SQLite (dev/test) and PostgreSQL (production).
"""

from __future__ import annotations

import asyncio
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
# Ensure the project root is importable when Alembic runs from the repo root.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from agentsystem.db.base import Base  # noqa: E402
from agentsystem.db import models  # noqa: E402,F401  (import registers models)
from agentsystem.db.session import build_engine  # noqa: E402
from agentsystem.settings import get_settings  # noqa: E402

config = context.config

if config.config_file_name is not None:
    try:
        fileConfig(config.config_file_name)
    except Exception:  # noqa: BLE001 - logging config is best-effort
        pass

target_metadata = Base.metadata


def _database_url() -> str:
    return get_settings().database_url


def run_migrations_offline() -> None:
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def _do_run_migrations(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    engine = build_engine(get_settings())
    async with engine.connect() as connection:
        await connection.run_sync(_do_run_migrations)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
