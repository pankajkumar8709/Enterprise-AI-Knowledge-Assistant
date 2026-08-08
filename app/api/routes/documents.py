from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_active_admin
from app.db.session import get_db
from app.schemas.document import DocumentListResponse, DocumentRead, DocumentUpdate
from app.services.documents import (
    create_document,
    delete_document,
    get_document_or_404,
    list_documents,
    update_document,
)

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
