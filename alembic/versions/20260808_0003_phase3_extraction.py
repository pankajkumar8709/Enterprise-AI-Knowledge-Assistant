"""Add Phase 3 extraction fields.

Revision ID: 20260808_0003
Revises: 20260807_0002
Create Date: 2026-08-08 00:03:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260808_0003"
down_revision = "20260807_0002"
branch_labels = None
depends_on = None


extraction_status_enum = sa.Enum(
    "pending",
    "processing",
    "ready",
    "failed",
    name="extraction_status",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()

    if bind.dialect.name == "postgresql":
        op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_type
                WHERE typname = 'extraction_status'
            ) THEN
                CREATE TYPE extraction_status AS ENUM (
                    'pending',
                    'processing',
                    'ready',
                    'failed'
                );
            END IF;
        END$$;
        """)

    status_type = extraction_status_enum if bind.dialect.name == "postgresql" else sa.String(length=50)

    op.add_column(
        "documents",
        sa.Column("extraction_status", status_type, nullable=False, server_default="pending"),
    )
    op.add_column("documents", sa.Column("extraction_raw_text_path", sa.String(length=500), nullable=True))
    op.add_column("documents", sa.Column("extraction_clean_text_path", sa.String(length=500), nullable=True))
    op.add_column("documents", sa.Column("extraction_error", sa.Text(), nullable=True))
    op.add_column(
        "documents",
        sa.Column("extraction_ocr_used", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("documents", sa.Column("extracted_char_count", sa.Integer(), nullable=True))
    op.add_column("documents", sa.Column("extraction_started_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("documents", sa.Column("extraction_completed_at", sa.DateTime(timezone=True), nullable=True))

    op.alter_column("documents", "extraction_status", server_default=None)
    op.alter_column("documents", "extraction_ocr_used", server_default=None)


def downgrade() -> None:
    bind = op.get_bind()

    op.drop_column("documents", "extraction_completed_at")
    op.drop_column("documents", "extraction_started_at")
    op.drop_column("documents", "extracted_char_count")
    op.drop_column("documents", "extraction_ocr_used")
    op.drop_column("documents", "extraction_error")
    op.drop_column("documents", "extraction_clean_text_path")
    op.drop_column("documents", "extraction_raw_text_path")
    op.drop_column("documents", "extraction_status")

    if bind.dialect.name == "postgresql":
        op.execute("""
        DROP TYPE IF EXISTS extraction_status
        """)
