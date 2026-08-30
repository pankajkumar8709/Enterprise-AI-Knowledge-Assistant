"""Add cascade delete to knowledge object document reference.

Revision ID: 20260831_0006
Revises: fee7833cf1d3
Create Date: 2026-08-31 01:50:00
"""

from alembic import op


revision = "20260831_0006"
down_revision = "fee7833cf1d3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        "fk_knowledge_objects_source_document_id_documents",
        "knowledge_objects",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "fk_knowledge_objects_source_document_id_documents",
        "knowledge_objects",
        "documents",
        ["source_document_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_knowledge_objects_source_document_id_documents",
        "knowledge_objects",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "fk_knowledge_objects_source_document_id_documents",
        "knowledge_objects",
        "documents",
        ["source_document_id"],
        ["id"],
    )
