import enum
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

# jsonb on PostgreSQL, portable JSON elsewhere (SQLite tests).
JSON_TYPE = JSON().with_variant(postgresql.JSONB(), "postgresql")


class DocumentStatus(str, enum.Enum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class Visibility(str, enum.Enum):
    ALL = "all"
    DEPARTMENT = "department"
    ADMIN_ONLY = "admin_only"


class ExtractionStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class ChunkingStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class Document(TimestampMixin, Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    source_name: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_name: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(255), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)
    sha256: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    uploaded_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
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
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus, name="document_status", values_callable=lambda x: [e.value for e in x]),
        default=DocumentStatus.UPLOADED,
        nullable=False,
    )
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    extraction_status: Mapped[ExtractionStatus] = mapped_column(
        Enum(ExtractionStatus, name="extraction_status", values_callable=lambda x: [e.value for e in x]),
        default=ExtractionStatus.PENDING,
        nullable=False,
    )
    extraction_raw_text_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    extraction_clean_text_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    extraction_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    extraction_ocr_used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    extracted_char_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    extraction_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    extraction_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    chunking_status: Mapped[ChunkingStatus] = mapped_column(
        Enum(ChunkingStatus, name="chunking_status", values_callable=lambda x: [e.value for e in x]),
        default=ChunkingStatus.PENDING,
        nullable=False,
    )
    chunking_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    chunking_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    chunking_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    chunks = relationship("Chunk", back_populates="document", cascade="all, delete-orphan")


def refresh_document_status(document: Document) -> None:
    """Derive documents.status from the pipeline stages (audit F-006).

    The status field must never be client-writable: it follows extraction and
    chunking so a document can no longer sit on `uploaded` forever, and any
    stage failure surfaces as `failed`.
    """

    if document.extraction_status == ExtractionStatus.FAILED or document.chunking_status == ChunkingStatus.FAILED:
        document.status = DocumentStatus.FAILED
    elif document.extraction_status == ExtractionStatus.READY and document.chunking_status == ChunkingStatus.READY:
        document.status = DocumentStatus.READY
    elif document.extraction_status == ExtractionStatus.PENDING and document.chunking_status == ChunkingStatus.PENDING:
        document.status = DocumentStatus.UPLOADED
    else:
        document.status = DocumentStatus.PROCESSING
