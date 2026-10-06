"""Add active-user tracking for immediate access revocation.

Revision ID: 20261005_0007
Revises: 20260831_0006
Create Date: 2026-10-05 10:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20261005_0007"
down_revision = "20260831_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.alter_column("users", "is_active", server_default=None)


def downgrade() -> None:
    op.drop_column("users", "is_active")
