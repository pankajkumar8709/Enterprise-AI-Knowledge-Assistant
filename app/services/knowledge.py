from __future__ import annotations

import logging
import re
from collections.abc import Iterable
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import String, and_, cast, false, func, or_, true
from sqlalchemy.orm import Session

from app.models.document import Document, ExtractionStatus, Visibility
from app.models.knowledge import (
    KnowledgeObject,
    KnowledgeObjectStatus,
    KnowledgeObjectType,
)
from app.models.knowledge_version import KnowledgeObjectVersion
from app.models.user import User, UserRole
from app.schemas.knowledge import (
    RELATION_PREDICATES,
    KnowledgeObjectCreate,
    KnowledgeObjectRead,
    KnowledgeObjectUpdate,
    KnowledgeRelation,
)
from app.services.documents import get_document_or_404
from app.services.extraction import get_extracted_text

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1
RULE_PATTERN = re.compile(r"\b(must|should|shall|required|not allowed|prohibited|only)\b", flags=re.IGNORECASE)

# Spec §6.2 required attributes per type (audit F-022): ★ fields must be present.
REQUIRED_ATTRIBUTES: dict[KnowledgeObjectType, set[str]] = {
    KnowledgeObjectType.POLICY: {"title", "summary"},
    KnowledgeObjectType.EMPLOYEE: {"full_name", "job_title"},
    KnowledgeObjectType.DEPARTMENT: {"name"},
    KnowledgeObjectType.PRODUCT: {"name"},
    KnowledgeObjectType.FAQ: {"question", "answer"},
    KnowledgeObjectType.BUSINESS_RULE: {"statement", "subject"},
    KnowledgeObjectType.ASSET: {"name"},
}


def _slugify(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return normalized or "knowledge-object"


def _build_search_text(name: str, payload: dict[str, object]) -> str:
    """Search text = name + flattened attributes (spec §5 search_text)."""

    parts: list[str] = [name]
    for key, value in payload.items():
        parts.append(str(key))
        if isinstance(value, dict):
            parts.extend(f"{sub_key} {sub_value}" for sub_key, sub_value in value.items())
        elif isinstance(value, list):
            parts.extend(str(item) for item in value)
        else:
            parts.append(str(value))
    return " ".join(parts)


def _deserialize_relations(relations: Iterable) -> list[dict]:
    items: list[dict] = []
    for relation in relations or []:
        if isinstance(relation, KnowledgeRelation):
            items.append(relation.model_dump())
        elif isinstance(relation, dict):
            items.append(relation)
    return items


def _safe_relations(relations: Iterable) -> list[dict]:
    """Drop stored relations whose predicate is outside the closed list (spec §6.2).

    Rows written before the predicate validator existed can hold predicates the read
    schema rejects; a stored value must never make the read endpoints return 500.
    """

    kept: list[dict] = []
    for relation in _deserialize_relations(relations):
        predicate = relation.get("relation_type") or relation.get("predicate")
        if predicate in RELATION_PREDICATES:
            kept.append(relation)
        else:
            logger.warning("Dropping relation with unknown predicate %r", predicate)
    return kept


def _as_read_model(obj: KnowledgeObject) -> KnowledgeObjectRead:
    return KnowledgeObjectRead.model_validate(
        {
            "id": obj.id,
            "object_type": obj.object_type,
            "object_key": obj.object_key,
            "name": obj.name,
            "payload": obj.payload,
            "relations": _safe_relations(obj.relations),
            "summary": obj.summary,
            "source_excerpt": obj.source_excerpt,
            "schema_version": obj.schema_version,
            "object_version": obj.object_version,
            "is_current": obj.is_current,
            "extraction_method": obj.extraction_method,
            "source_document_id": obj.source_document_id,
            "status": obj.status,
            "visibility": obj.visibility,
            "department_ids": obj.department_ids or [],
            "confidence": obj.confidence,
            "created_by_id": obj.created_by_id,
            "reviewed_by_id": obj.reviewed_by_id,
            "reviewed_at": obj.reviewed_at,
            "review_note": obj.review_note,
            "created_at": obj.created_at,
            "updated_at": obj.updated_at,
        }
    )


def _require_fields(payload: dict[str, object], required_fields: set[str], object_type: KnowledgeObjectType) -> None:
    missing = [field for field in sorted(required_fields) if not payload.get(field)]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Missing required fields for {object_type.value}: {', '.join(missing)}",
        )


