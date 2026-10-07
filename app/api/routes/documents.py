from typing import Annotated

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Body,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.deps import get_current_active_admin, get_current_user
from app.db.session import get_db
from app.models.chunk import Chunk, ChunkStrategy
from app.models.document import ChunkingStatus, Document, DocumentStatus, ExtractionStatus, Visibility
from app.models.ingestion_job import IngestionJob, JobStatus
from app.models.user import User
from app.schemas.document import (
    ChunkPreviewListResponse,
    ChunkPreviewRead,
    DocumentChunkingRequest,
    DocumentChunkingStatusRead,
    DocumentExtractedTextRead,
    DocumentExtractionStatusRead,
    DocumentListResponse,
    DocumentMetadataUpdate,
    DocumentRead,
    DocumentStatusRead,
    DocumentUpdate,
    DocumentVersionRead,
    JobRead,
)
from app.services.audit import record_audit
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
    get_document_or_403,
    get_document_or_404,
    list_documents,
    reprocess_document,
    update_document,
    update_document_metadata,
    upload_new_version,
)
from app.services.extraction import extract_document_text, get_extracted_text
from app.services.ingestion import queue_ingestion, run_ingestion_task
from app.services.knowledge import approve_pending_for_document

router = APIRouter()

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100

# Spec §7.2 stages (6 steps); embedding/okf stages are wired in Phase 6/8.
STAGE_ORDER = ["extracting", "cleaning", "chunking", "embedding", "okf_extracting", "indexing"]


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _stage_for(document: Document) -> tuple[str, int]:
    if document.extraction_status in (ExtractionStatus.PENDING, ExtractionStatus.PROCESSING):
        return "extracting", 17
    if document.chunking_status in (ChunkingStatus.PENDING, ChunkingStatus.PROCESSING):
        return "chunking", 67
    if document.status == DocumentStatus.FAILED:
        return "extracting" if document.extraction_status == ExtractionStatus.FAILED else "chunking", 50
    return "done", 100


def _latest_job_read(db: Session, document: Document) -> JobRead | None:
    from app.models.ingestion_job import IngestionJob

    job = (
        db.query(IngestionJob)
        .filter(IngestionJob.document_id == document.id, IngestionJob.version == document.version)
        .order_by(IngestionJob.id.desc())
        .first()
    )
    if job is None:
        return None
    return JobRead(
        id=job.id,
        status=job.status.value if isinstance(job.status, JobStatus) else str(job.status),
        attempt=job.attempt,
        error=job.error,
        started_at=job.started_at,
        finished_at=job.finished_at,
    )


@router.post("", response_model=DocumentRead, status_code=status.HTTP_202_ACCEPTED)
def upload_document(
    request: Request,
    background_tasks: BackgroundTasks,
    title: Annotated[str, Form(min_length=1, max_length=255)],
    file: UploadFile = File(...),
    force: bool = Query(default=False),
    visibility: Visibility = Form(default=Visibility.ALL),
    department_ids: list[int] = Form(default=[]),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_admin),
) -> DocumentRead:
    document = create_document(
        db,
        title=title,
        file=file,
        force=force,
        visibility=visibility,
        department_ids=department_ids,
        uploaded_by_id=current_user.id,
    )
    job = queue_ingestion(db, document)
    background_tasks.add_task(run_ingestion_task, document.id, document.version, job.id)
    record_audit(
        db,
        action="document.upload",
        entity_type="document",
        entity_id=str(document.id),
        user_id=current_user.id,
        metadata={"status": document.status.value, "sha256": document.sha256, "visibility": visibility.value},
        ip=_client_ip(request),
    )
    return DocumentRead.model_validate(db.query(Document).filter(Document.id == document.id).first())


