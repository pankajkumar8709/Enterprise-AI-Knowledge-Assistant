from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.chunk import Chunk
from app.models.document import (
    ChunkingStatus,
    Document,
    DocumentStatus,
    ExtractionStatus,
    Visibility,
)
from app.models.document_version import DocumentVersion
from app.models.ingestion_job import IngestionJob
from app.models.knowledge import KnowledgeObject, KnowledgeObjectStatus
from app.models.knowledge_source import KnowledgeObjectSource
from app.models.user import User, UserRole
from app.schemas.document import DocumentUpdate
from app.services.chunking import reset_document_chunks
from app.services.extraction import delete_extraction_files
from app.services.retrieval.acl import acl_clause

ALLOWED_DOCUMENT_TYPES = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "txt": "text/plain",
    "md": "text/markdown",
    "markdown": "text/markdown",
}


def _get_upload_root() -> Path:
    return Path(settings.document_upload_dir).resolve()


def _ensure_upload_root() -> Path:
    upload_root = _get_upload_root()
    upload_root.mkdir(parents=True, exist_ok=True)
    return upload_root


def _validate_upload(file: UploadFile) -> tuple[str, str]:
    extension = Path(file.filename or "").suffix.lower().lstrip(".")
    if extension not in settings.allowed_extension_list or extension not in ALLOWED_DOCUMENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Unsupported file type",
        )
    return extension, ALLOWED_DOCUMENT_TYPES[extension]


def _verify_file_signature(file_path: Path, extension: str) -> None:
    """Verify real content matches the extension (spec §7.1.1 magic bytes)."""

    def _reject() -> None:
        file_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="File content does not match its extension",
        )

    head = file_path.read_bytes()[:8192]
    if extension == "pdf":
        if not head.startswith(b"%PDF-"):
            _reject()
        return
    if extension in {"docx", "pptx"}:
        expected_member = "word/document.xml" if extension == "docx" else "ppt/presentation.xml"
        if not zipfile.is_zipfile(file_path):
            _reject()
        try:
            with zipfile.ZipFile(file_path) as archive:
                if expected_member not in archive.namelist():
                    _reject()
        except zipfile.BadZipFile:
            _reject()
        return
    # Text formats: reject binary content masquerading as text.
    if b"\x00" in head:
        _reject()


def _save_upload(file: UploadFile, stored_name: str) -> tuple[Path, int, str]:
    upload_root = _ensure_upload_root()
    destination = upload_root / stored_name
    file.file.seek(0)
    size = 0
    digest = hashlib.sha256()
    with destination.open("wb") as buffer:
        while chunk := file.file.read(1024 * 1024):
            size += len(chunk)
            if size > settings.max_document_size_bytes:
                buffer.close()
                destination.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                    detail="File exceeds size limit",
                )
            digest.update(chunk)
            buffer.write(chunk)
    file.file.seek(0)
    if size == 0:
        destination.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Empty file",
        )
    return destination, size, digest.hexdigest()


def _delete_stored_file(storage_path: str) -> None:
    Path(storage_path).unlink(missing_ok=True)


def get_document_or_404(db: Session, document_id: int) -> Document:
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return document


def get_document_or_403(db: Session, document_id: int, user: User) -> Document:
    """ACL-guarded read (spec §11: employees may read `all` or own-department docs)."""

    document = get_document_or_404(db, document_id)
    if db.query(Document).filter(Document.id == document.id, acl_clause(user, Document)).count() == 0:
        # Do not leak existence: employees get 404 for forbidden documents.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return document


def list_documents(db: Session, user: User | None = None) -> list[Document]:
    query = db.query(Document).order_by(Document.created_at.desc())
    if user is not None and user.role != UserRole.ADMIN:
        query = query.filter(acl_clause(user, Document))
    return query.all()


def _add_version_row(
    db: Session, document: Document, size_bytes: int, sha256: str | None, note: str | None, uploaded_by_id: int | None
) -> None:
    db.add(
        DocumentVersion(
            document_id=document.id,
            version=document.version,
            storage_path=document.storage_path,
            sha256=sha256,
            size_bytes=size_bytes,
            uploaded_by_id=uploaded_by_id,
            note=note,
        )
    )