def validate_knowledge_payload(object_type: KnowledgeObjectType, payload: dict[str, object]) -> None:
    _require_fields(payload, REQUIRED_ATTRIBUTES[object_type], object_type)
    if object_type == KnowledgeObjectType.POLICY and len(str(payload.get("summary", ""))) > 500:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="policy summary must be 500 characters or fewer",
        )


def _build_object_key(object_type: KnowledgeObjectType, name: str) -> str:
    return f"{object_type.value}:{_slugify(name)}"


def _department_clause(column, department_id: int | None):
    """SQL match of a JSON int-list column against one department id (portable)."""

    if department_id is None:
        return false()
    text = cast(column, String)
    marker = str(department_id)
    return or_(
        text == f"[{marker}]",
        text.like(f"[{marker}, %"),
        text.like(f"%, {marker}, %"),
        text.like(f"%, {marker}]"),
    )


def _visibility_clause(user: User, object_type=None):
    """ACL for reads (spec §9.1/§11): employees only see approved, non-admin-only
    objects they are allowed to see; admins see everything."""

    if user.role == UserRole.ADMIN:
        return true()
    dept_clause = _department_clause(KnowledgeObject.department_ids, user.department_id)
    return and_(
        KnowledgeObject.status == KnowledgeObjectStatus.APPROVED,
        KnowledgeObject.visibility != Visibility.ADMIN_ONLY,
        or_(
            KnowledgeObject.visibility == Visibility.ALL,
            and_(KnowledgeObject.visibility == Visibility.DEPARTMENT, dept_clause),
        ),
    )


def _new_object(
    *,
    object_type: KnowledgeObjectType,
    name: str,
    payload: dict[str, object],
    relations: list[KnowledgeRelation] | None = None,
    summary: str | None = None,
    source_excerpt: str | None = None,
    source_document_id: int | None = None,
) -> KnowledgeObjectCreate:
    relations = relations or []
    validate_knowledge_payload(object_type, payload)
    return KnowledgeObjectCreate(
        object_type=object_type,
        name=name,
        payload=payload,
        relations=relations,
        summary=summary,
        source_excerpt=source_excerpt,
        source_document_id=source_document_id,
    )


