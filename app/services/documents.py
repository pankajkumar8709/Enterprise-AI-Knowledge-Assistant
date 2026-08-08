from __future__ import annotations

import shutil
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.document import Document, DocumentStatus
from app.schemas.document import DocumentUpdate

ALLOWED_DOCUMENT_TYPES = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".markdown": "text/markdown",
}


def _get_upload_root() -> Path:
    return Path(settings.document_upload_dir).resolve()


def _ensure_upload_root() -> Path:
    upload_root = _get_upload_root()
    upload_root.mkdir(parents=True, exist_ok=True)
    return upload_root


def _validate_upload(file: UploadFile) -> tuple[str, str]:
    extension = Path(file.filename or "").suffix.lower()
    if extension not in ALLOWED_DOCUMENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file type",
        )
    return extension, ALLOWED_DOCUMENT_TYPES[extension]


def _save_upload(file: UploadFile, stored_name: str) -> tuple[Path, int]:
    upload_root = _ensure_upload_root()
    destination = upload_root / stored_name
    file.file.seek(0)
    size = 0
    with destination.open("wb") as buffer:
        while chunk := file.file.read(1024 * 1024):
            size += len(chunk)
            if size > settings.max_document_size_bytes:
                buffer.close()
                destination.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="File exceeds size limit",
                )
            buffer.write(chunk)
    file.file.seek(0)
    return destination, size


def _delete_stored_file(storage_path: str) -> None:
    Path(storage_path).unlink(missing_ok=True)


def get_document_or_404(db: Session, document_id: int) -> Document:
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return document


def list_documents(db: Session) -> list[Document]:
    return db.query(Document).order_by(Document.created_at.desc()).all()


def create_document(db: Session, title: str, file: UploadFile) -> Document:
    extension, expected_content_type = _validate_upload(file)
    stored_name = f"{uuid4().hex}{extension}"
    storage_path, size_bytes = _save_upload(file, stored_name)

    document = Document(
        title=title.strip(),
        source_name=file.filename or stored_name,
        stored_name=stored_name,
        content_type=file.content_type or expected_content_type,
        size_bytes=size_bytes,
        storage_path=str(storage_path),
        status=DocumentStatus.UPLOADED,
        version=1,
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


def update_document(
    db: Session,
    document: Document,
    payload: DocumentUpdate,
    file: UploadFile | None = None,
) -> Document:
    if payload.title is not None:
        document.title = payload.title.strip()

    if payload.status is not None:
        document.status = payload.status

    if file is not None:
        extension, expected_content_type = _validate_upload(file)
        stored_name = f"{uuid4().hex}{extension}"
        storage_path, size_bytes = _save_upload(file, stored_name)
        old_storage_path = document.storage_path

        document.source_name = file.filename or stored_name
        document.stored_name = stored_name
        document.content_type = file.content_type or expected_content_type
        document.size_bytes = size_bytes
        document.storage_path = str(storage_path)
        document.status = DocumentStatus.UPLOADED
        document.version += 1

        _delete_stored_file(old_storage_path)

    db.add(document)
    db.commit()
    db.refresh(document)
    return document


def delete_document(db: Session, document: Document) -> None:
    storage_path = document.storage_path
    db.delete(document)
    db.commit()
    _delete_stored_file(storage_path)
