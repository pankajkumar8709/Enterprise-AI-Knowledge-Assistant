"""mark the environment-managed bootstrap administrator

Revision ID: 20261006_0011
Revises: 20261006_0010
Create Date: 2026-10-06
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20261006_0011"
down_revision = "20261006_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("is_bootstrap_admin", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.alter_column("users", "is_bootstrap_admin", server_default=None)


def downgrade() -> None:
    op.drop_column("users", "is_bootstrap_admin")