def _extract_title(text: str, fallback: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip()
        if len(stripped) > 4:
            return stripped
    return fallback


def _extract_faq_objects(document: Document, lines: list[str]) -> list[KnowledgeObjectCreate]:
    items: list[KnowledgeObjectCreate] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if line.lower().startswith(("q:", "question:")):
            question = line.split(":", 1)[1].strip()
            answer = ""
            cursor = index + 1
            while cursor < len(lines):
                candidate = lines[cursor]
                lowered = candidate.lower()
                if lowered.startswith(("q:", "question:")):
                    break
                if lowered.startswith(("a:", "answer:")):
                    answer = candidate.split(":", 1)[1].strip()
                elif answer:
                    break
                cursor += 1
            if question and answer:
                items.append(
                    _new_object(
                        object_type=KnowledgeObjectType.FAQ,
                        name=question,
                        payload={"question": question, "answer": answer},
                        summary=answer[:240],
                        source_excerpt=f"Q: {question}\nA: {answer}",
                        source_document_id=document.id,
                    )
                )
            index = cursor
            continue
        index += 1
    return items


def _extract_department_objects(document: Document, lines: list[str]) -> list[KnowledgeObjectCreate]:
    items: list[KnowledgeObjectCreate] = []
    for line in lines:
        match = re.match(r"^(department|dept)\s*:\s*(.+)$", line, flags=re.IGNORECASE)
        if not match:
            continue
        department_name = match.group(2).strip()
        items.append(
            _new_object(
                object_type=KnowledgeObjectType.DEPARTMENT,
                name=department_name,
                payload={"name": department_name},
                summary=f"Department extracted from {document.title}",
                source_excerpt=line,
                source_document_id=document.id,
            )
        )
    return items


def _extract_employee_objects(document: Document, text: str) -> list[KnowledgeObjectCreate]:
    items: list[KnowledgeObjectCreate] = []
    pattern = re.compile(
        r"Employee\s*:\s*(?P<name>.+?)(?:\nTitle\s*:\s*(?P<title>.+?))?(?:\nDepartment\s*:\s*(?P<department>.+?))?(?:\nManager\s*:\s*(?P<manager>.+?))?(?:\n|$)",
        flags=re.IGNORECASE,
    )
    for match in pattern.finditer(text):
        name = match.group("name").strip()
        title = (match.group("title") or "").strip()
        department = (match.group("department") or "").strip()
        manager = (match.group("manager") or "").strip()
        relations: list[KnowledgeRelation] = []
        if department:
            relations.append(
                KnowledgeRelation(
                    relation_type="belongs_to",
                    target_type=KnowledgeObjectType.DEPARTMENT,
                    target_name=department,
                    evidence=f"Department: {department}",
                )
            )
        if manager:
            relations.append(
                KnowledgeRelation(
                    relation_type="reports_to",
                    target_type=KnowledgeObjectType.EMPLOYEE,
                    target_name=manager,
                    evidence=f"Manager: {manager}",
                )
            )
        items.append(
            _new_object(
                object_type=KnowledgeObjectType.EMPLOYEE,
                name=name,
                payload={
                    "full_name": name,
                    "job_title": title,
                    "department": department,
                    "reports_to": manager,
                },
                relations=relations,
                summary=f"{name}{f' - {title}' if title else ''}".strip(),
                source_excerpt=match.group(0).strip(),
                source_document_id=document.id,
            )
        )
    return items


def _extract_named_line_objects(
    document: Document,
    lines: list[str],
    prefix: str,
    object_type: KnowledgeObjectType,
    field_name: str = "name",
) -> list[KnowledgeObjectCreate]:
    items: list[KnowledgeObjectCreate] = []
    for line in lines:
        match = re.match(rf"^{re.escape(prefix)}\s*:\s*(.+)$", line, flags=re.IGNORECASE)
        if not match:
            continue
        name = match.group(1).strip()
        items.append(
            _new_object(
                object_type=object_type,
                name=name,
                payload={field_name: name},
                summary=f"{object_type.value.replace('_', ' ').title()} extracted from {document.title}",
                source_excerpt=line,
                source_document_id=document.id,
            )
        )
    return items


def _extract_business_rules(document: Document, lines: list[str], policy_title: str) -> list[KnowledgeObjectCreate]:
    items: list[KnowledgeObjectCreate] = []
    policy_key = _build_object_key(KnowledgeObjectType.POLICY, policy_title)
    for line in lines:
        if len(line) < 12 or not RULE_PATTERN.search(line):
            continue
        rule_name = line[:80]
        relations = [
            KnowledgeRelation(
                relation_type="governed_by",
                target_type=KnowledgeObjectType.POLICY,
                target_name=policy_title,
                evidence=policy_title,
            )
        ]
        items.append(
            _new_object(
                object_type=KnowledgeObjectType.BUSINESS_RULE,
                name=rule_name,
                payload={"statement": line, "subject": policy_title, "policy": policy_key},
                relations=relations,
                summary=line[:240],
                source_excerpt=line,
                source_document_id=document.id,
            )
        )
    return items


def _extract_policy_object(document: Document, text: str, lines: list[str]) -> KnowledgeObjectCreate | None:
    title = _extract_title(text, document.title)
    statements = [line for line in lines if RULE_PATTERN.search(line)]
    if "policy" not in title.lower() and not statements:
        return None
    summary = " ".join(statements[:3])[:500] if statements else title
    return _new_object(
        object_type=KnowledgeObjectType.POLICY,
        name=title,
        payload={
            "title": title,
            "summary": summary,
            "statements": statements[:10],
            "document_title": document.title,
        },
        summary=f"Policy extracted from {document.title}",
        source_excerpt="\n".join(statements[:5]) if statements else title,
        source_document_id=document.id,
    )


def extract_knowledge_candidates(
    document: Document,
) -> tuple[list[KnowledgeObjectCreate], int]:
    """Run the rule-based extractors.

    Returns candidates plus the number of items dropped because they failed
    schema validation (spec §7.4.3: invalid items are dropped and counted —
    they must never crash the pipeline).
    """

    _, clean_text = get_extracted_text(document)
    if not clean_text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Document must have extracted text before knowledge extraction",
        )

    lines = [line.strip() for line in clean_text.splitlines() if line.strip()]
    policy_title = _extract_title(clean_text, document.title)
    raw_candidates: list[KnowledgeObjectCreate] = []
    dropped_invalid = 0

    policy = _extract_policy_object(document, clean_text, lines)
    if policy is not None:
        raw_candidates.append(policy)

    extractors = (
        lambda: _extract_department_objects(document, lines),
        lambda: _extract_employee_objects(document, clean_text),
        lambda: _extract_named_line_objects(document, lines, "Product", KnowledgeObjectType.PRODUCT),
        lambda: _extract_named_line_objects(document, lines, "Asset", KnowledgeObjectType.ASSET),
        lambda: _extract_faq_objects(document, lines),
        lambda: _extract_business_rules(document, lines, policy_title),
    )
    for run in extractors:
        try:
            raw_candidates.extend(run())
        except HTTPException:
            dropped_invalid += 1

    deduped: dict[str, KnowledgeObjectCreate] = {}
    for candidate in raw_candidates:
        deduped[_build_object_key(candidate.object_type, candidate.name)] = candidate
    return list(deduped.values()), dropped_invalid


