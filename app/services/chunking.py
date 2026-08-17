from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable, Sequence

from pypdf import PdfReader
from sqlalchemy.orm import Session

from app.models.chunk import Chunk, ChunkStatus, ChunkStrategy
from app.models.document import ChunkingStatus, Document, ExtractionStatus

DEFAULT_CHUNK_SIZE = 800
DEFAULT_CHUNK_OVERLAP = 120
MAX_CHUNK_PREVIEW_LIMIT = 100


class ChunkingError(Exception):
    pass


@dataclass(slots=True)
class ChunkingOptions:
    chunk_size: int = DEFAULT_CHUNK_SIZE
    overlap: int = DEFAULT_CHUNK_OVERLAP
    strategies: tuple[ChunkStrategy, ...] = (
        ChunkStrategy.FIXED_SIZE,
        ChunkStrategy.SENTENCE_BASED,
        ChunkStrategy.SECTION_BASED,
    )


@dataclass(slots=True)
class SectionSpan:
    title: str | None
    start: int
    end: int
    text: str


@dataclass(slots=True)
class PageSpan:
    page_number: int
    start: int
    end: int


@dataclass(slots=True)
class ChunkDraft:
    text: str
    overlap_size: int
    section_title: str | None = None
    start_offset: int | None = None
    end_offset: int | None = None


def reset_document_chunks(db: Session, document: Document, *, commit: bool = True) -> Document:
    db.query(Chunk).filter(Chunk.document_id == document.id).delete(synchronize_session=False)
    document.chunking_status = ChunkingStatus.PENDING
    document.chunking_error = None
    document.chunk_count = 0
    document.chunking_started_at = None
    document.chunking_completed_at = None
    db.add(document)
    if commit:
        db.commit()
        db.refresh(document)
    return document


def chunk_document(
    db: Session,
    document: Document,
    options: ChunkingOptions | None = None,
) -> Document:
    options = options or ChunkingOptions()
    _validate_chunking_options(options)
    _ensure_document_can_be_chunked(document)

    reset_document_chunks(db, document, commit=False)
    document.chunking_status = ChunkingStatus.PROCESSING
    document.chunking_started_at = datetime.now(UTC)
    db.add(document)
    db.commit()
    db.refresh(document)

    try:
        clean_text = _read_clean_text(document)
        sections = _split_into_sections(clean_text)
        page_spans = _build_page_spans(document, clean_text)
        chunk_records = _build_chunk_records(document, clean_text, sections, page_spans, options)
        if not chunk_records:
            raise ChunkingError("No chunks could be generated from the extracted text")

        db.add_all(chunk_records)
        document.chunk_count = len(chunk_records)
        document.chunking_status = ChunkingStatus.READY
        document.chunking_error = None
        document.chunking_completed_at = datetime.now(UTC)
    except ChunkingError as exc:
        document.chunking_status = ChunkingStatus.FAILED
        document.chunking_error = str(exc)
        document.chunk_count = 0
        document.chunking_completed_at = datetime.now(UTC)

    db.add(document)
    db.commit()
    db.refresh(document)
    return document


def list_document_chunks(
    db: Session,
    document_id: int,
    *,
    strategy: ChunkStrategy | None = None,
    limit: int = 20,
) -> list[Chunk]:
    limit = min(max(limit, 1), MAX_CHUNK_PREVIEW_LIMIT)
    query = db.query(Chunk).filter(Chunk.document_id == document_id, Chunk.status == ChunkStatus.READY)
    if strategy is not None:
        query = query.filter(Chunk.strategy == strategy)
    return query.order_by(Chunk.strategy.asc(), Chunk.chunk_index.asc()).limit(limit).all()


def count_document_chunks(
    db: Session,
    document_id: int,
    *,
    strategy: ChunkStrategy | None = None,
) -> int:
    query = db.query(Chunk).filter(Chunk.document_id == document_id, Chunk.status == ChunkStatus.READY)
    if strategy is not None:
        query = query.filter(Chunk.strategy == strategy)
    return query.count()


def _validate_chunking_options(options: ChunkingOptions) -> None:
    if options.chunk_size < 100:
        raise ChunkingError("Chunk size must be at least 100 characters")
    if options.overlap < 0:
        raise ChunkingError("Chunk overlap cannot be negative")
    if options.overlap >= options.chunk_size:
        raise ChunkingError("Chunk overlap must be smaller than chunk size")
    if not options.strategies:
        raise ChunkingError("At least one chunking strategy is required")


def _ensure_document_can_be_chunked(document: Document) -> None:
    if document.extraction_status != ExtractionStatus.READY:
        raise ChunkingError("Chunking requires a document with successful text extraction")
    if not document.extraction_clean_text_path:
        raise ChunkingError("Chunking requires a clean extracted text file")


