"""Embedding service (spec §7.2 embedding stage, §9.2).

The SentenceTransformer model is loaded once per process (lazy, thread-safe
after the first call). Vectors are L2-normalised so cosine similarity equals
dot product, matching the HNSW `vector_cosine_ops` index.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

from app.core.config import settings

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

_model: SentenceTransformer | None = None


def get_model() -> SentenceTransformer:
    global _model  # noqa: PLW0603
    if _model is None:
        from sentence_transformers import SentenceTransformer  # noqa: PLC0415

        logger.info("loading embedding model %s", settings.embedding_model)
        _model = SentenceTransformer(settings.embedding_model)
        logger.info("embedding model loaded")
    return _model


def embed_texts(texts: list[str], *, is_query: bool = False) -> list[list[float]]:
    """Return L2-normalised vectors for *texts*.

    Query strings are prefixed per spec §4 `QUERY_EMBED_PREFIX`; chunk strings
    are embedded as-is (the prefix is applied at index time in the ingestion
    pipeline via the document title + section title prefix — spec §7.3 step 6).
    """
    if not texts:
        return []
    model = get_model()
    if is_query:
        texts = [settings.query_embed_prefix + t for t in texts]
    vectors = model.encode(
        texts,
        batch_size=settings.embedding_batch,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    return [v.tolist() for v in vectors]


def embed_query(query: str) -> list[float]:
    return embed_texts([query], is_query=True)[0]


def embed_chunk_text(document_title: str, section_title: str | None, content: str) -> list[float]:
    """Build the indexed string (spec §7.3 step 6) and embed it."""
    prefix = f"{document_title} > {section_title}\n" if section_title else f"{document_title}\n"
    return embed_texts([prefix + content])[0]


# ---------------------------------------------------------------------------
# Ingestion helper — embed all pending chunks for one document version
# ---------------------------------------------------------------------------

def embed_document_chunks(db: Session, document_id: int, version: int) -> int:
    """Embed every chunk for *document_id*/*version* that has no embedding yet.

    Returns the number of chunks embedded. Raises on model/DB errors so the
    ingestion pipeline can mark the job failed and retry.
    """
    from app.models.chunk import Chunk  # noqa: PLC0415
    from app.models.document import Document  # noqa: PLC0415

    document = db.query(Document).filter(Document.id == document_id).first()
    if document is None:
        raise ValueError(f"document {document_id} not found")

    chunks = (
        db.query(Chunk)
        .filter(
            Chunk.document_id == document_id,
            Chunk.version == version,
            Chunk.embedding.is_(None),
        )
        .order_by(Chunk.chunk_index)
        .all()
    )
    if not chunks:
        return 0

    batch_size = settings.embedding_batch
    embedded = 0
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i : i + batch_size]
        texts = [
            embed_chunk_text(document.title, c.section_title, c.text)
            for c in batch
        ]
        vectors = embed_texts(texts)
        for chunk, vec in zip(batch, vectors):
            chunk.embedding = vec
            db.add(chunk)
        db.commit()
        embedded += len(batch)
        logger.debug("embedded %d/%d chunks for document %d", embedded, len(chunks), document_id)

    return embedded


# ---------------------------------------------------------------------------
# Backfill CLI helper — embed all ready chunks across all documents
# ---------------------------------------------------------------------------

def backfill_embeddings(db: Session) -> dict[str, int]:
    """Embed every chunk that has no embedding (backfill for existing data).

    Returns ``{"total": N, "embedded": M}``.
    """
    from app.models.chunk import Chunk  # noqa: PLC0415

    total = db.query(Chunk).filter(Chunk.embedding.is_(None)).count()
    if total == 0:
        logger.info("backfill: all chunks already have embeddings")
        return {"total": 0, "embedded": 0}

    logger.info("backfill: %d chunks need embeddings", total)

    # Group by (document_id, version) to reuse the document title.
    from sqlalchemy import distinct  # noqa: PLC0415

    pairs = (
        db.query(distinct(Chunk.document_id), Chunk.version)
        .filter(Chunk.embedding.is_(None))
        .all()
    )
    embedded = 0
    for doc_id, version in pairs:
        n = embed_document_chunks(db, doc_id, version)
        embedded += n
        logger.info("backfill: document %d v%d — %d chunks embedded", doc_id, version, n)

    return {"total": total, "embedded": embedded}