def _persist_versioned_object(
    db: Session,
    *,
    object_type: KnowledgeObjectType,
    name: str,
    payload: dict[str, object],
    relations: list[KnowledgeRelation] | list[dict],
    summary: str | None,
    source_excerpt: str | None,
    source_document_id: int | None,
    extraction_method: str,
    object_status: KnowledgeObjectStatus,
    visibility: Visibility = Visibility.ALL,
    department_ids: list[int] | None = None,
    created_by_id: int | None = None,
    review_note: str | None = None,
    reviewed_by_id: int | None = None,
) -> tuple[KnowledgeObject, bool]:
    validate_knowledge_payload(object_type, payload)
    object_key = _build_object_key(object_type, name)
    relation_dicts = _deserialize_relations(relations)
    # Live = status in (pending_review, approved); exactly one such row per key
    # (spec §5 partial unique index). Superseded rows are archived history.
    live_statuses = (
        KnowledgeObjectStatus.PENDING_REVIEW,
        KnowledgeObjectStatus.APPROVED,
    )
    existing = (
        db.query(KnowledgeObject)
        .filter(
            KnowledgeObject.object_key == object_key,
            KnowledgeObject.status.in_(live_statuses),
        )
        .first()
    )
    if existing is not None and (
        existing.payload == payload
        and existing.relations == relation_dicts
        and existing.summary == summary
        and existing.source_excerpt == source_excerpt
        and existing.name == name
    ):
        # Spec §6.3: identical facts never fork a new version; the single live
        # object per key is kept (the schema holds one source link per row).
        return existing, False

    max_version = (
        db.query(func.max(KnowledgeObject.object_version)).filter(KnowledgeObject.object_key == object_key).scalar()
        or 0
    )
    next_version = int(max_version) + 1
    if existing is not None:
        # Move the superseded row out of the live set *before* inserting the
        # replacement so the partial unique index is never transiently violated.
        existing.is_current = False
        existing.status = KnowledgeObjectStatus.ARCHIVED
        db.add(existing)
        db.flush()

    knowledge_object = KnowledgeObject(
        object_type=object_type,
        object_key=object_key,
        name=name,
        payload=payload,
        relations=relation_dicts,
        summary=summary,
        source_excerpt=source_excerpt,
        schema_version=SCHEMA_VERSION,
        object_version=next_version,
        is_current=True,
        extraction_method=extraction_method,
        source_document_id=source_document_id,
        status=object_status,
        visibility=visibility,
        department_ids=department_ids or [],
        created_by_id=created_by_id,
        reviewed_by_id=reviewed_by_id,
        reviewed_at=datetime.now(UTC) if (reviewed_by_id or review_note) else None,
        review_note=review_note,
        search_text=_build_search_text(name, payload),
    )
    db.add(knowledge_object)
    db.flush()
    _write_version_snapshot(db, knowledge_object, changed_by_id=reviewed_by_id, change_note=review_note)
    return knowledge_object, existing is not None


