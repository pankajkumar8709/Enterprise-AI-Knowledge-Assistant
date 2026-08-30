from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_active_admin, get_current_user
from app.db.session import get_db
from app.models.knowledge import KnowledgeObjectType
from app.schemas.knowledge import (
    KnowledgeExtractionResponse,
    KnowledgeObjectCreate,
    KnowledgeObjectListResponse,
    KnowledgeObjectRead,
    KnowledgeObjectUpdate,
)
from app.services.knowledge import (
    create_knowledge_object,
    delete_knowledge_object,
    extract_knowledge_from_document,
    list_knowledge_objects,
    list_knowledge_versions,
    read_knowledge_object as read_knowledge_object_by_id,
    search_knowledge_objects,
    update_knowledge_object,
)

router = APIRouter()


@router.post("/extract/{document_id}", response_model=KnowledgeExtractionResponse, status_code=status.HTTP_200_OK)
def extract_document_knowledge(
    document_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_admin),
) -> KnowledgeExtractionResponse:
    return extract_knowledge_from_document(db, document_id)


@router.post("", response_model=KnowledgeObjectRead, status_code=status.HTTP_201_CREATED)
def create_knowledge(
    payload: KnowledgeObjectCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_admin),
) -> KnowledgeObjectRead:
    return create_knowledge_object(db, payload)


@router.get("", response_model=KnowledgeObjectListResponse, status_code=status.HTTP_200_OK)
def read_knowledge(
    object_type: KnowledgeObjectType | None = Query(default=None),
    document_id: int | None = Query(default=None),
    include_history: bool = Query(default=False),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> KnowledgeObjectListResponse:
    items = list_knowledge_objects(
        db,
        object_type=object_type,
        document_id=document_id,
        include_history=include_history,
    )
    return KnowledgeObjectListResponse(items=items, total=len(items))


@router.get("/search", response_model=KnowledgeObjectListResponse, status_code=status.HTTP_200_OK)
def search_knowledge(
    q: str = Query(min_length=1),
    object_type: KnowledgeObjectType | None = Query(default=None),
    document_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> KnowledgeObjectListResponse:
    items = search_knowledge_objects(db, query_text=q, object_type=object_type, document_id=document_id)
    return KnowledgeObjectListResponse(items=items, total=len(items))


@router.get("/{knowledge_id}", response_model=KnowledgeObjectRead, status_code=status.HTTP_200_OK)
def read_knowledge_object(
    knowledge_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> KnowledgeObjectRead:
    return read_knowledge_object_by_id(db, knowledge_id)


@router.get("/{knowledge_id}/versions", response_model=KnowledgeObjectListResponse, status_code=status.HTTP_200_OK)
def read_knowledge_versions(
    knowledge_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> KnowledgeObjectListResponse:
    items = list_knowledge_versions(db, knowledge_id)
    return KnowledgeObjectListResponse(items=items, total=len(items))


@router.put("/{knowledge_id}", response_model=KnowledgeObjectRead, status_code=status.HTTP_200_OK)
def replace_knowledge_object(
    knowledge_id: int,
    payload: KnowledgeObjectUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_admin),
) -> KnowledgeObjectRead:
    return update_knowledge_object(db, knowledge_id, payload)


@router.delete("/{knowledge_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_knowledge_object(
    knowledge_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_admin),
) -> Response:
    delete_knowledge_object(db, knowledge_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
