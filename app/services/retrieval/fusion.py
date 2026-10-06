"""Reciprocal Rank Fusion (spec §9.2).

Merges vector-search and full-text-search result lists into a single ranked
list. Chunks found only by FTS get their cosine similarity computed in a
second query so the eligibility floor (`MIN_SIMILARITY`) can be applied
uniformly.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.chunk import Chunk
from app.models.document import Document
from app.models.user import User

logger = logging.getLogger(__name__)


@dataclass
class ChunkResult:
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
    source_filename: str
    doc_uploaded_at: datetime | None = field(default=None)


def rrf_fuse(
    db: Session,
    query_vector: list[float],
    vec_results: list[tuple[int, float]],
    fts_results: list[tuple[int, float]],
    user: User,
) -> list[ChunkResult]:
    """Fuse *vec_results* and *fts_results* via RRF and return enriched results.

    Steps (spec §9.2):
    1. Compute RRF scores from both ranked lists.
    2. For FTS-only hits, fetch their cosine similarity.
    3. Drop any chunk with similarity < MIN_SIMILARITY.
    4. Return top FINAL_CHUNKS ordered by RRF score.
    """
    k = settings.rrf_k

    vec_map: dict[int, float] = dict(vec_results)
    fts_map: dict[int, float] = dict(fts_results)

    rrf_scores: dict[int, float] = defaultdict(float)
    for rank, (cid, _) in enumerate(vec_results, 1):
        rrf_scores[cid] += 1.0 / (k + rank)
    for rank, (cid, _) in enumerate(fts_results, 1):
        rrf_scores[cid] += 1.0 / (k + rank)

    all_ids = list(rrf_scores.keys())
    if not all_ids:
        return []

    # Fetch similarity for FTS-only hits (not in vec_map).
    fts_only_ids = [cid for cid in all_ids if cid not in vec_map]
    if fts_only_ids and query_vector:
        from app.models.chunk import Chunk as _Chunk  # noqa: PLC0415

        rows = (
            db.query(
                _Chunk.id,
                (1 - _Chunk.embedding.cosine_distance(query_vector)).label("sim"),
            )
            .filter(_Chunk.id.in_(fts_only_ids), _Chunk.embedding.is_not(None))
            .all()
        )
        for row in rows:
            vec_map[row.id] = float(row.sim)

    # Filter by MIN_SIMILARITY; chunks with no embedding get sim=0.
    eligible = {
        cid: vec_map.get(cid, 0.0)
        for cid in all_ids
        if vec_map.get(cid, 0.0) >= settings.min_similarity
    }
    if not eligible:
        return []

    # Sort by RRF score and take top FINAL_CHUNKS.
    ranked = sorted(eligible.keys(), key=lambda cid: rrf_scores[cid], reverse=True)
    top_ids = ranked[: settings.final_chunks]

    # Bulk-load chunk + document metadata.
    chunks = (
        db.query(Chunk, Document.title)
        .join(Document, Chunk.document_id == Document.id)
        .filter(Chunk.id.in_(top_ids))
        .all()
    )
    chunk_map: dict[int, tuple[Chunk, str]] = {c.id: (c, title) for c, title in chunks}

    results: list[ChunkResult] = []
    for cid in top_ids:
        if cid not in chunk_map:
            continue
        chunk, doc_title = chunk_map[cid]
        results.append(
            ChunkResult(
                chunk_id=cid,
                document_id=chunk.document_id,
                document_title=doc_title,
                page_start=chunk.page_number,
                section_title=chunk.section_title,
                content=chunk.text,
                token_count=chunk.token_count,
                similarity=eligible[cid],
                fts_rank=fts_map.get(cid, 0.0),
                rrf_score=rrf_scores[cid],
                source_filename=chunk.source_file_name,
                doc_uploaded_at=chunk.upload_date,
            )
        )

    return results
