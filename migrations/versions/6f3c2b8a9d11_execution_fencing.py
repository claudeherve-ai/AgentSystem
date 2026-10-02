"""add execution fencing and provisioning uniqueness

Revision ID: 6f3c2b8a9d11
Revises: 0507355081ee
Create Date: 2026-09-01 00:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "6f3c2b8a9d11"
down_revision: Union[str, None] = "0507355081ee"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("workspaces", schema=None) as batch_op:
        batch_op.create_unique_constraint(
            "workspaces_tenant_name", ["tenant_id", "name"]
        )

    with op.batch_alter_table("projects", schema=None) as batch_op:
        batch_op.create_unique_constraint(
            "projects_workspace_name", ["tenant_id", "workspace_id", "name"]
        )

    with op.batch_alter_table("runs", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("execution_token", sa.String(length=64), nullable=True)
        )
        batch_op.create_index(
            batch_op.f("ix_runs_execution_token"),
            ["execution_token"],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("runs", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_runs_execution_token"))
        batch_op.drop_column("execution_token")

    with op.batch_alter_table("projects", schema=None) as batch_op:
        batch_op.drop_constraint("projects_workspace_name", type_="unique")

    with op.batch_alter_table("workspaces", schema=None) as batch_op:
        batch_op.drop_constraint("workspaces_tenant_name", type_="unique")
