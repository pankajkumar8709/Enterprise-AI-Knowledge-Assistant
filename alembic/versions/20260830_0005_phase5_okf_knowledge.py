"""Add Phase 5 OKF knowledge extraction fields.

Revision ID: 20260830_0005
Revises: 20260817_0004
Create Date: 2026-08-30 18:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260830_0005"
down_revision = "20260817_0004"
branch_labels = None
depends_on = None


knowledge_object_type_enum = postgresql.ENUM(
    "policy",
    "employee",
    "department",
    "product",
    "faq",
    "business_rule",
    "asset",
    name="knowledge_object_type",
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
                    WHERE typname = 'knowledge_object_type'
                ) THEN
                    CREATE TYPE knowledge_object_type AS ENUM (
                        'policy',
                        'employee',
                        'department',
                        'product',
                        'faq',
                        'business_rule',
                        'asset'
                    );
                END IF;
            END $$;
            """
        )

    object_type_type = knowledge_object_type_enum if bind.dialect.name == "postgresql" else sa.String(length=100)

    op.add_column(
        "knowledge_objects",
        sa.Column("object_key", sa.String(length=160), nullable=True),
    )
    op.add_column(
        "knowledge_objects",
        sa.Column("relations", sa.Text(), nullable=False, server_default="[]"),
    )
    op.add_column(
        "knowledge_objects",
        sa.Column("summary", sa.Text(), nullable=True),
    )
    op.add_column(
        "knowledge_objects",
        sa.Column("source_excerpt", sa.Text(), nullable=True),
    )
    op.add_column(
        "knowledge_objects",
        sa.Column("schema_version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "knowledge_objects",
        sa.Column("object_version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "knowledge_objects",
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "knowledge_objects",
        sa.Column("extraction_method", sa.String(length=80), nullable=False, server_default="manual"),
    )

    op.execute(
        """
        UPDATE knowledge_objects
        SET object_key = LOWER(REPLACE(object_type, ' ', '_')) || ':' || LOWER(REPLACE(REPLACE(name, ' ', '-'), '/', '-'))
        WHERE object_key IS NULL
        """
    )

    if bind.dialect.name == "postgresql":
        op.execute(
            """
            ALTER TABLE knowledge_objects
            ALTER COLUMN object_type TYPE knowledge_object_type
            USING LOWER(REPLACE(object_type, ' ', '_'))::knowledge_object_type
            """
        )

    op.alter_column("knowledge_objects", "object_key", nullable=False)
    op.create_index("ix_knowledge_objects_object_key", "knowledge_objects", ["object_key"], unique=False)

    op.alter_column("knowledge_objects", "relations", server_default=None)
    op.alter_column("knowledge_objects", "schema_version", server_default=None)
    op.alter_column("knowledge_objects", "object_version", server_default=None)
    op.alter_column("knowledge_objects", "is_current", server_default=None)
    op.alter_column("knowledge_objects", "extraction_method", server_default=None)


def downgrade() -> None:
    bind = op.get_bind()

    op.drop_index("ix_knowledge_objects_object_key", table_name="knowledge_objects")
    op.drop_column("knowledge_objects", "extraction_method")
    op.drop_column("knowledge_objects", "is_current")
    op.drop_column("knowledge_objects", "object_version")
    op.drop_column("knowledge_objects", "schema_version")
    op.drop_column("knowledge_objects", "source_excerpt")
    op.drop_column("knowledge_objects", "summary")
    op.drop_column("knowledge_objects", "relations")
    op.drop_column("knowledge_objects", "object_key")

    if bind.dialect.name == "postgresql":
        op.execute(
            """
            ALTER TABLE knowledge_objects
            ALTER COLUMN object_type TYPE VARCHAR(100)
            USING object_type::text
            """
        )
        op.execute("DROP TYPE IF EXISTS knowledge_object_type")
