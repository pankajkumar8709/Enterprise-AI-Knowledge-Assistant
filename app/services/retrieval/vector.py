"""Vector similarity search (spec §9.2).

Runs an HNSW cosine-distance query against `document_chunks.embedding` with
the ACL clause applied inside SQL. Returns at most `VECTOR_TOP_K` results
ordered by similarity descending.
"""

from __future__ import annotations

import logging

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.chunk import Chunk
from app.models.user import User
from app.services.retrieval.acl import acl_clause

logger = logging.getLogger(__name__)


def vector_search(
    db: Session,
    query_vector: list[float],
    user: User,
    *,
    document_ids: list[int] | None = None,
    top_k: int | None = None,
) -> list[tuple[int, float]]:
    """Return ``[(chunk_id, similarity), ...]`` ordered by similarity desc.

    *similarity* = 1 − cosine_distance (range 0–1).
    Only chunks with ``similarity >= settings.min_similarity`` are returned.
    """
    k = top_k or settings.vector_top_k

    # Guard: Vector column and SET LOCAL are PG-only.
    if db.bind is not None and "sqlite" in str(db.bind.dialect.name):  # type: ignore[union-attr]
        return []

    # Set HNSW ef_search for recall quality (spec §9.2).
    db.execute(text("SET LOCAL hnsw.ef_search = 100"))

    q = (
        db.query(
            Chunk.id,
            (1 - Chunk.embedding.cosine_distance(query_vector)).label("similarity"),
        )
        .filter(
            Chunk.embedding.is_not(None),
            acl_clause(user, Chunk),
        )
    )

    if document_ids:
        q = q.filter(Chunk.document_id.in_(document_ids))

    rows = (
        q.order_by(Chunk.embedding.cosine_distance(query_vector))
        .limit(k)
        .all()
    )

    return [
        (row.id, float(row.similarity))
        for row in rows
        if float(row.similarity) >= settings.min_similarity
    ]
