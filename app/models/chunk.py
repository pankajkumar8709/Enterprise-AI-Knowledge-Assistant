import enum
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, DateTime, Enum, FetchedValue, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, deferred, mapped_column, relationship

from app.core.config import settings
from app.models.base import TSVECTOR, Base, TimestampMixin
from app.models.document import JSON_TYPE, Visibility


class ChunkStrategy(str, enum.Enum):
    FIXED_SIZE = "fixed_size"
    SENTENCE_BASED = "sentence_based"
    SECTION_BASED = "section_based"


class ChunkStatus(str, enum.Enum):
    READY = "ready"
    ARCHIVED = "archived"


class Chunk(TimestampMixin, Base):
    __tablename__ = "document_chunks"
    __table_args__ = (
        # Audit F-019: one contiguous chunk_index set per document (spec §5).
        UniqueConstraint("document_id", "chunk_index", name="uq_document_chunks_document_chunk_index"),
        # Phase 5.5 item 6 (spec §5): full-text + vector + ACL retrieval indexes.
        # The PG-specific USING/ops clauses are ignored by other dialects.
        Index("ix_document_chunks_document_version", "document_id", "version"),
        Index(
            "ix_document_chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
            postgresql_with={"m": 16, "ef_construction": 64},
        ),
        Index("ix_document_chunks_tsv", "tsv", postgresql_using="gin"),
        Index(
            "ix_document_chunks_department_ids",
            "department_ids",
            postgresql_using="gin",
            postgresql_ops={"department_ids": "jsonb_path_ops"},
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True, nullable=False)
    strategy: Mapped[ChunkStrategy] = mapped_column(
        Enum(ChunkStrategy, name="chunk_strategy", values_callable=lambda values: [value.value for value in values]),
        nullable=False,
    )
    status: Mapped[ChunkStatus] = mapped_column(
        Enum(ChunkStatus, name="chunk_status", values_callable=lambda values: [value.value for value in values]),
        default=ChunkStatus.READY,
        nullable=False,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    text_length: Mapped[int] = mapped_column(Integer, nullable=False)
    start_offset: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_offset: Mapped[int | None] = mapped_column(Integer, nullable=True)
    overlap_size: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    section_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    upload_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    token_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    # L2-normalized bge-small-en-v1.5 vector (384 dims) on PostgreSQL;
    # JSON array on SQLite tests. Vector SQL operators are PG-only.
    embedding: Mapped[list | None] = mapped_column(
        Vector(settings.embedding_dim).with_variant(JSON(), "sqlite"), nullable=True
    )
    # Full-text vector — PostgreSQL GENERATED ALWAYS STORED column.
    # deferred + FetchedValue: never sent in INSERT/UPDATE; loaded on access.
    tsv: Mapped[object | None] = deferred(
        mapped_column(TSVECTOR(), nullable=True,
                      server_default=FetchedValue(), server_onupdate=FetchedValue())
    )
    visibility: Mapped[Visibility] = mapped_column(
        Enum(
            Visibility,
            name="visibility",
            values_callable=lambda values: [value.value for value in values],
        ),
        default=Visibility.ALL,
        nullable=False,
    )
    department_ids: Mapped[list] = mapped_column(JSON_TYPE, default=list, nullable=False)

    document = relationship("Document", back_populates="chunks")
