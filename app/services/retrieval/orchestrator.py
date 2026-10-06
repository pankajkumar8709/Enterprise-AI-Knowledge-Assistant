"""Retrieval orchestrator (spec §9).

Single entry point: `retrieve(db, user, query, history)` → `RetrievalResult`.

Wires together:
  query_rewrite → classifier → vector+FTS (RAG) → OKF search → merger
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.models.user import User
from app.services.classifier import ClassifierResult, classify_query
from app.services.embeddings import embed_query
from app.services.query_rewrite import rewrite_query
from app.services.retrieval.fulltext import fulltext_search
from app.services.retrieval.fusion import ChunkResult, rrf_fuse
from app.services.retrieval.merger import ContextItem, merge
from app.services.retrieval.okf_search import OKFResult, okf_search
from app.services.retrieval.vector import vector_search

logger = logging.getLogger(__name__)


@dataclass
class RetrievalResult:
    route: str  # "structured" | "document" | "mixed"
    rewritten_query: str
    classifier: ClassifierResult
    context: list[ContextItem]
    chunk_results: list[ChunkResult] = field(default_factory=list)
    okf_results: list[OKFResult] = field(default_factory=list)


def retrieve(
    db: Session,
    user: User,
    query: str,
    history: list[dict[str, str]] | None = None,
    *,
    document_ids: list[int] | None = None,
) -> RetrievalResult:
    """Full retrieval pipeline for one user query.

    *history* is a list of ``{"role": "user"|"assistant", "content": "..."}``
    dicts (most-recent last) used for query rewriting.
    """
    history = history or []

    # 1. Rewrite follow-up questions into standalone queries.
    rewritten = rewrite_query(query, history)
    logger.debug("retrieve: original=%r rewritten=%r", query, rewritten)

    # 2. Classify the (rewritten) query.
    classification = classify_query(rewritten)
    route = classification.route
    logger.debug("retrieve: route=%s confidence=%.2f", route, classification.confidence)

    # 3. Run retrieval paths based on route.
    chunk_results: list[ChunkResult] = []
    okf_results: list[OKFResult] = []

    run_rag = route in ("document", "mixed")
    run_okf = route in ("structured", "mixed")

    # Safety net (spec §9.5): structured with 0 OKF hits → also run RAG.
    # We always run OKF first when structured so we can check the hit count.
    if run_okf:
        okf_results = okf_search(
            db,
            rewritten,
            user,
            type_hints=classification.entity_hints or None,
        )
        if route == "structured" and not okf_results:
            logger.debug("retrieve: structured but 0 OKF hits → adding RAG")
            run_rag = True

    if run_rag:
        try:
            qvec = embed_query(rewritten)
        except Exception as exc:
            logger.warning("retrieve: embedding failed (%s), skipping vector search", exc)
            qvec = []

        if qvec:
            vec_results = vector_search(db, qvec, user, document_ids=document_ids)
            fts_results = fulltext_search(db, rewritten, user, document_ids=document_ids)
            chunk_results = rrf_fuse(db, qvec, vec_results, fts_results, user)
        else:
            # Embedding unavailable: fall back to FTS only.
            fts_results = fulltext_search(db, rewritten, user, document_ids=document_ids)
            chunk_results = rrf_fuse(db, [], [], fts_results, user)

    # 4. Merge into a single ranked context list.
    context = merge(route, chunk_results, okf_results)

    return RetrievalResult(
        route=route,
        rewritten_query=rewritten,
        classifier=classification,
        context=context,
        chunk_results=chunk_results,
        okf_results=okf_results,
    )
