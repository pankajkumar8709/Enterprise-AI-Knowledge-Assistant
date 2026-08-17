from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from app.models.chunk import ChunkStatus, ChunkStrategy
from app.models.document import ChunkingStatus, DocumentStatus, ExtractionStatus

DocumentTitle = Annotated[str, Field(min_length=1, max_length=255)]


class DocumentRead(BaseModel):
    id: int
    title: str
    source_name: str
    stored_name: str
    content_type: str
    size_bytes: int
    storage_path: str
    status: DocumentStatus
    version: int
    extraction_status: ExtractionStatus
    extraction_raw_text_path: str | None
    extraction_clean_text_path: str | None
    extraction_error: str | None
    extraction_ocr_used: bool
    extracted_char_count: int | None
    extraction_started_at: datetime | None
    extraction_completed_at: datetime | None
    chunking_status: ChunkingStatus
    chunking_error: str | None
    chunk_count: int
    chunking_started_at: datetime | None
    chunking_completed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentUpdate(BaseModel):
    title: DocumentTitle | None = None
    status: DocumentStatus | None = None


class DocumentListResponse(BaseModel):
    items: list[DocumentRead]
    total: int


class DocumentExtractionStatusRead(BaseModel):
    document_id: int
    status: ExtractionStatus
    raw_text_path: str | None
    clean_text_path: str | None
    error: str | None
    ocr_used: bool
    extracted_char_count: int | None
    started_at: datetime | None
    completed_at: datetime | None


class DocumentExtractedTextRead(BaseModel):
    document_id: int
    raw_text: str | None
    clean_text: str | None


class DocumentChunkingRequest(BaseModel):
    chunk_size: int = Field(default=800, ge=100, le=5000)
    overlap: int = Field(default=120, ge=0, le=1000)
    strategies: list[ChunkStrategy] = Field(
        default_factory=lambda: [
            ChunkStrategy.FIXED_SIZE,
            ChunkStrategy.SENTENCE_BASED,
            ChunkStrategy.SECTION_BASED,
        ]
    )


class DocumentChunkingStatusRead(BaseModel):
    document_id: int
    status: ChunkingStatus
    error: str | None
    chunk_count: int
    started_at: datetime | None
    completed_at: datetime | None


class ChunkPreviewRead(BaseModel):
    id: int
    strategy: ChunkStrategy
    status: ChunkStatus
    chunk_index: int
    text: str
    text_length: int
    overlap_size: int
    page_number: int | None
    section_title: str | None
    source_file_name: str
    upload_date: datetime

    model_config = ConfigDict(from_attributes=True)


class ChunkPreviewListResponse(BaseModel):
    document_id: int
    chunking_status: ChunkingStatus
    strategy: ChunkStrategy | None
    total: int
    items: list[ChunkPreviewRead]