@router.get("", response_model=DocumentListResponse, status_code=status.HTTP_200_OK)
def read_documents(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DocumentListResponse:
    # Spec §8: admin sees all; employees get ACL-filtered results (§11 matrix).
    documents = list_documents(db, current_user)
    page_size = min(max(page_size, 1), MAX_PAGE_SIZE)
    page = max(page, 1)
    start = (page - 1) * page_size
    items = [DocumentRead.model_validate(document) for document in documents[start : start + page_size]]
    return DocumentListResponse(items=items, total=len(documents), page=page, page_size=page_size)


@router.get("/{document_id}", response_model=DocumentRead, status_code=status.HTTP_200_OK)
def read_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DocumentRead:
    return DocumentRead.model_validate(get_document_or_403(db, document_id, current_user))


@router.patch("/{document_id}", response_model=DocumentRead, status_code=status.HTTP_200_OK)
def patch_document(
    document_id: int,
    payload: DocumentMetadataUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_admin),
) -> DocumentRead:
    document = get_document_or_404(db, document_id)
    acl_changed = payload.visibility is not None or payload.department_ids is not None
    document = update_document_metadata(
        db,
        document,
        title=payload.title,
        visibility=payload.visibility,
        department_ids=payload.department_ids,
        auto_approve_knowledge=payload.auto_approve_knowledge,
    )
    approved_count = 0
    if payload.auto_approve_knowledge:
        # Trusted-source rule: enabling the flag also approves facts from this
        # document that were still waiting for review.
        approved_count = approve_pending_for_document(
            db,
            document.id,
            reviewed_by_id=current_user.id,
            note="auto-approved: document marked as trusted source",
        )
    record_audit(
        db,
        action="document.update",
        entity_type="document",
        entity_id=str(document.id),
        user_id=current_user.id,
        metadata={
            "title": document.title,
            "visibility": document.visibility.value,
            "auto_approve_knowledge": document.auto_approve_knowledge,
            "pending_approved": approved_count,
        },
        ip=_client_ip(request),
    )
    if acl_changed:
        record_audit(
            db,
            action="acl.change",
            entity_type="document",
            entity_id=str(document.id),
            user_id=current_user.id,
            metadata={"visibility": document.visibility.value, "department_ids": document.department_ids},
            ip=_client_ip(request),
        )
    return DocumentRead.model_validate(document)


@router.put("/{document_id}/file", response_model=DocumentRead, status_code=status.HTTP_202_ACCEPTED)
def replace_document_file(
    document_id: int,
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    note: Annotated[str | None, Form(max_length=2000)] = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_admin),
) -> DocumentRead:
    document = get_document_or_404(db, document_id)
    document = upload_new_version(db, document, file, note=note, uploaded_by_id=current_user.id)
    job = queue_ingestion(db, document)
    background_tasks.add_task(run_ingestion_task, document.id, document.version, job.id)
    record_audit(
        db,
        action="document.update",
        entity_type="document",
        entity_id=str(document.id),
        user_id=current_user.id,
        metadata={"version": document.version, "note": note},
        ip=_client_ip(request),
    )
    return DocumentRead.model_validate(db.query(Document).filter(Document.id == document.id).first())


@router.post("/{document_id}/reprocess", response_model=DocumentRead, status_code=status.HTTP_202_ACCEPTED)
def reprocess(
    document_id: int,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_admin),
) -> DocumentRead:
    document = get_document_or_404(db, document_id)
    # Guard against double-clicks / overlapping reprocess runs: two concurrent
    # ingestion jobs on one document version re-chunk simultaneously and race
    # on the chunk rows (observed as StaleDataError: "expected to update N
    # row(s); 0 were matched").
    active_job = (
        db.query(IngestionJob)
        .filter(
            IngestionJob.document_id == document.id,
            IngestionJob.version == document.version,
            IngestionJob.status.in_([JobStatus.QUEUED, JobStatus.RUNNING]),
        )
        .first()
    )
    if active_job is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An ingestion job is already queued or running for this document version; wait for it to finish",
        )
    document = reprocess_document(db, document)
    job = queue_ingestion(db, document)
    background_tasks.add_task(run_ingestion_task, document.id, document.version, job.id)
    record_audit(
        db,
        action="document.reprocess",
        entity_type="document",
        entity_id=str(document.id),
        user_id=current_user.id,
        metadata={"version": document.version},
        ip=_client_ip(request),
    )
    return DocumentRead.model_validate(db.query(Document).filter(Document.id == document.id).first())


@router.get("/{document_id}/versions", response_model=list[DocumentVersionRead], status_code=status.HTTP_200_OK)
def read_document_versions(
    document_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_admin),
) -> list[DocumentVersionRead]:
    from app.models.document_version import DocumentVersion

    document = get_document_or_404(db, document_id)
    rows = (
        db.query(DocumentVersion)
        .filter(DocumentVersion.document_id == document.id)
        .order_by(DocumentVersion.version.desc())
        .all()
    )
    return [DocumentVersionRead.model_validate(row) for row in rows]


@router.get("/{document_id}/download")
def download_document(
    document_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FileResponse:
    # ACL: employees may download only documents they can see (spec §11).
    document = get_document_or_403(db, document_id, current_user)
    record_audit(
        db,
        action="document.download",
        entity_type="document",
        entity_id=str(document.id),
        user_id=current_user.id,
        ip=_client_ip(request),
    )
    return FileResponse(
        path=document.storage_path,
        media_type=document.content_type,
        filename=document.source_name,
        headers={"Content-Disposition": f'attachment; filename="{document.source_name}"'},
    )


@router.get("/{document_id}/status", response_model=DocumentStatusRead, status_code=status.HTTP_200_OK)
def read_document_status(
    document_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_admin),
) -> DocumentStatusRead:
    document = get_document_or_404(db, document_id)
    stage, progress_pct = _stage_for(document)
    error = document.extraction_error or document.chunking_error
    return DocumentStatusRead(
        document_id=document.id,
        status=document.status,
        stage=stage,
        progress_pct=progress_pct,
        error_message=error,
        job=_latest_job_read(db, document),
    )


