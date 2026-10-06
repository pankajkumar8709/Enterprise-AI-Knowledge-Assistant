"""Search endpoints (spec §8):
  POST /search/semantic  — hybrid vector+FTS chunk search (Phase 6)
  POST /search/okf       — OKF knowledge search (Phase 7)
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.services.embeddings import embed_query
from app.services.retrieval.fulltext import fulltext_search
from app.services.retrieval.fusion import ChunkResult, rrf_fuse
from app.services.retrieval.okf_search import OKFResult, okf_search
from app.services.retrieval.vector import vector_search

router = APIRouter()


class SemanticSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=6, ge=1, le=20)
    document_ids: list[int] | None = None


class SemanticSearchResult(BaseModel):
    chunk_id: int
    document_id: int
    document_title: str
    page_start: int | None
    section_title: str | None
    content: str
    token_count: int | None
    similarity: float
    fts_rank: float
    rrf_score: float


@router.post("/semantic", response_model=list[SemanticSearchResult], status_code=status.HTTP_200_OK)
def semantic_search(
    payload: SemanticSearchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[SemanticSearchResult]:
    """Hybrid vector + full-text search with RRF fusion (spec §9.2).

    ACL is enforced inside SQL — employees never receive chunks outside their
    visibility scope.
    """
    try:
        qvec = embed_query(payload.query)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Embedding model unavailable: {exc}",
        ) from exc

    vec_results = vector_search(
        db,
        qvec,
        current_user,
        document_ids=payload.document_ids,
        top_k=payload.top_k * 3,  # over-fetch before fusion
    )
    fts_results = fulltext_search(
        db,
        payload.query,
        current_user,
        document_ids=payload.document_ids,
        top_k=payload.top_k * 3,
    )

    fused: list[ChunkResult] = rrf_fuse(db, qvec, vec_results, fts_results, current_user)
    # Honour the caller's top_k (rrf_fuse already caps at FINAL_CHUNKS).
    fused = fused[: payload.top_k]

    return [
        SemanticSearchResult(
            chunk_id=r.chunk_id,
            document_id=r.document_id,
            document_title=r.document_title,
            page_start=r.page_start,
            section_title=r.section_title,
            content=r.content,
            token_count=r.token_count,
            similarity=round(r.similarity, 4),
            fts_rank=round(r.fts_rank, 4),
            rrf_score=round(r.rrf_score, 6),
        )
        for r in fused
    ]


# ---------------------------------------------------------------------------
# OKF knowledge search (Phase 7 — spec §9.3)
# ---------------------------------------------------------------------------


class OKFSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=8, ge=1, le=20)
    type_hints: list[str] | None = None


class OKFSearchResult(BaseModel):
    okf_id: int
    object_type: str
    name: str
    canonical_key: str
    attributes: dict
    score: float
    source_document_id: int | None
    confidence: float | None
    via_relation: bool
    relation_predicate: str | None


@router.post("/okf", response_model=list[OKFSearchResult], status_code=status.HTTP_200_OK)
def okf_knowledge_search(
    payload: OKFSearchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[OKFSearchResult]:
    """OKF knowledge search with trgm + FTS scoring and 1-hop expansion (spec §9.3).

    ACL is enforced inside SQL. Only approved, in-validity-window objects are
    returned. Employees never receive admin_only or other-department objects.
    """
    results: list[OKFResult] = okf_search(
        db,
        payload.query,
        current_user,
        type_hints=payload.type_hints,
        top_k=payload.top_k,
    )
    return [
        OKFSearchResult(
            okf_id=r.okf_id,
            object_type=r.object_type,
            name=r.name,
            canonical_key=r.canonical_key,
            attributes=r.attributes,
            score=round(r.score, 4),
            source_document_id=r.source_document_id,
            confidence=r.confidence,
            via_relation=r.via_relation,
            relation_predicate=r.relation_predicate,
        )
        for r in results
    ]
