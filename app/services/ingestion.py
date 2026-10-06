"""Staged ingestion pipeline (spec §7.2).

Celery + Redis are deferred on this host (human decision, Phase 5.5 #3): the
same stage sequence, idempotency, and retry policy run as a FastAPI background
task with an `ingestion_jobs` row per run. The stage names and the job table
match the spec so switching the executor to Celery later is a thin change.
"""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.document import ChunkingStatus, Document, DocumentStatus, ExtractionStatus, refresh_document_status
from app.models.ingestion_job import IngestionJob, JobStatus
from app.services.audit import record_audit
from app.services.chunking import ChunkingError, ChunkingOptions, chunk_document, reset_document_chunks
from app.services.extraction import ExtractionError, extract_document_text

logger = logging.getLogger(__name__)

# Spec §7.2: retries 3× with backoff 30s/120s/480s (monkeypatched to zeros in tests).
INGEST_RETRY_BACKOFF_SECONDS: tuple[float, ...] = (30.0, 120.0, 480.0)


def queue_ingestion(db: Session, document: Document, *, note: str | None = None) -> IngestionJob:
    """Create the job row for a document version before the task is scheduled."""

    job = IngestionJob(
        document_id=document.id,
        version=document.version,
        celery_task_id=uuid4().hex,  # job identifier; Celery will fill this with the task id
        status=JobStatus.QUEUED,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    if note:
        logger.info("ingestion queued: %s", note)
    return job


def run_ingestion_task(document_id: int, version: int, job_id: int) -> None:
    """Background-task entrypoint: owns its own DB session."""

    db = SessionLocal()
    try:
        run_ingestion(db, document_id=document_id, version=version, job_id=job_id)
    finally:
        db.close()


def run_ingestion(db: Session, *, document_id: int, version: int, job_id: int) -> bool:
    """Execute the pipeline with the spec retry policy. Returns success."""

    document = db.query(Document).filter(Document.id == document_id).first()
    job = db.query(IngestionJob).filter(IngestionJob.id == job_id).first()
    if document is None or job is None:
        logger.error("ingestion job %s skipped: document %s missing", job_id, document_id)
        return False

    max_attempts = 1 + len(INGEST_RETRY_BACKOFF_SECONDS)
    for attempt in range(1, max_attempts + 1):
        job.status = JobStatus.RUNNING
        job.attempt = attempt
        job.started_at = datetime.now(UTC)
        job.error = None
        db.add(job)
        db.commit()
        try:
            _run_pipeline(db, document)
        except (ExtractionError, ChunkingError) as exc:
            message = str(exc)
            _mark_failed(db, document, message)
            if attempt < max_attempts:
                delay = INGEST_RETRY_BACKOFF_SECONDS[attempt - 1]
                logger.warning("ingestion attempt %s failed (%s); retrying in %ss", attempt, message, delay)
                time.sleep(delay)
                continue
            job.status = JobStatus.FAILED
            job.error = message
            job.finished_at = datetime.now(UTC)
            db.add(job)
            db.commit()
            record_audit(
                db,
                action="document.failed",
                entity_type="document",
                entity_id=str(document.id),
                metadata={"stage": "ingestion", "error": message, "attempts": attempt},
            )
            return False
        except Exception as exc:
            message = f"unexpected ingestion error: {exc}"
            logger.exception("unexpected ingestion failure for document %s", document_id)
            _mark_failed(db, document, message)
            job.status = JobStatus.FAILED
            job.error = message
            job.finished_at = datetime.now(UTC)
            db.add(job)
            db.commit()
            record_audit(
                db,
                action="document.failed",
                entity_type="document",
                entity_id=str(document.id),
                metadata={"stage": "ingestion", "error": message, "attempts": attempt},
            )
            return False

        job.status = JobStatus.SUCCEEDED
        job.finished_at = datetime.now(UTC)
        db.add(job)
        db.commit()
        return True
    return False


def _run_pipeline(db: Session, document: Document) -> None:
    """One pipeline attempt: extracting → cleaning → chunking → [embedding] → [okf] → indexing.

    The `embedding` and `okf_extracting` stages are wired in Phase 6/Phase 8;
    until then documents become `ready` for the stages that exist.
    """

    # Stage: extracting + cleaning (spec §7.2 — extraction service performs both).
    document = extract_document_text(db, document)

    # Stage: chunking.
    reset_document_chunks(db, document, commit=False)
    document = chunk_document(db, document, ChunkingOptions())

    # Stage: embedding (Phase 6) — chunks stay without embeddings until then.
    # Stage: okf_extracting (Phase 8) — skipped while LLM_EXTERNAL_ALLOWED=false.

    # Stage: indexing.
    document.status = DocumentStatus.READY
    refresh_document_status(document)
    db.add(document)
    db.commit()
    db.refresh(document)
    record_audit(
        db,
        action="document.ready",
        entity_type="document",
        entity_id=str(document.id),
        metadata={"version": document.version, "chunks": document.chunk_count},
    )


def _mark_failed(db: Session, document: Document, message: str) -> None:
    if document.extraction_status == ExtractionStatus.PROCESSING:
        document.extraction_status = ExtractionStatus.FAILED
        document.extraction_error = message
    if document.chunking_status == ChunkingStatus.PROCESSING:
        document.chunking_status = ChunkingStatus.FAILED
        document.chunking_error = message
    refresh_document_status(document)
    db.add(document)
    db.commit()
    db.refresh(document)