@router.get(
    "/{document_id}/extraction-status", response_model=DocumentExtractionStatusRead, status_code=status.HTTP_200_OK
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
        error=document.extraction_error,
        ocr_used=document.extraction_ocr_used,
        extracted_char_count=document.extracted_char_count,
        started_at=document.extraction_started_at,
        completed_at=document.extraction_completed_at,
    )


@router.get("/{document_id}/extracted-text", response_model=DocumentExtractedTextRead, status_code=status.HTTP_200_OK)
def read_document_extracted_text(
    document_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_admin),
) -> DocumentExtractedTextRead:
    document = get_document_or_404(db, document_id)
    raw_text, clean_text = get_extracted_text(document)
    return DocumentExtractedTextRead(document_id=document.id, raw_text=raw_text, clean_text=clean_text)


@router.post("/{document_id}/extract", response_model=DocumentExtractionStatusRead, status_code=status.HTTP_200_OK)
def trigger_document_extraction(
    document_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_admin),
) -> DocumentExtractionStatusRead:
    document = get_document_or_404(db, document_id)
    document = extract_document_text(db, document)
    record_audit(
        db,
        action="document.reprocess",
        entity_type="document",
        entity_id=str(document.id),
        user_id=current_user.id,
        metadata={"extraction_status": document.extraction_status.value},
        ip=_client_ip(request),
    )
    return DocumentExtractionStatusRead(
        document_id=document.id,
        status=document.extraction_status,
        error=document.extraction_error,
        ocr_used=document.extraction_ocr_used,
        extracted_char_count=document.extracted_char_count,
        started_at=document.extraction_started_at,
        completed_at=document.extraction_completed_at,
    )


@router.get("/{document_id}/chunk-status", response_model=DocumentChunkingStatusRead, status_code=status.HTTP_200_OK)
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


@router.post("/{document_id}/chunk", response_model=DocumentChunkingStatusRead, status_code=status.HTTP_200_OK)
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


@router.get("/{document_id}/chunks/preview", response_model=ChunkPreviewListResponse, status_code=status.HTTP_200_OK)
def read_document_chunk_preview(
    document_id: int,
    strategy: ChunkStrategy | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=MAX_PAGE_SIZE),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_admin),
) -> ChunkPreviewListResponse:
    document = get_document_or_404(db, document_id)
    total = count_document_chunks(db, document_id=document.id, strategy=strategy)
    start = (page - 1) * page_size
    chunks: list[Chunk] = list_document_chunks(
        db, document_id=document.id, strategy=strategy, limit=page_size, offset=start
    )
    return ChunkPreviewListResponse(
        document_id=document.id,
        chunking_status=document.chunking_status,
        strategy=strategy,
        total=total,
        page=page,
        page_size=page_size,
        items=[ChunkPreviewRead.model_validate(chunk) for chunk in chunks],
    )


@router.put("/{document_id}", response_model=DocumentRead, status_code=status.HTTP_200_OK)
def replace_document(
    document_id: int,
    request: Request,
    background_tasks: BackgroundTasks,
    title: Annotated[str | None, Form(min_length=1, max_length=255)] = None,
    file: UploadFile | None = File(default=None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_admin),
) -> DocumentRead:
    # Audit F-006: `status` is no longer client-writable; it follows the pipeline.
    payload = DocumentUpdate.model_validate({"title": title})
    document = get_document_or_404(db, document_id)
    document = update_document(db, document=document, payload=payload, file=file, uploaded_by_id=current_user.id)
    if file is not None:
        job = queue_ingestion(db, document)
        background_tasks.add_task(run_ingestion_task, document.id, document.version, job.id)
    record_audit(
        db,
        action="document.update",
        entity_type="document",
        entity_id=str(document.id),
        user_id=current_user.id,
        metadata={"title": document.title, "version": document.version},
        ip=_client_ip(request),
    )
    return DocumentRead.model_validate(document)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_document(
    document_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_admin),
) -> Response:
    document = get_document_or_404(db, document_id)
    delete_document(db, document)
    record_audit(
        db,
        action="document.delete",
        entity_type="document",
        entity_id=str(document_id),
        user_id=current_user.id,
        ip=_client_ip(request),
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