def _read_clean_text(document: Document) -> str:
    clean_text_path = Path(document.extraction_clean_text_path or "")
    if not clean_text_path.exists():
        raise ChunkingError("Clean extracted text file is missing")
    clean_text = clean_text_path.read_text(encoding="utf-8").strip()
    if not clean_text:
        raise ChunkingError("Clean extracted text is empty")
    return clean_text


def _build_chunk_records(
    document: Document,
    clean_text: str,
    sections: Sequence[SectionSpan],
    page_spans: Sequence[PageSpan],
    options: ChunkingOptions,
) -> list[Chunk]:
    chunk_records: list[Chunk] = []
    for strategy in options.strategies:
        drafts = _generate_chunks_for_strategy(strategy, clean_text, sections, options.chunk_size, options.overlap)
        for index, draft in enumerate(drafts, start=1):
            start_offset, end_offset = _resolve_offsets(clean_text, draft.text, draft.start_offset)
            section_title = draft.section_title or _section_title_for_offset(sections, start_offset)
            page_number = _page_number_for_offset(page_spans, start_offset)
            chunk_records.append(
                Chunk(
                    document_id=document.id,
                    strategy=strategy,
                    status=ChunkStatus.READY,
                    chunk_index=index,
                    text=draft.text,
                    text_length=len(draft.text),
                    start_offset=start_offset,
                    end_offset=end_offset,
                    overlap_size=draft.overlap_size,
                    page_number=page_number,
                    section_title=section_title,
                    source_file_name=document.source_name,
                    upload_date=document.created_at,
                )
            )
    return chunk_records


def _generate_chunks_for_strategy(
    strategy: ChunkStrategy,
    clean_text: str,
    sections: Sequence[SectionSpan],
    chunk_size: int,
    overlap: int,
) -> list[ChunkDraft]:
    if strategy == ChunkStrategy.FIXED_SIZE:
        return _fixed_size_chunks(clean_text, chunk_size, overlap)
    if strategy == ChunkStrategy.SENTENCE_BASED:
        return _sentence_based_chunks(clean_text, chunk_size, overlap)
    if strategy == ChunkStrategy.SECTION_BASED:
        return _section_based_chunks(sections, chunk_size, overlap)
    raise ChunkingError(f"Unsupported chunking strategy: {strategy.value}")


def _fixed_size_chunks(text: str, chunk_size: int, overlap: int) -> list[ChunkDraft]:
    chunks: list[ChunkDraft] = []
    step = chunk_size - overlap
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunk_text = text[start:end].strip()
        if chunk_text:
            chunks.append(
                ChunkDraft(
                    text=chunk_text,
                    overlap_size=overlap if chunks else 0,
                    start_offset=start,
                    end_offset=end,
                )
            )
        if end >= len(text):
            break
        start += step
    return chunks


def _sentence_based_chunks(text: str, chunk_size: int, overlap: int) -> list[ChunkDraft]:
    sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+|\n{2,}", text) if part.strip()]
    if not sentences:
        return _fixed_size_chunks(text, chunk_size, overlap)

    chunks: list[ChunkDraft] = []
    current_sentences: list[str] = []
    current_length = 0

    for sentence in sentences:
        sentence_length = len(sentence) + (1 if current_sentences else 0)
        if current_sentences and current_length + sentence_length > chunk_size:
            chunk_text = " ".join(current_sentences).strip()
            chunks.append(ChunkDraft(text=chunk_text, overlap_size=overlap if chunks else 0))
            current_sentences = _tail_sentences_for_overlap(current_sentences, overlap)
            current_length = len(" ".join(current_sentences)) if current_sentences else 0

        if len(sentence) > chunk_size and not current_sentences:
            chunks.extend(_fixed_size_chunks(sentence, chunk_size, overlap))
            continue

        current_sentences.append(sentence)
        current_length = len(" ".join(current_sentences))

    if current_sentences:
        chunk_text = " ".join(current_sentences).strip()
        if chunk_text:
            chunks.append(ChunkDraft(text=chunk_text, overlap_size=overlap if chunks else 0))
    return chunks


def _tail_sentences_for_overlap(sentences: Sequence[str], overlap: int) -> list[str]:
    if overlap == 0:
        return []
    tail: list[str] = []
    total_length = 0
    for sentence in reversed(sentences):
        extra_length = len(sentence) + (1 if tail else 0)
        if tail and total_length + extra_length > overlap:
            break
        tail.insert(0, sentence)
        total_length += extra_length
    return tail


