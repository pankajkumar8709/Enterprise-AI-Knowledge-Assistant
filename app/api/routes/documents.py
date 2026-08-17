from typing import Annotated

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, Query, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_active_admin
from app.db.session import get_db
from app.models.chunk import ChunkStrategy
from app.schemas.document import (
    ChunkPreviewListResponse,
    DocumentExtractedTextRead,
    DocumentChunkingRequest,
    DocumentChunkingStatusRead,
    DocumentExtractionStatusRead,
    DocumentListResponse,
    DocumentRead,
    DocumentUpdate,
)
from app.services.chunking import (
    ChunkingError,
    ChunkingOptions,
    chunk_document,
    count_document_chunks,
    list_document_chunks,
)
from app.services.documents import (
    create_document,
    delete_document,
    get_document_or_404,
    list_documents,
    update_document,
)
from app.services.extraction import extract_document_text, get_extracted_text

router = APIRouter()


@router.post("", response_model=DocumentRead, status_code=status.HTTP_201_CREATED)
def upload_document(
    title: Annotated[str, Form(min_length=1, max_length=255)],
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_admin),
) -> DocumentRead:
    return create_document(db, title=title, file=file)


@router.get("", response_model=DocumentListResponse, status_code=status.HTTP_200_OK)
def read_documents(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_admin),
) -> DocumentListResponse:
    documents = list_documents(db)
    return DocumentListResponse(items=documents, total=len(documents))


@router.get("/{document_id}", response_model=DocumentRead, status_code=status.HTTP_200_OK)
def read_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_admin),
) -> DocumentRead:
    return get_document_or_404(db, document_id)


@router.get(
    "/{document_id}/extraction-status",
    response_model=DocumentExtractionStatusRead,
    status_code=status.HTTP_200_OK,
)
def read_document_extraction_status(
    document_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_admin),
) -> DocumentExtractionStatusRead:
    document = get_document_or_404(db, document_id)
    return DocumentExtractionStatusRead(
        document_id=document.id,
        status=document.extraction_status,
        raw_text_path=document.extraction_raw_text_path,
        clean_text_path=document.extraction_clean_text_path,
        error=document.extraction_error,
        ocr_used=document.extraction_ocr_used,
        extracted_char_count=document.extracted_char_count,
        started_at=document.extraction_started_at,
        completed_at=document.extraction_completed_at,
    )


@router.get(
    "/{document_id}/extracted-text",
    response_model=DocumentExtractedTextRead,
    status_code=status.HTTP_200_OK,
)
def read_document_extracted_text(
    document_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_admin),
) -> DocumentExtractedTextRead:
    document = get_document_or_404(db, document_id)
    raw_text, clean_text = get_extracted_text(document)
    return DocumentExtractedTextRead(document_id=document.id, raw_text=raw_text, clean_text=clean_text)


@router.post(
    "/{document_id}/extract",
    response_model=DocumentExtractionStatusRead,
    status_code=status.HTTP_200_OK,
)
def trigger_document_extraction(
    document_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_admin),
) -> DocumentExtractionStatusRead:
    document = get_document_or_404(db, document_id)
    document = extract_document_text(db, document)
    return DocumentExtractionStatusRead(
        document_id=document.id,
        status=document.extraction_status,
        raw_text_path=document.extraction_raw_text_path,
        clean_text_path=document.extraction_clean_text_path,
        error=document.extraction_error,
        ocr_used=document.extraction_ocr_used,
        extracted_char_count=document.extracted_char_count,
        started_at=document.extraction_started_at,
        completed_at=document.extraction_completed_at,
    )


@router.get(
    "/{document_id}/chunk-status",
    response_model=DocumentChunkingStatusRead,
    status_code=status.HTTP_200_OK,
)
def read_document_chunk_status(
    document_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_admin),
) -> DocumentChunkingStatusRead:
    document = get_document_or_404(db, document_id)
    return DocumentChunkingStatusRead(
        document_id=document.id,
        status=document.chunking_status,
        error=document.chunking_error,
        chunk_count=document.chunk_count,
        started_at=document.chunking_started_at,
        completed_at=document.chunking_completed_at,
    )


@router.post(
    "/{document_id}/chunk",
    response_model=DocumentChunkingStatusRead,
    status_code=status.HTTP_200_OK,
)
def trigger_document_chunking(
    document_id: int,
    payload: DocumentChunkingRequest | None = Body(default=None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_admin),
) -> DocumentChunkingStatusRead:
    document = get_document_or_404(db, document_id)
    payload = payload or DocumentChunkingRequest()
    try:
        document = chunk_document(
            db,
            document,
            ChunkingOptions(
                chunk_size=payload.chunk_size,
                overlap=payload.overlap,
                strategies=tuple(payload.strategies),
            ),
        )
    except ChunkingError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return DocumentChunkingStatusRead(
        document_id=document.id,
        status=document.chunking_status,
        error=document.chunking_error,
        chunk_count=document.chunk_count,
        started_at=document.chunking_started_at,
        completed_at=document.chunking_completed_at,
    )


@router.get(
    "/{document_id}/chunks/preview",
    response_model=ChunkPreviewListResponse,
    status_code=status.HTTP_200_OK,
)
def read_document_chunk_preview(
    document_id: int,
    strategy: ChunkStrategy | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_admin),
) -> ChunkPreviewListResponse:
    document = get_document_or_404(db, document_id)
    chunks = list_document_chunks(db, document_id=document.id, strategy=strategy, limit=limit)
    total = count_document_chunks(db, document_id=document.id, strategy=strategy)
    return ChunkPreviewListResponse(
        document_id=document.id,
        chunking_status=document.chunking_status,
        strategy=strategy,
        total=total,
        items=chunks,
    )


@router.put("/{document_id}", response_model=DocumentRead, status_code=status.HTTP_200_OK)
def replace_document(
    document_id: int,
    title: Annotated[str | None, Form(min_length=1, max_length=255)] = None,
    status_value: Annotated[str | None, Form(alias="status")] = None,
    file: UploadFile | None = File(default=None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_admin),
) -> DocumentRead:
    payload = DocumentUpdate.model_validate({"title": title, "status": status_value})
    document = get_document_or_404(db, document_id)
    return update_document(db, document=document, payload=payload, file=file)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_admin),
) -> Response:
    document = get_document_or_404(db, document_id)
    delete_document(db, document)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
