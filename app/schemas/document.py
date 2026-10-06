from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from app.core.config import settings
from app.models.chunk import ChunkStatus, ChunkStrategy
from app.models.document import ChunkingStatus, DocumentStatus, ExtractionStatus, Visibility

DocumentTitle = Annotated[str, Field(min_length=1, max_length=255)]


class DocumentRead(BaseModel):
    id: int
    title: str
    source_name: str
    stored_name: str
    content_type: str
    size_bytes: int
    sha256: str | None = None
    status: DocumentStatus
    version: int
    visibility: Visibility = Visibility.ALL
    department_ids: list[int] = Field(default_factory=list)
    extraction_status: ExtractionStatus
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


class DocumentVersionRead(BaseModel):
    id: int
    version: int
    sha256: str | None = None
    size_bytes: int
    uploaded_by_id: int | None = None
    note: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentListResponse(BaseModel):
    items: list[DocumentRead]
    total: int
    page: int
    page_size: int


class DocumentMetadataUpdate(BaseModel):
    """PATCH /documents/{id} body (spec §8): title + ACL; ACL changes propagate."""

    title: DocumentTitle | None = None
    visibility: Visibility | None = None
    department_ids: list[int] | None = None


class JobRead(BaseModel):
    id: int
    status: str
    attempt: int
    error: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class DocumentStatusRead(BaseModel):
    document_id: int
    status: DocumentStatus
    stage: str
    progress_pct: int
    error_message: str | None
    job: JobRead | None = None


class DocumentExtractionStatusRead(BaseModel):
    document_id: int
    status: ExtractionStatus
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
    chunk_size: int = Field(default=settings.chunk_target_tokens * 4, ge=100, le=8000)
    overlap: int = Field(default=settings.chunk_overlap_tokens * 4, ge=0, le=2000)
    strategies: list[ChunkStrategy] = Field(default_factory=lambda: [ChunkStrategy.SECTION_BASED])


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
    token_count: int | None = None
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
    page: int
    page_size: int
    items: list[ChunkPreviewRead]
