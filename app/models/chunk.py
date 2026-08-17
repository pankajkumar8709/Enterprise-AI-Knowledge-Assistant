import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class ChunkStrategy(str, enum.Enum):
    FIXED_SIZE = "fixed_size"
    SENTENCE_BASED = "sentence_based"
    SECTION_BASED = "section_based"


class ChunkStatus(str, enum.Enum):
    READY = "ready"
    ARCHIVED = "archived"


class Chunk(TimestampMixin, Base):
    __tablename__ = "document_chunks"

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

    document = relationship("Document", back_populates="chunks")