def create_document(
    db: Session,
    title: str,
    file: UploadFile,
    force: bool = False,
    visibility: Visibility = Visibility.ALL,
    department_ids: list[int] | None = None,
    uploaded_by_id: int | None = None,
) -> Document:
    extension, expected_content_type = _validate_upload(file)
    stored_name = f"{uuid4().hex}.{extension}"
    storage_path, size_bytes, sha256 = _save_upload(file, stored_name)
    _verify_file_signature(storage_path, extension)

    if not force:
        existing = db.query(Document).filter(Document.sha256 == sha256).order_by(Document.id.asc()).first()
        if existing is not None:
            storage_path.unlink(missing_ok=True)
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Duplicate document: identical file already exists as document {existing.id}",
            )

    document = Document(
        title=title.strip(),
        source_name=file.filename or stored_name,
        stored_name=stored_name,
        content_type=file.content_type or expected_content_type,
        size_bytes=size_bytes,
        storage_path=str(storage_path),
        sha256=sha256,
        status=DocumentStatus.PROCESSING,
        version=1,
        visibility=visibility,
        department_ids=list(department_ids or []),
        uploaded_by_id=uploaded_by_id,
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    _add_version_row(db, document, size_bytes, sha256, note=None, uploaded_by_id=uploaded_by_id)
    db.commit()
    return document


def update_document(
    db: Session,
    document: Document,
    payload: DocumentUpdate,
    file: UploadFile | None = None,
    uploaded_by_id: int | None = None,
) -> Document:
    if payload.title is not None:
        document.title = payload.title.strip()

    if file is not None:
        _store_new_version(db, document, file, note=None, uploaded_by_id=uploaded_by_id)

    db.add(document)
    db.commit()
    db.refresh(document)
    return document


def update_document_metadata(
    db: Session,
    document: Document,
    *,
    title: str | None = None,
    visibility: Visibility | None = None,
    department_ids: list[int] | None = None,
) -> Document:
    """PATCH /documents/{id} — metadata + ACL; ACL changes propagate in one transaction (spec §5)."""

    acl_changed = False
    if title is not None:
        document.title = title.strip()
    if visibility is not None and visibility != document.visibility:
        document.visibility = visibility
        acl_changed = True
    if department_ids is not None and list(department_ids) != list(document.department_ids or []):
        document.department_ids = list(department_ids)
        acl_changed = True

    db.add(document)
    if acl_changed:
        propagate_document_acl(db, document)
    db.commit()
    db.refresh(document)
    return document


def _store_new_version(
    db: Session, document: Document, file: UploadFile, *, note: str | None, uploaded_by_id: int | None
) -> None:
    extension, expected_content_type = _validate_upload(file)
    stored_name = f"{uuid4().hex}.{extension}"
    storage_path, size_bytes, sha256 = _save_upload(file, stored_name)
    _verify_file_signature(storage_path, extension)
    old_storage_path = document.storage_path

    document.source_name = file.filename or stored_name
    document.stored_name = stored_name
    document.content_type = file.content_type or expected_content_type
    document.size_bytes = size_bytes
    document.storage_path = str(storage_path)
    document.sha256 = sha256
    document.version += 1
    document.status = DocumentStatus.PROCESSING
    document.extraction_status = ExtractionStatus.PENDING
    document.extraction_error = None
    document.chunking_status = ChunkingStatus.PENDING
    document.chunking_error = None
    document.chunk_count = 0

    _add_version_row(db, document, size_bytes, sha256, note=note, uploaded_by_id=uploaded_by_id)
    _delete_stored_file(old_storage_path)


def upload_new_version(
    db: Session,
    document: Document,
    file: UploadFile,
    *,
    note: str | None = None,
    uploaded_by_id: int | None = None,
) -> Document:
    """PUT /documents/{id}/file — new file version, pipeline re-runs (spec §5/§8)."""

    _store_new_version(db, document, file, note=note, uploaded_by_id=uploaded_by_id)
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


def reprocess_document(db: Session, document: Document) -> Document:
    """POST /documents/{id}/reprocess — re-run ingestion on the current version (spec §8)."""

    document.status = DocumentStatus.PROCESSING
    document.extraction_status = ExtractionStatus.PENDING
    document.extraction_error = None
    document.chunking_status = ChunkingStatus.PENDING
    document.chunking_error = None
    document.chunk_count = 0
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


def propagate_document_acl(db: Session, document: Document) -> None:
    """Denormalized ACL copies on chunks + OKF objects updated in one transaction (spec §5)."""

    db.query(KnowledgeObject).filter(
        KnowledgeObject.source_document_id == document.id,
        KnowledgeObject.is_current.is_(True),
    ).update(
        {
            KnowledgeObject.visibility: document.visibility,
            KnowledgeObject.department_ids: list(document.department_ids or []),
        },
        synchronize_session=False,
    )
    db.query(Chunk).filter(Chunk.document_id == document.id).update(
        {
            Chunk.visibility: document.visibility,
            Chunk.department_ids: list(document.department_ids or []),
        },
        synchronize_session=False,
    )


def delete_document(db: Session, document: Document) -> None:
    storage_path = document.storage_path
    delete_extraction_files(document)
    reset_document_chunks(db, document, commit=False)
    # Spec §5: knowledge objects whose only source was this document are
    # archived (never hard-deleted); objects with other sources stay alive.
    for knowledge_object in db.query(KnowledgeObject).filter(KnowledgeObject.source_document_id == document.id).all():
        other_sources = (
            db.query(KnowledgeObject)
            .filter(
                KnowledgeObject.object_key == knowledge_object.object_key,
                KnowledgeObject.id != knowledge_object.id,
                KnowledgeObject.source_document_id != document.id,
            )
            .count()
        )
        if other_sources:
            knowledge_object.source_document_id = None
            db.add(knowledge_object)
        else:
            knowledge_object.status = KnowledgeObjectStatus.ARCHIVED
            knowledge_object.is_current = False
            # Detach before the document row goes away: the FK is ON DELETE
            # CASCADE and would otherwise destroy the archived history.
            knowledge_object.source_document_id = None
            db.add(knowledge_object)
    # Version history, job rows and source links never outlive the document.
    db.query(DocumentVersion).filter(DocumentVersion.document_id == document.id).delete(synchronize_session=False)
    db.query(IngestionJob).filter(IngestionJob.document_id == document.id).delete(synchronize_session=False)
    db.query(KnowledgeObjectSource).filter(KnowledgeObjectSource.document_id == document.id).delete(
        synchronize_session=False
    )
    db.delete(document)
    db.commit()
    _delete_stored_file(storage_path)
