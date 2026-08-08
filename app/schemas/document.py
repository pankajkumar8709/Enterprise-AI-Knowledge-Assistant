from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from app.models.document import DocumentStatus, ExtractionStatus

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