def _section_based_chunks(sections: Sequence[SectionSpan], chunk_size: int, overlap: int) -> list[ChunkDraft]:
    chunks: list[ChunkDraft] = []
    for section in sections:
        section_text = section.text.strip()
        if not section_text:
            continue
        if len(section_text) <= chunk_size:
            chunks.append(
                ChunkDraft(
                    text=section_text,
                    overlap_size=0,
                    section_title=section.title,
                    start_offset=section.start,
                    end_offset=section.end,
                )
            )
            continue

        nested_chunks = _sentence_based_chunks(section_text, chunk_size, overlap)
        if not nested_chunks:
            nested_chunks = _fixed_size_chunks(section_text, chunk_size, overlap)
        for nested_chunk in nested_chunks:
            offset = section.start + (nested_chunk.start_offset or 0)
            chunks.append(
                ChunkDraft(
                    text=nested_chunk.text,
                    overlap_size=nested_chunk.overlap_size,
                    section_title=section.title,
                    start_offset=offset,
                    end_offset=offset + len(nested_chunk.text),
                )
            )
    return chunks


def _split_into_sections(text: str) -> list[SectionSpan]:
    lines = text.splitlines(keepends=True)
    headings: list[tuple[int, str]] = []
    offset = 0
    for line in lines:
        stripped = line.strip()
        if _is_heading_line(stripped):
            headings.append((offset, _normalize_heading(stripped)))
        offset += len(line)

    if not headings:
        return [SectionSpan(title=None, start=0, end=len(text), text=text.strip())]

    sections: list[SectionSpan] = []
    if headings[0][0] > 0:
        intro_text = text[: headings[0][0]].strip()
        if intro_text:
            sections.append(SectionSpan(title=None, start=0, end=headings[0][0], text=intro_text))

    for index, (start_offset, title) in enumerate(headings):
        end_offset = headings[index + 1][0] if index + 1 < len(headings) else len(text)
        section_text = text[start_offset:end_offset].strip()
        if section_text:
            sections.append(SectionSpan(title=title, start=start_offset, end=end_offset, text=section_text))

    return sections or [SectionSpan(title=None, start=0, end=len(text), text=text.strip())]


def _is_heading_line(line: str) -> bool:
    if not line:
        return False
    if line.startswith("#"):
        return True
    if re.fullmatch(r"\d+(\.\d+)*[\). -]+\S.*", line):
        return True
    words = line.split()
    if len(words) > 10:
        return False
    if line.isupper() and any(char.isalpha() for char in line):
        return True
    if line.endswith(":") and len(words) <= 8:
        return True
    title_case_words = sum(1 for word in words if word[:1].isupper())
    return len(words) <= 6 and title_case_words == len(words) and not line.endswith(".")


def _normalize_heading(line: str) -> str:
    return line.lstrip("#").strip().rstrip(":")


def _build_page_spans(document: Document, clean_text: str) -> list[PageSpan]:
    if Path(document.storage_path).suffix.lower() != ".pdf":
        return [PageSpan(page_number=1, start=0, end=len(clean_text))]

    reader = PdfReader(document.storage_path)
    raw_page_texts = [(page.extract_text() or "").strip() for page in reader.pages]
    cleaned_page_texts = [_normalize_page_text(page_text) for page_text in raw_page_texts]
    page_spans: list[PageSpan] = []
    current_offset = 0
    for index, page_text in enumerate(cleaned_page_texts, start=1):
        if not page_text:
            continue
        start = clean_text.find(page_text[: min(len(page_text), 200)], current_offset)
        if start == -1:
            start = current_offset
        end = min(start + len(page_text), len(clean_text))
        page_spans.append(PageSpan(page_number=index, start=start, end=end))
        current_offset = end

    return page_spans or [PageSpan(page_number=1, start=0, end=len(clean_text))]


def _normalize_page_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\x0c", "\n")
    text = re.sub(r"[^\S\n]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _resolve_offsets(text: str, chunk_text: str, suggested_start: int | None) -> tuple[int, int]:
    if suggested_start is not None:
        normalized_start = max(suggested_start, 0)
        if text[normalized_start : normalized_start + len(chunk_text)] == chunk_text:
            return normalized_start, normalized_start + len(chunk_text)

    start = text.find(chunk_text)
    if start == -1:
        condensed_chunk = re.sub(r"\s+", " ", chunk_text.strip())
        condensed_text = re.sub(r"\s+", " ", text)
        start = condensed_text.find(condensed_chunk)
        if start == -1:
            return 0, len(chunk_text)
    return start, start + len(chunk_text)


def _section_title_for_offset(sections: Sequence[SectionSpan], start_offset: int) -> str | None:
    for section in sections:
        if section.start <= start_offset < section.end:
            return section.title
    return sections[-1].title if sections else None


def _page_number_for_offset(page_spans: Sequence[PageSpan], start_offset: int) -> int | None:
    for page_span in page_spans:
        if page_span.start <= start_offset < page_span.end:
            return page_span.page_number
    return page_spans[-1].page_number if page_spans else None
