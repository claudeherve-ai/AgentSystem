"""SQLAlchemy 2 declarative base and shared column mixins.

A stable naming convention is applied so Alembic autogenerate produces
deterministic constraint names across SQLite (dev/test) and PostgreSQL (prod).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, MetaData, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


def utcnow() -> datetime:
    """Timezone-aware UTC now (used as the Python-side default for timestamps)."""
    return datetime.now(timezone.utc)


def new_uuid() -> str:
    return uuid.uuid4().hex


class Base(DeclarativeBase):
    """Declarative base with a shared metadata + naming convention."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class TimestampMixin:
    """Adds ``created_at`` / ``updated_at`` columns."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class UUIDPkMixin:
    """Adds a string UUID primary key."""

    id: Mapped[str] = mapped_column(
        String(32), primary_key=True, default=new_uuid
    )


__all__ = ["Base", "TimestampMixin", "UUIDPkMixin", "new_uuid", "utcnow"]
