"""Add Phase 4 chunking tables and tracking fields.

Revision ID: 20260817_0004
Revises: 20260808_0003
Create Date: 2026-08-17 10:30:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260817_0004"
down_revision = "20260808_0003"
branch_labels = None
depends_on = None


chunking_status_enum = postgresql.ENUM(
    "pending",
    "processing",
    "ready",
    "failed",
    name="chunking_status",
    create_type=False,
)

chunk_strategy_enum = postgresql.ENUM(
    "fixed_size",
    "sentence_based",
    "section_based",
    name="chunk_strategy",
    create_type=False,
)

chunk_status_enum = postgresql.ENUM(
    "ready",
    "archived",
    name="chunk_status",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()

    if bind.dialect.name == "postgresql":
        op.execute(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1
                    FROM pg_type
                    WHERE typname = 'chunking_status'
                ) THEN
                    CREATE TYPE chunking_status AS ENUM (
                        'pending',
                        'processing',
                        'ready',
                        'failed'
                    );
                END IF;

                IF NOT EXISTS (
                    SELECT 1
                    FROM pg_type
                    WHERE typname = 'chunk_strategy'
                ) THEN
                    CREATE TYPE chunk_strategy AS ENUM (
                        'fixed_size',
                        'sentence_based',
                        'section_based'
                    );
                END IF;

                IF NOT EXISTS (
                    SELECT 1
                    FROM pg_type
                    WHERE typname = 'chunk_status'
                ) THEN
                    CREATE TYPE chunk_status AS ENUM (
                        'ready',
                        'archived'
                    );
                END IF;
            END $$;
            """
        )

    chunking_status_type = (
        chunking_status_enum
        if bind.dialect.name == "postgresql"
        else sa.String(length=50)
    )

    chunk_strategy_type = (
        chunk_strategy_enum
        if bind.dialect.name == "postgresql"
        else sa.String(length=50)
    )

    chunk_status_type = (
        chunk_status_enum
        if bind.dialect.name == "postgresql"
        else sa.String(length=50)
    )

    # Add chunking tracking fields to documents
    op.add_column(
        "documents",
        sa.Column(
            "chunking_status",
            chunking_status_type,
            nullable=False,
            server_default="pending",
        ),
    )

    op.add_column(
        "documents",
        sa.Column(
            "chunking_error",
            sa.Text(),
            nullable=True,
        ),
    )

    op.add_column(
        "documents",
        sa.Column(
            "chunk_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )

    op.add_column(
        "documents",
        sa.Column(
            "chunking_started_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    op.add_column(
        "documents",
        sa.Column(
            "chunking_completed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    # Create document_chunks table
    op.create_table(
        "document_chunks",
        sa.Column(
            "id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "document_id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "strategy",
            chunk_strategy_type,
            nullable=False,
        ),
        sa.Column(
            "status",
            chunk_status_type,
            nullable=False,
            server_default="ready",
        ),
        sa.Column(
            "chunk_index",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "text",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "text_length",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "start_offset",
            sa.Integer(),
            nullable=True,
        ),
        sa.Column(
            "end_offset",
            sa.Integer(),
            nullable=True,
        ),
        sa.Column(
            "overlap_size",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "page_number",
            sa.Integer(),
            nullable=True,
        ),
        sa.Column(
            "section_title",
            sa.String(length=255),
            nullable=True,
        ),
        sa.Column(
            "source_file_name",
            sa.String(length=255),
            nullable=False,
        ),
        sa.Column(
            "upload_date",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Indexes
    op.create_index(
        "ix_document_chunks_id",
        "document_chunks",
        ["id"],
        unique=False,
    )

    op.create_index(
        "ix_document_chunks_document_id",
        "document_chunks",
        ["document_id"],
        unique=False,
    )

    # Remove temporary server defaults after creation
    op.alter_column(
        "documents",
        "chunking_status",
        server_default=None,
    )

    op.alter_column(
        "documents",
        "chunk_count",
        server_default=None,
    )

    op.alter_column(
        "document_chunks",
        "status",
        server_default=None,
    )

    op.alter_column(
        "document_chunks",
        "overlap_size",
        server_default=None,
    )


def downgrade() -> None:
    bind = op.get_bind()

    # Drop indexes
    op.drop_index(
        "ix_document_chunks_document_id",
        table_name="document_chunks",
    )

    op.drop_index(
        "ix_document_chunks_id",
        table_name="document_chunks",
    )

    # Drop chunks table
    op.drop_table("document_chunks")

    # Remove document chunking fields
    op.drop_column(
        "documents",
        "chunking_completed_at",
    )

    op.drop_column(
        "documents",
        "chunking_started_at",
    )

    op.drop_column(
        "documents",
        "chunk_count",
    )

    op.drop_column(
        "documents",
        "chunking_error",
    )

    op.drop_column(
        "documents",
        "chunking_status",
    )

    # Remove PostgreSQL enum types
    if bind.dialect.name == "postgresql":
        op.execute("DROP TYPE IF EXISTS chunk_status")
        op.execute("DROP TYPE IF EXISTS chunk_strategy")
        op.execute("DROP TYPE IF EXISTS chunking_status")