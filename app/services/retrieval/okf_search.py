"""OKF knowledge search (spec §9.3).

Searches approved, in-validity-window OKF objects using pg_trgm similarity
and tsvector full-text ranking. ACL is applied inside SQL. The top-3 results
are expanded by one relation hop (spec §9.3 step 4).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date

from sqlalchemy import ColumnElement, Float, String, case, cast, func, literal, or_
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.knowledge import KnowledgeObject, KnowledgeObjectStatus, KnowledgeObjectType
from app.models.knowledge_edge import KnowledgeObjectRelation
from app.models.user import User
from app.services.knowledge import _visibility_clause  # reuse existing ACL helper

logger = logging.getLogger(__name__)


@dataclass
class OKFResult:
    okf_id: int
    object_type: str
    name: str
    canonical_key: str
    attributes: dict
    score: float
    source_document_id: int | None
    visibility: str
    department_ids: list[int]
    confidence: float | None
    # True when this result came from relation expansion, not direct search.
    via_relation: bool = False
    relation_predicate: str | None = None


def _base_acl_validity_filter(user: User, today: date):
    """Approved + in-validity-window + ACL (spec §9.3)."""
    return [
        KnowledgeObject.status == KnowledgeObjectStatus.APPROVED,
        KnowledgeObject.is_current.is_(True),
        or_(KnowledgeObject.valid_to.is_(None), KnowledgeObject.valid_to >= today),
        _visibility_clause(user),
    ]


def okf_search(
    db: Session,
    query: str,
    user: User,
    *,
    type_hints: list[str] | None = None,
    top_k: int | None = None,
) -> list[OKFResult]:
    """Return scored OKF results for *query* with 1-hop relation expansion.

    Falls back to an empty list on non-PostgreSQL dialects (trgm is PG-only).
    """
    k = top_k or settings.okf_top_k
    today = date.today()

    # Guard: pg_trgm is PG-only.
    if db.bind is not None and "sqlite" in str(db.bind.dialect.name):  # type: ignore[union-attr]
        return []

    # --- Scoring (spec §9.3 step 2) ---
    # score = 0.5*trgm_sim + 0.4*min(1, ts_rank_cd*2) + 0.1*type_boost
    trgm_sim = func.similarity(KnowledgeObject.search_text, query).cast(Float)
    tsquery = func.websearch_to_tsquery("english", query)
    fts_rank = func.ts_rank_cd(KnowledgeObject.search_tsv, tsquery).cast(Float)

    # type_boost: 1 if the object type is in the classifier's hinted types.
    # CASE (not CAST(boolean AS FLOAT)) — PostgreSQL cannot cast boolean to
    # double precision, which made every OKF-scored query fail to compile.
    hint_set = set(type_hints or [])
    type_boost: ColumnElement[float]
    if hint_set:
        type_boost = cast(
            case(
                (KnowledgeObject.object_type.in_(list(hint_set)), 1),
                else_=0,
            ),
            Float,
        )
    else:
        type_boost = literal(0.0)

    score_expr = (
        0.5 * trgm_sim
        + 0.4 * func.least(literal(1.0), fts_rank * 2)
        + 0.1 * type_boost
    ).label("score")

    # --- Candidate filter (spec §9.3 step 1) ---
    trgm_threshold = func.similarity(KnowledgeObject.search_text, query) >= 0.2
    fts_match = KnowledgeObject.search_tsv.op("@@")(tsquery)

    filters = _base_acl_validity_filter(user, today)
    filters.append(or_(trgm_threshold, fts_match))

    if type_hints:
        filters.append(KnowledgeObject.object_type.in_(type_hints))

    rows = (
        db.query(KnowledgeObject, score_expr)
        .filter(*filters)
        .order_by(score_expr.desc())
        .limit(k)
        .all()
    )

    results: list[OKFResult] = []
    for obj, score in rows:
        if float(score) < settings.okf_min_score:
            continue
        results.append(_to_result(obj, float(score)))

    # --- 1-hop relation expansion (spec §9.3 step 4) ---
    if results:
        results = _expand_relations(db, results, user, today, k)

    return results


def _to_result(obj: KnowledgeObject, score: float, *, via_relation: bool = False, predicate: str | None = None) -> OKFResult:
    return OKFResult(
        okf_id=obj.id,
        object_type=obj.object_type.value,
        name=obj.name,
        canonical_key=obj.object_key,
        attributes=obj.payload or {},
        score=score,
        source_document_id=obj.source_document_id,
        visibility=obj.visibility.value,
        department_ids=list(obj.department_ids or []),
        confidence=obj.confidence,
        via_relation=via_relation,
        relation_predicate=predicate,
    )


def _expand_relations(
    db: Session,
    direct: list[OKFResult],
    user: User,
    today: date,
    k: int,
) -> list[OKFResult]:
    """Load approved 1-hop neighbours for the top-3 direct results (spec §9.3 step 4).

    Neighbour score = parent_score × 0.6; max 5 extra; deduplicated.
    """
    top3_ids = [r.okf_id for r in direct[:3]]
    existing_ids = {r.okf_id for r in direct}

    # Both directions: subject→object and object→subject.
    edges = (
        db.query(KnowledgeObjectRelation)
        .filter(
            or_(
                KnowledgeObjectRelation.subject_id.in_(top3_ids),
                KnowledgeObjectRelation.object_id.in_(top3_ids),
            ),
            KnowledgeObjectRelation.status == KnowledgeObjectStatus.APPROVED,
        )
        .limit(20)
        .all()
    )

    parent_score: dict[int, tuple[float, str]] = {}
    neighbour_ids: list[int] = []
    for edge in edges:
        if edge.subject_id in top3_ids:
            nid = edge.object_id
        else:
            nid = edge.subject_id
        if nid not in existing_ids and nid not in parent_score:
            # Find the parent score.
            for r in direct[:3]:
                if r.okf_id == edge.subject_id or r.okf_id == edge.object_id:
                    parent_score[nid] = (r.score, edge.predicate)
                    break
            neighbour_ids.append(nid)

    if not neighbour_ids:
        return direct

    acl_filters = _base_acl_validity_filter(user, today)
    neighbours = (
        db.query(KnowledgeObject)
        .filter(KnowledgeObject.id.in_(neighbour_ids[:5]), *acl_filters)
        .all()
    )

    expanded = list(direct)
    for obj in neighbours:
        ps, pred = parent_score.get(obj.id, (0.0, None))
        expanded.append(_to_result(obj, round(ps * 0.6, 4), via_relation=True, predicate=pred))

    return expanded
