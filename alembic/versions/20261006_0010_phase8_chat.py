"""phase8_chat_tables

Revision ID: 20261006_0010
Revises: 20261005_0009
Create Date: 2026-10-06
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20261006_0010"
down_revision = "20261005_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "conversations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("title", sa.String(255), nullable=True),
        sa.Column("archived", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    # `index=True` on user_id already emits ix_conversations_user_id; a second
    # op.create_index() of the same name fails with DuplicateTable. Primary keys get
    # their index explicitly, matching the convention in migration 0001.
    op.create_index("ix_conversations_id", "conversations", ["id"], unique=False)

    # Enums (PostgreSQL only; SQLite ignores)
    message_role = sa.Enum("user", "assistant", name="message_role")
    chat_route = sa.Enum("structured", "document", "mixed", name="chat_route")

    op.create_table(
        "messages",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "conversation_id",
            sa.Integer(),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("role", message_role, nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("route", chat_route, nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("confidence_label", sa.String(20), nullable=True),
        sa.Column("answerable", sa.Boolean(), nullable=True),
        sa.Column("rewritten_query", sa.Text(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("token_in", sa.Integer(), nullable=True),
        sa.Column("token_out", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    # ix_messages_conversation_id is created by the column's index=True.
    op.create_index("ix_messages_id", "messages", ["id"], unique=False)

    op.create_table(
        "message_sources",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "message_id",
            sa.Integer(),
            sa.ForeignKey("messages.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("ref", sa.String(10), nullable=False),
        sa.Column("kind", sa.String(10), nullable=False),
        sa.Column(
            "chunk_id",
            sa.Integer(),
            sa.ForeignKey("document_chunks.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "okf_object_id",
            sa.Integer(),
            sa.ForeignKey("knowledge_objects.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "document_id",
            sa.Integer(),
            sa.ForeignKey("documents.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("snippet", sa.Text(), nullable=True),
        sa.Column("cited", sa.Boolean(), nullable=False, server_default="false"),
        # Model uses JSON_TYPE (JSONB on PostgreSQL) with a Python-side default=dict
        # and no server default, so none is set here either.
        sa.Column("extra", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    # ix_message_sources_message_id is created by the column's index=True.
    op.create_index("ix_message_sources_id", "message_sources", ["id"], unique=False)


def downgrade() -> None:
    op.drop_table("message_sources")
    op.drop_table("messages")
    op.drop_table("conversations")
    # Drop enums on PostgreSQL
    sa.Enum(name="chat_route").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="message_role").drop(op.get_bind(), checkfirst=True)
