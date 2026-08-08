"""Expand documents table for Phase 2 document management.

Revision ID: 20260807_0002
Revises: 20260727_0001
Create Date: 2026-08-07 00:02:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260807_0002"
down_revision = "20260727_0001"
branch_labels = None
depends_on = None


document_status_enum = sa.Enum(
    "uploaded",
    "processing",
    "ready",
    "failed",
    name="document_status",
    create_type=False,
)


def upgrade() -> None:
    # Create enum type if it doesn't exist
    op.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1
            FROM pg_type
            WHERE typname = 'document_status'
        ) THEN
            CREATE TYPE document_status AS ENUM (
                'uploaded',
                'processing',
                'ready',
                'failed'
            );
        END IF;
    END$$;
    """)

    # ---------------------------
    # Add new columns
    # ---------------------------
    op.add_column(
        "documents",
        sa.Column("stored_name", sa.String(255), nullable=True),
    )

    op.add_column(
        "documents",
        sa.Column("content_type", sa.String(255), nullable=True),
    )

    op.add_column(
        "documents",
        sa.Column("size_bytes", sa.Integer(), nullable=True),
    )

    op.add_column(
        "documents",
        sa.Column("storage_path", sa.String(500), nullable=True),
    )

    op.add_column(
        "documents",
        sa.Column(
            "version",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
    )

    # ---------------------------
    # Populate existing rows
    # ---------------------------
    op.execute("""
        UPDATE documents
        SET stored_name = source_name
        WHERE stored_name IS NULL
    """)

    op.execute("""
        UPDATE documents
        SET content_type = 'application/octet-stream'
        WHERE content_type IS NULL
    """)

    op.execute("""
        UPDATE documents
        SET size_bytes = 0
        WHERE size_bytes IS NULL
    """)

    op.execute("""
        UPDATE documents
        SET storage_path = ''
        WHERE storage_path IS NULL
    """)

    # ---------------------------
    # Make columns NOT NULL
    # ---------------------------
    op.alter_column("documents", "stored_name", nullable=False)
    op.alter_column("documents", "content_type", nullable=False)
    op.alter_column("documents", "size_bytes", nullable=False)
    op.alter_column("documents", "storage_path", nullable=False)

    # ---------------------------
    # Convert status column
    # ---------------------------

    # Remove old varchar default
    op.execute("""
        ALTER TABLE documents
        ALTER COLUMN status DROP DEFAULT
    """)

    # Normalize existing data
    op.execute("""
        UPDATE documents
        SET status = LOWER(status)
    """)

    # Convert VARCHAR -> ENUM
    op.alter_column(
        "documents",
        "status",
        existing_type=sa.String(length=50),
        type_=document_status_enum,
        existing_nullable=False,
        postgresql_using="LOWER(status)::document_status",
    )

    # Add enum default
    op.execute("""
        ALTER TABLE documents
        ALTER COLUMN status
        SET DEFAULT 'uploaded'::document_status
    """)

    # Remove temporary default from version
    op.alter_column(
        "documents",
        "version",
        server_default=None,
    )


def downgrade() -> None:
    # Remove enum default
    op.execute("""
        ALTER TABLE documents
        ALTER COLUMN status DROP DEFAULT
    """)

    # Convert ENUM -> VARCHAR
    op.alter_column(
        "documents",
        "status",
        existing_type=document_status_enum,
        type_=sa.String(length=50),
        existing_nullable=False,
        postgresql_using="status::text",
    )

    op.drop_column("documents", "version")
    op.drop_column("documents", "storage_path")
    op.drop_column("documents", "size_bytes")
    op.drop_column("documents", "content_type")
    op.drop_column("documents", "stored_name")

    op.execute("""
        DROP TYPE IF EXISTS document_status
    """)