def _write_version_snapshot(
    db: Session, obj: KnowledgeObject, *, changed_by_id: int | None, change_note: str | None
) -> None:
    """Snapshot every new version into okf_object_versions (spec §5/§6.3)."""

    db.add(
        KnowledgeObjectVersion(
            okf_object_id=obj.id,
            version=obj.object_version,
            snapshot={
                "type": obj.object_type.value,
                "canonical_key": obj.object_key,
                "name": obj.name,
                "attributes": obj.payload,
                "relations": obj.relations,
                "summary": obj.summary,
                "status": obj.status.value,
                "visibility": obj.visibility.value,
                "department_ids": obj.department_ids or [],
                "version": obj.object_version,
                "schema_version": obj.schema_version,
                "confidence": obj.confidence,
                "source_document_id": obj.source_document_id,
            },
            changed_by_id=changed_by_id,
            change_note=change_note,
            changed_at=datetime.now(UTC),
        )
    )


def extract_knowledge_from_document(db: Session, document_id: int):
    from app.schemas.knowledge import KnowledgeExtractionResponse

    document = get_document_or_404(db, document_id)
    if document.extraction_status != ExtractionStatus.READY:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Document extraction must be ready before Phase 5 knowledge extraction",
        )

    candidates, dropped_invalid = extract_knowledge_candidates(document)
    existing_current = {
        item.object_key: item
        for item in db.query(KnowledgeObject)
        .filter(
            KnowledgeObject.source_document_id == document.id,
            KnowledgeObject.is_current.is_(True),
            KnowledgeObject.extraction_method == "document_extraction",
        )
        .all()
    }

    items: list[KnowledgeObject] = []
    created = 0
    updated = 0
    candidate_keys: set[str] = set()
    # Trusted-source rule (admin toggle on the document): facts extracted from
    # a trusted document are created directly as approved. Everything else
    # waits for admin review per spec §7.4.6
    # (OKF_AUTO_APPROVE_THRESHOLD=1.01 -> never auto-approve).
    trusted = bool(getattr(document, "auto_approve_knowledge", False))
    object_status = KnowledgeObjectStatus.APPROVED if trusted else KnowledgeObjectStatus.PENDING_REVIEW
    auto_review_note = "auto-approved: trusted document" if trusted else None
    for candidate in candidates:
        knowledge_object, was_update = _persist_versioned_object(
            db,
            object_type=candidate.object_type,
            name=candidate.name,
            payload=candidate.payload,
            relations=candidate.relations,
            summary=candidate.summary,
            source_excerpt=candidate.source_excerpt,
            source_document_id=document.id,
            extraction_method="document_extraction",
            object_status=object_status,
            visibility=document.visibility,
            department_ids=list(document.department_ids or []),
            review_note=auto_review_note,
        )
        candidate_keys.add(knowledge_object.object_key)
        items.append(knowledge_object)
        if was_update:
            updated += 1
        elif knowledge_object.object_version == 1:
            created += 1

    archived = 0
    for object_key, existing in existing_current.items():
        if object_key in candidate_keys:
            continue
        # Facts removed from the document are superseded, not left live: the
        # partial unique index admits only one live row per key (spec §5).
        existing.is_current = False
        existing.status = KnowledgeObjectStatus.ARCHIVED
        db.add(existing)
        archived += 1

    db.commit()
    for item in items:
        db.refresh(item)
    return KnowledgeExtractionResponse(
        document_id=document.id,
        created=created,
        updated=updated,
        archived=archived,
        dropped_invalid=dropped_invalid,
        items=[_as_read_model(item) for item in items],
    )


