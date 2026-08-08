from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from app.models.document import DocumentStatus

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
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentUpdate(BaseModel):
    title: DocumentTitle | None = None
    status: DocumentStatus | None = None


class DocumentListResponse(BaseModel):
    items: list[DocumentRead]
    total: int
