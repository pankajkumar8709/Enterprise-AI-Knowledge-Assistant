from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_active_admin, get_current_user
from app.db.session import get_db
from app.models.knowledge import KnowledgeObjectType
from app.models.user import User
from app.schemas.knowledge import (
    KnowledgeBulkReviewRequest,
    KnowledgeExtractionResponse,
    KnowledgeObjectCreate,
    KnowledgeObjectListResponse,
    KnowledgeObjectRead,
    KnowledgeObjectUpdate,
    KnowledgeReviewRequest,
)
from app.services.audit import record_audit
from app.services.knowledge import (
    approve_knowledge_object,
    bulk_review_knowledge_objects,
    create_knowledge_object,
    delete_knowledge_object,
    extract_knowledge_from_document,
    list_knowledge_objects,
    list_knowledge_versions,
    reject_knowledge_object,
    search_knowledge_objects,
    update_knowledge_object,
)
from app.services.knowledge import (
    read_knowledge_object as read_knowledge_object_by_id,
)

router = APIRouter()

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


def _paginate(items: list, page: int, page_size: int) -> tuple[list, int, int, int]:
    page_size = min(max(page_size, 1), MAX_PAGE_SIZE)
    page = max(page, 1)
    start = (page - 1) * page_size
    return items[start : start + page_size], len(items), page, page_size


@router.post("/extract/{document_id}", response_model=KnowledgeExtractionResponse, status_code=status.HTTP_200_OK)
def extract_document_knowledge(
    document_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_admin),
) -> KnowledgeExtractionResponse:
    result = extract_knowledge_from_document(db, document_id)
    record_audit(
        db,
        action="okf.extract",
        entity_type="document",
        entity_id=str(document_id),
        user_id=current_user.id,
        metadata={"created": result.created, "updated": result.updated},
        ip=request.client.host if request.client else None,
    )
    return result


@router.post("", response_model=KnowledgeObjectRead, status_code=status.HTTP_201_CREATED)
def create_knowledge(
    payload: KnowledgeObjectCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_admin),
) -> KnowledgeObjectRead:
    created = create_knowledge_object(db, payload, current_user)
    record_audit(
        db,
        action="okf.create",
        entity_type="knowledge_object",
        entity_id=str(created.id),
        user_id=current_user.id,
        ip=request.client.host if request.client else None,
    )
    return created


@router.get("", response_model=KnowledgeObjectListResponse, status_code=status.HTTP_200_OK)
def read_knowledge(
    object_type: KnowledgeObjectType | None = Query(default=None),
    document_id: int | None = Query(default=None),
    include_history: bool = Query(default=False),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> KnowledgeObjectListResponse:
    items = list_knowledge_objects(
        db,
        user=current_user,
        object_type=object_type,
        document_id=document_id,
        include_history=include_history,
    )
    page_items, total, page, page_size = _paginate(items, page, page_size)
    return KnowledgeObjectListResponse(items=page_items, total=total, page=page, page_size=page_size)


@router.get("/search", response_model=KnowledgeObjectListResponse, status_code=status.HTTP_200_OK)
def search_knowledge(
    q: str = Query(min_length=1),
    object_type: KnowledgeObjectType | None = Query(default=None),
    document_id: int | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> KnowledgeObjectListResponse:
    items = search_knowledge_objects(
        db, user=current_user, query_text=q, object_type=object_type, document_id=document_id
    )
    page_items, total, page, page_size = _paginate(items, page, page_size)
    return KnowledgeObjectListResponse(items=page_items, total=total, page=page, page_size=page_size)


@router.post("/bulk-review", status_code=status.HTTP_200_OK)
def bulk_review(
    payload: KnowledgeBulkReviewRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_admin),
) -> dict:
    count, _ = bulk_review_knowledge_objects(db, payload.ids, payload.action, current_user, note=None)
    record_audit(
        db,
        action=f"okf.{payload.action}",
        entity_type="knowledge_object",
        entity_id=",".join(str(i) for i in payload.ids),
        user_id=current_user.id,
        ip=request.client.host if request.client else None,
    )
    return {"reviewed": count, "action": payload.action}


@router.get("/{knowledge_id}", response_model=KnowledgeObjectRead, status_code=status.HTTP_200_OK)
def read_knowledge_object(
    knowledge_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> KnowledgeObjectRead:
    return read_knowledge_object_by_id(db, knowledge_id, current_user)


@router.get("/{knowledge_id}/versions", response_model=KnowledgeObjectListResponse, status_code=status.HTTP_200_OK)
def read_knowledge_versions(
    knowledge_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> KnowledgeObjectListResponse:
    items = list_knowledge_versions(db, knowledge_id, current_user)
    page_items, total, page, page_size = _paginate(items, page, page_size)
    return KnowledgeObjectListResponse(items=page_items, total=total, page=page, page_size=page_size)


@router.put("/{knowledge_id}", response_model=KnowledgeObjectRead, status_code=status.HTTP_200_OK)
def replace_knowledge_object(
    knowledge_id: int,
    payload: KnowledgeObjectUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_admin),
) -> KnowledgeObjectRead:
    updated = update_knowledge_object(db, knowledge_id, payload, current_user)
    record_audit(
        db,
        action="okf.update",
        entity_type="knowledge_object",
        entity_id=str(knowledge_id),
        user_id=current_user.id,
        metadata={"change_note": payload.change_note},
        ip=request.client.host if request.client else None,
    )
    return updated


def _review_action(
    request: Request,
    db: Session,
    current_user,
    knowledge_id: int,
    action: str,
    note: str | None,
) -> KnowledgeObjectRead:
    reviewer = approve_knowledge_object if action == "approve" else reject_knowledge_object
    result = reviewer(db, knowledge_id, current_user, note)
    record_audit(
        db,
        action=f"okf.{action}",
        entity_type="knowledge_object",
        entity_id=str(knowledge_id),
        user_id=current_user.id,
        metadata={"note": note},
        ip=request.client.host if request.client else None,
    )
    return result


@router.post("/{knowledge_id}/approve", response_model=KnowledgeObjectRead, status_code=status.HTTP_200_OK)
def approve_knowledge(
    knowledge_id: int,
    request: Request,
    payload: KnowledgeReviewRequest | None = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_admin),
) -> KnowledgeObjectRead:
    note = payload.note if payload else None
    return _review_action(request, db, current_user, knowledge_id, "approve", note)


@router.post("/{knowledge_id}/reject", response_model=KnowledgeObjectRead, status_code=status.HTTP_200_OK)
def reject_knowledge(
    knowledge_id: int,
    request: Request,
    payload: KnowledgeReviewRequest | None = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_admin),
) -> KnowledgeObjectRead:
    note = payload.note if payload else None
    return _review_action(request, db, current_user, knowledge_id, "reject", note)


@router.delete("/{knowledge_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_knowledge_object(
    knowledge_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_admin),
) -> Response:
    delete_knowledge_object(db, knowledge_id)
    record_audit(
        db,
        action="okf.delete",
        entity_type="knowledge_object",
        entity_id=str(knowledge_id),
        user_id=current_user.id,
        ip=request.client.host if request.client else None,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
