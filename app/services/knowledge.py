from __future__ import annotations

import json
import re
from collections.abc import Iterable

from fastapi import HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.document import Document, ExtractionStatus
from app.models.knowledge import KnowledgeObject, KnowledgeObjectType
from app.schemas.knowledge import KnowledgeObjectCreate, KnowledgeObjectRead, KnowledgeObjectUpdate, KnowledgeRelation
from app.services.documents import get_document_or_404
from app.services.extraction import get_extracted_text

SCHEMA_VERSION = 1
RULE_PATTERN = re.compile(r"\b(must|should|shall|required|not allowed|prohibited|only)\b", flags=re.IGNORECASE)


def _slugify(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return normalized or "knowledge-object"


def _serialize_payload(payload: dict[str, object]) -> str:
    return json.dumps(payload, ensure_ascii=True, sort_keys=True)


def _serialize_relations(relations: Iterable[KnowledgeRelation]) -> str:
    return json.dumps([relation.model_dump() for relation in relations], ensure_ascii=True, sort_keys=True)


def _deserialize_payload(payload: str) -> dict[str, object]:
    return json.loads(payload)


def _deserialize_relations(relations: str) -> list[KnowledgeRelation]:
    raw_items = json.loads(relations or "[]")
    return [KnowledgeRelation.model_validate(item) for item in raw_items]


def _as_read_model(obj: KnowledgeObject) -> KnowledgeObjectRead:
    return KnowledgeObjectRead.model_validate(
        {
            "id": obj.id,
            "object_type": obj.object_type,
            "object_key": obj.object_key,
            "name": obj.name,
            "payload": _deserialize_payload(obj.payload),
            "relations": _deserialize_relations(obj.relations),
            "summary": obj.summary,
            "source_excerpt": obj.source_excerpt,
            "schema_version": obj.schema_version,
            "object_version": obj.object_version,
            "is_current": obj.is_current,
            "extraction_method": obj.extraction_method,
            "source_document_id": obj.source_document_id,
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
    match object_type:
        case KnowledgeObjectType.POLICY:
            _require_fields(payload, {"title"}, object_type)
        case KnowledgeObjectType.EMPLOYEE:
            _require_fields(payload, {"full_name"}, object_type)
        case KnowledgeObjectType.DEPARTMENT:
            _require_fields(payload, {"name"}, object_type)
        case KnowledgeObjectType.PRODUCT:
            _require_fields(payload, {"name"}, object_type)
        case KnowledgeObjectType.FAQ:
            _require_fields(payload, {"question", "answer"}, object_type)
        case KnowledgeObjectType.BUSINESS_RULE:
            _require_fields(payload, {"rule"}, object_type)
        case KnowledgeObjectType.ASSET:
            _require_fields(payload, {"name"}, object_type)


def _build_object_key(object_type: KnowledgeObjectType, name: str) -> str:
    return f"{object_type.value}:{_slugify(name)}"


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
                    relation_type="member_of",
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
                    "title": title or None,
                    "department": department or None,
                    "manager": manager or None,
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
    for line in lines:
        if len(line) < 12 or not RULE_PATTERN.search(line):
            continue
        rule_name = line[:80]
        relations = [
            KnowledgeRelation(
                relation_type="derived_from",
                target_type=KnowledgeObjectType.POLICY,
                target_name=policy_title,
                evidence=policy_title,
            )
        ]
        items.append(
            _new_object(
                object_type=KnowledgeObjectType.BUSINESS_RULE,
                name=rule_name,
                payload={"rule": line, "policy": policy_title},
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
    return _new_object(
        object_type=KnowledgeObjectType.POLICY,
        name=title,
        payload={"title": title, "statements": statements[:10], "document_title": document.title},
        summary=f"Policy extracted from {document.title}",
        source_excerpt="\n".join(statements[:5]) if statements else title,
        source_document_id=document.id,
    )


def extract_knowledge_candidates(document: Document) -> list[KnowledgeObjectCreate]:
    _, clean_text = get_extracted_text(document)
    if not clean_text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Document must have extracted text before knowledge extraction",
        )

    lines = [line.strip() for line in clean_text.splitlines() if line.strip()]
    policy_title = _extract_title(clean_text, document.title)
    candidates: list[KnowledgeObjectCreate] = []

    policy = _extract_policy_object(document, clean_text, lines)
    if policy is not None:
        candidates.append(policy)

    candidates.extend(_extract_department_objects(document, lines))
    candidates.extend(_extract_employee_objects(document, clean_text))
    candidates.extend(_extract_named_line_objects(document, lines, "Product", KnowledgeObjectType.PRODUCT))
    candidates.extend(_extract_named_line_objects(document, lines, "Asset", KnowledgeObjectType.ASSET))
    candidates.extend(_extract_faq_objects(document, lines))
    candidates.extend(_extract_business_rules(document, lines, policy_title))

    deduped: dict[str, KnowledgeObjectCreate] = {}
    for candidate in candidates:
        deduped[_build_object_key(candidate.object_type, candidate.name)] = candidate
    return list(deduped.values())


def _persist_versioned_object(
    db: Session,
    *,
    object_type: KnowledgeObjectType,
    name: str,
    payload: dict[str, object],
    relations: list[KnowledgeRelation],
    summary: str | None,
    source_excerpt: str | None,
    source_document_id: int | None,
    extraction_method: str,
) -> tuple[KnowledgeObject, bool]:
    validate_knowledge_payload(object_type, payload)
    object_key = _build_object_key(object_type, name)
    serialized_payload = _serialize_payload(payload)
    serialized_relations = _serialize_relations(relations)
    query = db.query(KnowledgeObject).filter(
        KnowledgeObject.object_key == object_key,
        KnowledgeObject.is_current.is_(True),
    )
    if source_document_id is None:
        query = query.filter(KnowledgeObject.source_document_id.is_(None))
    else:
        query = query.filter(KnowledgeObject.source_document_id == source_document_id)
    existing = query.first()
    if existing and (
        existing.payload == serialized_payload
        and existing.relations == serialized_relations
        and existing.summary == summary
        and existing.source_excerpt == source_excerpt
        and existing.source_document_id == source_document_id
        and existing.name == name
    ):
        return existing, False

    next_version = 1
    if existing:
        existing.is_current = False
        db.add(existing)
        next_version = existing.object_version + 1

    knowledge_object = KnowledgeObject(
        object_type=object_type,
        object_key=object_key,
        name=name,
        payload=serialized_payload,
        relations=serialized_relations,
        summary=summary,
        source_excerpt=source_excerpt,
        schema_version=SCHEMA_VERSION,
        object_version=next_version,
        is_current=True,
        extraction_method=extraction_method,
        source_document_id=source_document_id,
    )
    db.add(knowledge_object)
    db.flush()
    return knowledge_object, existing is not None


def extract_knowledge_from_document(db: Session, document_id: int):
    from app.schemas.knowledge import KnowledgeExtractionResponse

    document = get_document_or_404(db, document_id)
    if document.extraction_status != ExtractionStatus.READY:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Document extraction must be ready before Phase 5 knowledge extraction",
        )

    candidates = extract_knowledge_candidates(document)
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
        existing.is_current = False
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
        items=[_as_read_model(item) for item in items],
    )


def create_knowledge_object(db: Session, payload: KnowledgeObjectCreate):
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
    )
    db.commit()
    db.refresh(knowledge_object)
    return _as_read_model(knowledge_object)


def get_knowledge_object_or_404(db: Session, knowledge_id: int) -> KnowledgeObject:
    knowledge_object = db.query(KnowledgeObject).filter(KnowledgeObject.id == knowledge_id).first()
    if not knowledge_object:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge object not found")
    return knowledge_object


def read_knowledge_object(db: Session, knowledge_id: int) -> KnowledgeObjectRead:
    return _as_read_model(get_knowledge_object_or_404(db, knowledge_id))


def list_knowledge_objects(
    db: Session,
    *,
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
    return [_as_read_model(item) for item in query.order_by(KnowledgeObject.created_at.desc()).all()]


def search_knowledge_objects(
    db: Session,
    *,
    query_text: str,
    object_type: KnowledgeObjectType | None = None,
    document_id: int | None = None,
):
    query = db.query(KnowledgeObject).filter(KnowledgeObject.is_current.is_(True))
    if object_type is not None:
        query = query.filter(KnowledgeObject.object_type == object_type)
    if document_id is not None:
        query = query.filter(KnowledgeObject.source_document_id == document_id)
    like_value = f"%{query_text.strip()}%"
    query = query.filter(
        or_(
            KnowledgeObject.name.ilike(like_value),
            KnowledgeObject.payload.ilike(like_value),
            KnowledgeObject.summary.ilike(like_value),
            KnowledgeObject.source_excerpt.ilike(like_value),
        )
    )
    return [_as_read_model(item) for item in query.order_by(KnowledgeObject.updated_at.desc()).all()]


def list_knowledge_versions(db: Session, knowledge_id: int):
    knowledge_object = get_knowledge_object_or_404(db, knowledge_id)
    query = (
        db.query(KnowledgeObject)
        .filter(KnowledgeObject.object_key == knowledge_object.object_key)
        .order_by(KnowledgeObject.object_version.desc())
    )
    return [_as_read_model(item) for item in query.all()]


def update_knowledge_object(db: Session, knowledge_id: int, payload: KnowledgeObjectUpdate):
    existing = get_knowledge_object_or_404(db, knowledge_id)
    merged_name = payload.name if payload.name is not None else existing.name
    merged_payload = _deserialize_payload(existing.payload)
    if payload.payload is not None:
        merged_payload = payload.payload
    merged_relations = _deserialize_relations(existing.relations)
    if payload.relations is not None:
        merged_relations = payload.relations
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
    )
    db.commit()
    db.refresh(knowledge_object)
    return _as_read_model(knowledge_object)


def delete_knowledge_object(db: Session, knowledge_id: int) -> None:
    knowledge_object = get_knowledge_object_or_404(db, knowledge_id)
    siblings = db.query(KnowledgeObject).filter(KnowledgeObject.object_key == knowledge_object.object_key).all()
    for sibling in siblings:
        db.delete(sibling)
    db.commit()
