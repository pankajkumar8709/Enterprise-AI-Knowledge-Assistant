from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.deps import get_current_active_admin
from app.db.session import get_db
from app.models.audit import AuditLog
from app.models.document import Document, DocumentStatus
from app.models.knowledge import KnowledgeObject, KnowledgeObjectStatus
from app.models.user import User
from app.services.audit import record_audit

router = APIRouter()

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


@router.get("/stats")
def admin_stats(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_admin),
) -> dict:
    """GET /admin/stats (spec §8). Message-derived metrics fill in at Phase 8."""

    document_rows: dict[DocumentStatus, int] = {
        doc_status: count
        for doc_status, count in db.query(Document.status, func.count(Document.id)).group_by(Document.status).all()
    }
    okf_rows: dict[KnowledgeObjectStatus, int] = {
        okf_status: count
        for okf_status, count in db.query(KnowledgeObject.status, func.count(KnowledgeObject.id))
        .filter(KnowledgeObject.is_current.is_(True))
        .group_by(KnowledgeObject.status)
        .all()
    }
    users = db.query(func.count(User.id)).scalar() or 0

    # chat.query events exist in the audit trail from Phase 8 onward; until then
    # the audit table yields zeros for these derived metrics.
    week_ago = datetime.now(UTC) - timedelta(days=7)
    queries_7d = (
        db.query(func.count(AuditLog.id))
        .filter(AuditLog.action == "chat.query", AuditLog.created_at >= week_ago)
        .scalar()
        or 0
    )

    return {
        "documents": {
            "total": sum(document_rows.values()),
            "ready": int(document_rows.get(DocumentStatus.READY, 0)),
            "processing": int(document_rows.get(DocumentStatus.PROCESSING, 0)),
            "failed": int(document_rows.get(DocumentStatus.FAILED, 0)),
        },
        "okf": {
            "approved": int(okf_rows.get(KnowledgeObjectStatus.APPROVED, 0)),
            "pending": int(okf_rows.get(KnowledgeObjectStatus.PENDING_REVIEW, 0)),
        },
        "users": int(users),
        "queries_7d": int(queries_7d),
        "avg_latency_ms": 0,  # messages.latency_ms aggregate arrives with Phase 8
        "helpful_rate": 0.0,  # feedback aggregate arrives with Phase 8
    }


@router.get("/analytics")
def admin_analytics(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_admin),
) -> dict:
    """GET /admin/analytics (spec §8) — audit-trail derived until Phase 8 adds messages."""

    top_queries = [
        {"query": query, "count": count}
        for query, count in db.query(AuditLog.entity_id, func.count(AuditLog.id).label("count"))
        .filter(AuditLog.action == "chat.query")
        .group_by(AuditLog.entity_id)
        .order_by(func.count(AuditLog.id).desc())
        .limit(10)
        .all()
    ]
    daily_volume = [
        {"date": str(day), "count": count}
        for day, count in db.query(func.date(AuditLog.created_at), func.count(AuditLog.id))
        .filter(AuditLog.action == "chat.query")
        .group_by(func.date(AuditLog.created_at))
        .order_by(func.date(AuditLog.created_at))
        .limit(30)
        .all()
    ]
    return {
        "top_queries": top_queries,
        "unanswered_queries": [],  # needs messages.answerable=false (Phase 8)
        "route_distribution": {},  # needs messages.route (Phase 8)
        "daily_volume": daily_volume,
    }


@router.get("/audit-logs")
def admin_audit_logs(
    user_id: int | None = Query(default=None),
    action: str | None = Query(default=None),
    from_ts: datetime | None = Query(default=None, alias="from"),
    to_ts: datetime | None = Query(default=None, alias="to"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_admin),
) -> dict:
    """GET /admin/audit-logs (spec §8): filters user_id, action, from, to."""

    query = db.query(AuditLog)
    if user_id is not None:
        query = query.filter(AuditLog.user_id == user_id)
    if action is not None:
        query = query.filter(AuditLog.action == action)
    if from_ts is not None:
        query = query.filter(AuditLog.created_at >= from_ts)
    if to_ts is not None:
        query = query.filter(AuditLog.created_at <= to_ts)

    total = query.count()
    page_size = min(max(page_size, 1), MAX_PAGE_SIZE)
    page = max(page, 1)
    rows = query.order_by(AuditLog.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    record_audit(
        db,
        action="admin.audit_logs.read",
        entity_type="admin",
        entity_id=str(current_user.id),
        user_id=current_user.id,
        commit=False,
    )
    return {
        "items": [
            {
                "id": row.id,
                "user_id": row.user_id,
                "action": row.action,
                "entity_type": row.entity_type,
                "entity_id": row.entity_id,
                "metadata": row.metadata_json,
                "ip": row.ip,
                "created_at": row.created_at.isoformat(),
            }
            for row in rows
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }
