"""Phase 5.5 enabling changes: refresh tokens, ingestion jobs, document versions,
OKF sources/relations/versions, chunk embedding+tsv+version, OKF search/validity.

Revision ID: 20261005_0009
Revises: 20261005_0008
Create Date: 2026-10-05
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20261005_0009"
down_revision = "20261005_0008"
branch_labels = None
depends_on = None

knowledge_status_enum = postgresql.ENUM(
    "pending_review", "approved", "rejected", "archived",
    name="knowledge_status", create_type=False,
)
jsonb = postgresql.JSONB()


def _is_postgresql() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    if _is_postgresql():
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
        op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
        op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    # --- refresh_tokens (spec §5; rotation in §8/§11) ---
    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_refresh_tokens_token_hash"),
    )
    op.create_index("ix_refresh_tokens_id", "refresh_tokens", ["id"])
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])

    # --- ingestion_jobs (spec §5; executor = background tasks until Celery) ---
    if _is_postgresql():
        op.execute(
            "DO $$ BEGIN CREATE TYPE ingestion_job_status AS ENUM "
            "('queued','running','succeeded','failed'); "
            "EXCEPTION WHEN duplicate_object THEN NULL; END $$;"
        )
    op.create_table(
        "ingestion_jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("celery_task_id", sa.String(length=64), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(
                "queued", "running", "succeeded", "failed",
                name="ingestion_job_status", create_type=False,
            ) if _is_postgresql() else sa.String(length=20),
            nullable=False,
            server_default=sa.text("'queued'"),
        ),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ingestion_jobs_id", "ingestion_jobs", ["id"])
    op.create_index("ix_ingestion_jobs_document_id", "ingestion_jobs", ["document_id"])

    # --- document_versions (spec §5) ---
    op.create_table(
        "document_versions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("storage_path", sa.String(length=500), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("uploaded_by_id", sa.Integer(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["uploaded_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", "version", name="uq_document_versions_document_version"),
    )
    op.create_index("ix_document_versions_id", "document_versions", ["id"])
    op.create_index("ix_document_versions_document_id", "document_versions", ["document_id"])

    # --- okf_sources (spec §5/§6.1: verbatim quote evidence) ---
    op.create_table(
        "okf_sources",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("okf_object_id", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=True),
        sa.Column("chunk_id", sa.Integer(), nullable=True),
        sa.Column("page", sa.Integer(), nullable=True),
        sa.Column("quote", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["okf_object_id"], ["knowledge_objects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["chunk_id"], ["document_chunks.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_okf_sources_id", "okf_sources", ["id"])
    op.create_index("ix_okf_sources_okf_object_id", "okf_sources", ["okf_object_id"])
    op.create_index("ix_okf_sources_document_id", "okf_sources", ["document_id"])

    # --- okf_relations (spec §5/§6.2; closed predicate list) ---
    op.create_table(
        "okf_relations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("subject_id", sa.Integer(), nullable=False),
        sa.Column("predicate", sa.String(length=40), nullable=False),
        sa.Column("object_id", sa.Integer(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column(
            "status",
            knowledge_status_enum if _is_postgresql() else sa.String(length=20),
            nullable=False,
            server_default=sa.text("'pending_review'"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["subject_id"], ["knowledge_objects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["object_id"], ["knowledge_objects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("subject_id", "predicate", "object_id", name="uq_okf_relations_subject_predicate_object"),
    )
    op.create_index("ix_okf_relations_id", "okf_relations", ["id"])
    op.create_index("ix_okf_relations_subject_id", "okf_relations", ["subject_id"])
    op.create_index("ix_okf_relations_object_id", "okf_relations", ["object_id"])

    # --- okf_object_versions (spec §5/§6.3 snapshots) ---
    op.create_table(
        "okf_object_versions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("okf_object_id", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("snapshot", jsonb if _is_postgresql() else sa.JSON(), nullable=False),
        sa.Column("changed_by_id", sa.Integer(), nullable=True),
        sa.Column("change_note", sa.Text(), nullable=True),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["okf_object_id"], ["knowledge_objects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["changed_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_okf_object_versions_id", "okf_object_versions", ["id"])
    op.create_index("ix_okf_object_versions_okf_object_id", "okf_object_versions", ["okf_object_id"])

    # --- document_chunks: version + embedding + tsv + indexes (spec §5) ---
    op.add_column("document_chunks", sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")))
    op.create_index("ix_document_chunks_document_version", "document_chunks", ["document_id", "version"])
    if _is_postgresql():
        op.execute("ALTER TABLE document_chunks ADD COLUMN embedding vector(384)")
        op.execute(
            "CREATE INDEX ix_document_chunks_embedding_hnsw ON document_chunks "
            "USING hnsw (embedding vector_cosine_ops) WITH (m=16, ef_construction=64)"
        )
        op.execute(
            "ALTER TABLE document_chunks ADD COLUMN tsv tsvector "
            "GENERATED ALWAYS AS (to_tsvector('english', \"text\")) STORED"
        )
        op.execute("CREATE INDEX ix_document_chunks_tsv ON document_chunks USING gin (tsv)")
        op.execute(
            "CREATE INDEX ix_document_chunks_department_ids ON document_chunks "
            "USING gin (department_ids jsonb_path_ops)"
        )

    # --- knowledge_objects: search_text + validity window + search indexes ---
    op.add_column("knowledge_objects", sa.Column("search_text", sa.Text(), nullable=True))
    op.add_column("knowledge_objects", sa.Column("valid_from", sa.Date(), nullable=True))
    op.add_column("knowledge_objects", sa.Column("valid_to", sa.Date(), nullable=True))
    if _is_postgresql():
        # Backfill search_text = name + flattened attributes (spec §5).
        op.execute(
            "UPDATE knowledge_objects SET search_text = name || ' ' || COALESCE("
            "(SELECT string_agg(j.key || ' ' || j.value, ' ') "
            "FROM jsonb_each_text(knowledge_objects.payload) AS j), '')"
        )
        op.execute(
            "ALTER TABLE knowledge_objects ADD COLUMN search_tsv tsvector "
            "GENERATED ALWAYS AS (to_tsvector('english', coalesce(search_text, ''))) STORED"
        )
        op.execute("CREATE INDEX ix_knowledge_objects_search_tsv ON knowledge_objects USING gin (search_tsv)")
        op.execute(
            "CREATE INDEX ix_knowledge_objects_search_text_trgm ON knowledge_objects "
            "USING gin (search_text gin_trgm_ops)"
        )
        op.execute(
            "CREATE INDEX ix_knowledge_objects_attributes ON knowledge_objects "
            "USING gin (payload jsonb_path_ops)"
        )
        op.create_index("ix_knowledge_objects_type_status", "knowledge_objects", ["object_type", "status"])


def downgrade() -> None:
    if _is_postgresql():
        op.drop_index("ix_knowledge_objects_type_status", table_name="knowledge_objects")
        op.execute("DROP INDEX IF EXISTS ix_knowledge_objects_attributes")
        op.execute("DROP INDEX IF EXISTS ix_knowledge_objects_search_text_trgm")
        op.execute("DROP INDEX IF EXISTS ix_knowledge_objects_search_tsv")
        op.execute("ALTER TABLE knowledge_objects DROP COLUMN IF EXISTS search_tsv")
    op.drop_column("knowledge_objects", "valid_to")
    op.drop_column("knowledge_objects", "valid_from")
    op.drop_column("knowledge_objects", "search_text")

    if _is_postgresql():
        op.execute("DROP INDEX IF EXISTS ix_document_chunks_department_ids")
        op.execute("DROP INDEX IF EXISTS ix_document_chunks_tsv")
        op.execute("ALTER TABLE document_chunks DROP COLUMN IF EXISTS tsv")
        op.execute("DROP INDEX IF EXISTS ix_document_chunks_embedding_hnsw")
        op.execute("ALTER TABLE document_chunks DROP COLUMN IF EXISTS embedding")
    op.drop_index("ix_document_chunks_document_version", table_name="document_chunks")
    op.drop_column("document_chunks", "version")

    op.drop_table("okf_object_versions")
    op.drop_table("okf_relations")
    op.drop_table("okf_sources")
    op.drop_table("document_versions")
    op.drop_table("ingestion_jobs")
    if _is_postgresql():
        op.execute("DROP TYPE IF EXISTS ingestion_job_status")
    op.drop_table("refresh_tokens")
