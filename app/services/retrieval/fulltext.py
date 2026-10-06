"""Full-text search (spec §9.2).

Uses the generated `tsv` tsvector column on `document_chunks` with
`websearch_to_tsquery` and `ts_rank_cd`. The ACL clause is applied inside SQL.
"""

from __future__ import annotations

import logging

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.chunk import Chunk
from app.models.user import User
from app.services.retrieval.acl import acl_clause

logger = logging.getLogger(__name__)


def fulltext_search(
    db: Session,
    query: str,
    user: User,
    *,
    document_ids: list[int] | None = None,
    top_k: int | None = None,
) -> list[tuple[int, float]]:
    """Return ``[(chunk_id, fts_rank), ...]`` ordered by rank desc.

    Falls back to an empty list when the dialect is not PostgreSQL (e.g. SQLite
    in tests) since `websearch_to_tsquery` is PG-only.
    """
    k = top_k or settings.fts_top_k

    # Guard: tsv column is NULL on non-PG dialects.
    if db.bind is not None and "sqlite" in str(db.bind.dialect.name):  # type: ignore[union-attr]
        return []

    tsquery = func.websearch_to_tsquery("english", query)
    rank = func.ts_rank_cd(Chunk.tsv, tsquery)

    q = (
        db.query(Chunk.id, rank.label("fts_rank"))
        .filter(
            Chunk.tsv.op("@@")(tsquery),
            acl_clause(user, Chunk),
        )
    )

    if document_ids:
        q = q.filter(Chunk.document_id.in_(document_ids))

    rows = q.order_by(rank.desc()).limit(k).all()
    return [(row.id, float(row.fts_rank)) for row in rows]