def create_knowledge_object(db: Session, payload: KnowledgeObjectCreate, user: User):
    knowledge_object, _ = _persist_versioned_object(
        db,
        object_type=payload.object_type,
        name=payload.name,
        payload=payload.payload,
        relations=payload.relations,
        summary=payload.summary,
        source_excerpt=payload.source_excerpt,
        source_document_id=payload.source_document_id,
        extraction_method="manual",
        # Spec §8: manually created objects are admin-approved immediately.
        object_status=KnowledgeObjectStatus.APPROVED,
        visibility=payload.visibility,
        department_ids=payload.department_ids,
        created_by_id=user.id,
        reviewed_by_id=user.id,
    )
    db.commit()
    db.refresh(knowledge_object)
    return _as_read_model(knowledge_object)


def get_knowledge_object_or_404(db: Session, knowledge_id: int) -> KnowledgeObject:
    knowledge_object = db.query(KnowledgeObject).filter(KnowledgeObject.id == knowledge_id).first()
    if not knowledge_object:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge object not found")
    return knowledge_object


def read_knowledge_object(db: Session, knowledge_id: int, user: User) -> KnowledgeObjectRead:
    knowledge_object = get_knowledge_object_or_404(db, knowledge_id)
    if not db.query(KnowledgeObject).filter(KnowledgeObject.id == knowledge_id, _visibility_clause(user)).count():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge object not found")
    return _as_read_model(knowledge_object)


def list_knowledge_objects(
    db: Session,
    *,
    user: User,
    object_type: KnowledgeObjectType | None = None,
    document_id: int | None = None,
    include_history: bool = False,
):
    query = db.query(KnowledgeObject)
    if not include_history:
        query = query.filter(KnowledgeObject.is_current.is_(True))
    if object_type is not None:
        query = query.filter(KnowledgeObject.object_type == object_type)
    if document_id is not None:
        query = query.filter(KnowledgeObject.source_document_id == document_id)
    query = query.filter(_visibility_clause(user))
    return [_as_read_model(item) for item in query.order_by(KnowledgeObject.created_at.desc()).all()]


def search_knowledge_objects(
    db: Session,
    *,
    user: User,
    query_text: str,
    object_type: KnowledgeObjectType | None = None,
    document_id: int | None = None,
):
    query = db.query(KnowledgeObject).filter(KnowledgeObject.is_current.is_(True))
    if object_type is not None:
        query = query.filter(KnowledgeObject.object_type == object_type)
    if document_id is not None:
        query = query.filter(KnowledgeObject.source_document_id == document_id)
    query = query.filter(_visibility_clause(user))
    like_value = f"%{query_text.strip()}%"
    query = query.filter(
        or_(
            KnowledgeObject.name.ilike(like_value),
            cast(KnowledgeObject.payload, String).ilike(like_value),
            KnowledgeObject.summary.ilike(like_value),
            KnowledgeObject.source_excerpt.ilike(like_value),
        )
    )
    return [_as_read_model(item) for item in query.order_by(KnowledgeObject.updated_at.desc()).all()]


def list_knowledge_versions(db: Session, knowledge_id: int, user: User):
    knowledge_object = get_knowledge_object_or_404(db, knowledge_id)
    query = (
        db.query(KnowledgeObject)
        .filter(KnowledgeObject.object_key == knowledge_object.object_key)
        .filter(_visibility_clause(user))
        .order_by(KnowledgeObject.object_version.desc())
    )
    return [_as_read_model(item) for item in query.all()]


