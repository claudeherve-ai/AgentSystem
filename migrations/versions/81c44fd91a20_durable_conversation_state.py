"""persist durable agent conversation state

Revision ID: 81c44fd91a20
Revises: 6f3c2b8a9d11
Create Date: 2026-09-01 00:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "81c44fd91a20"
down_revision: Union[str, None] = "6f3c2b8a9d11"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("sessions", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "agent_state",
                sa.JSON(),
                nullable=False,
                server_default=sa.text("'{}'"),
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("sessions", schema=None) as batch_op:
        batch_op.drop_column("agent_state")
