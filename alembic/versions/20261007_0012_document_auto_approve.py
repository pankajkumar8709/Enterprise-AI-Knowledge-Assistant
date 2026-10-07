"""per-document trusted source flag: auto-approve extracted knowledge

Revision ID: 20261007_0012
Revises: 20261006_0011
Create Date: 2026-10-07
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20261007_0012"
down_revision = "20261006_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column("auto_approve_knowledge", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.alter_column("documents", "auto_approve_knowledge", server_default=None)


def downgrade() -> None:
    op.drop_column("documents", "auto_approve_knowledge")