def update_knowledge_object(db: Session, knowledge_id: int, payload: KnowledgeObjectUpdate, user: User):
    existing = get_knowledge_object_or_404(db, knowledge_id)
    merged_name = payload.name if payload.name is not None else existing.name
    merged_payload = dict(existing.payload)
    if payload.payload is not None:
        merged_payload = payload.payload
    merged_relations = list(existing.relations or [])
    if payload.relations is not None:
        merged_relations = [relation.model_dump() for relation in payload.relations]
    merged_summary = payload.summary if payload.summary is not None else existing.summary
    merged_excerpt = payload.source_excerpt if payload.source_excerpt is not None else existing.source_excerpt

    knowledge_object, _ = _persist_versioned_object(
        db,
        object_type=existing.object_type,
        name=merged_name,
        payload=merged_payload,
        relations=merged_relations,
        summary=merged_summary,
        source_excerpt=merged_excerpt,
        source_document_id=existing.source_document_id,
        extraction_method=existing.extraction_method,
        # Admin edits keep the object's current review state; the mandatory
        # change_note is stored on the new version row (spec §8, audit F-038).
        object_status=existing.status,
        visibility=payload.visibility if payload.visibility is not None else existing.visibility,
        department_ids=(
            payload.department_ids if payload.department_ids is not None else (existing.department_ids or [])
        ),
        created_by_id=existing.created_by_id,
        review_note=payload.change_note,
        reviewed_by_id=user.id,
    )
    db.commit()
    db.refresh(knowledge_object)
    return _as_read_model(knowledge_object)


def delete_knowledge_object(db: Session, knowledge_id: int) -> None:
    """Spec §8 DELETE /knowledge/{id} archives instead of deleting (audit F-011)."""
    knowledge_object = get_knowledge_object_or_404(db, knowledge_id)
    knowledge_object.status = KnowledgeObjectStatus.ARCHIVED
    knowledge_object.is_current = False
    db.add(knowledge_object)
    db.commit()


def _review_knowledge_object(
    db: Session, knowledge_id: int, user: User, new_status: KnowledgeObjectStatus, note: str | None
) -> KnowledgeObjectRead:
    knowledge_object = get_knowledge_object_or_404(db, knowledge_id)
    if not knowledge_object.is_current:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot review a superseded knowledge version",
        )
    knowledge_object.status = new_status
    knowledge_object.reviewed_by_id = user.id
    knowledge_object.reviewed_at = datetime.now(UTC)
    knowledge_object.review_note = note
    db.add(knowledge_object)
    db.commit()
    db.refresh(knowledge_object)
    return _as_read_model(knowledge_object)


def approve_knowledge_object(db: Session, knowledge_id: int, user: User, note: str | None = None):
    return _review_knowledge_object(db, knowledge_id, user, KnowledgeObjectStatus.APPROVED, note)


def reject_knowledge_object(db: Session, knowledge_id: int, user: User, note: str | None = None):
    return _review_knowledge_object(db, knowledge_id, user, KnowledgeObjectStatus.REJECTED, note)


def bulk_review_knowledge_objects(
    db: Session, ids: list[int], action: str, user: User, note: str | None = None
) -> tuple[int, list[KnowledgeObjectRead]]:
    new_status = KnowledgeObjectStatus.APPROVED if action == "approve" else KnowledgeObjectStatus.REJECTED
    reviewed: list[KnowledgeObjectRead] = []
    for knowledge_id in ids:
        reviewed.append(_review_knowledge_object(db, knowledge_id, user, new_status, note))
    return len(reviewed), reviewed


def approve_pending_for_document(
    db: Session,
    document_id: int,
    *,
    reviewed_by_id: int | None,
    note: str,
) -> int:
    """Approve every current pending_review object extracted from one document.

    Used when an admin marks a document as a trusted source: previously
    extracted facts that were still waiting for review are approved in bulk
    (each recording who enabled the trust and why). Returns the count.
    """

    pending = (
        db.query(KnowledgeObject)
        .filter(
            KnowledgeObject.source_document_id == document_id,
            KnowledgeObject.status == KnowledgeObjectStatus.PENDING_REVIEW,
            KnowledgeObject.is_current.is_(True),
        )
        .all()
    )
    now = datetime.now(UTC)
    for knowledge_object in pending:
        knowledge_object.status = KnowledgeObjectStatus.APPROVED
        knowledge_object.reviewed_by_id = reviewed_by_id
        knowledge_object.reviewed_at = now
        knowledge_object.review_note = note
        db.add(knowledge_object)
    if pending:
        db.commit()
        for knowledge_object in pending:
            db.refresh(knowledge_object)
    return len(pending)
