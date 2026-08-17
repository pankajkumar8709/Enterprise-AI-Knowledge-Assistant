from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable
from xml.etree import ElementTree

from pypdf import PdfReader
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.document import Document, ExtractionStatus
from app.services.chunking import chunk_document, reset_document_chunks

WORD_NAMESPACE = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
PPT_NAMESPACES = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
}
REPEATED_HEADER_MIN_OCCURRENCES = 2


class ExtractionError(Exception):
    pass


@dataclass(slots=True)
class ExtractionResult:
    raw_text: str
    clean_text: str
    used_ocr: bool


def _get_extraction_root() -> Path:
    return Path(settings.document_extraction_dir).resolve()


def _ensure_extraction_root() -> Path:
    extraction_root = _get_extraction_root()
    extraction_root.mkdir(parents=True, exist_ok=True)
    return extraction_root


def _document_output_dir(document_id: int) -> Path:
    output_dir = _ensure_extraction_root() / str(document_id)
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def delete_extraction_files(document: Document) -> None:
    if document.extraction_raw_text_path:
        Path(document.extraction_raw_text_path).unlink(missing_ok=True)
    if document.extraction_clean_text_path:
        Path(document.extraction_clean_text_path).unlink(missing_ok=True)

    output_dir = _get_extraction_root() / str(document.id)
    if output_dir.exists():
        shutil.rmtree(output_dir, ignore_errors=True)


def extract_document_text(db: Session, document: Document) -> Document:
    delete_extraction_files(document)
    reset_document_chunks(db, document, commit=False)
    document.extraction_status = ExtractionStatus.PROCESSING
    document.extraction_error = None
    document.extraction_ocr_used = False
    document.extracted_char_count = None
    document.extraction_raw_text_path = None
    document.extraction_clean_text_path = None
    document.extraction_started_at = datetime.now(UTC)
    document.extraction_completed_at = None
    db.add(document)
    db.commit()
    db.refresh(document)

    try:
        result = _extract_from_path(Path(document.storage_path))
        output_dir = _document_output_dir(document.id)
        raw_path = output_dir / "raw.txt"
        clean_path = output_dir / "clean.txt"
        raw_path.write_text(result.raw_text, encoding="utf-8")
        clean_path.write_text(result.clean_text, encoding="utf-8")

        document.extraction_raw_text_path = str(raw_path)
        document.extraction_clean_text_path = str(clean_path)
        document.extracted_char_count = len(result.clean_text)
        document.extraction_ocr_used = result.used_ocr
        document.extraction_status = ExtractionStatus.READY
        document.extraction_completed_at = datetime.now(UTC)
    except ExtractionError as exc:
        document.extraction_status = ExtractionStatus.FAILED
        document.extraction_error = str(exc)
        document.extraction_completed_at = datetime.now(UTC)

    db.add(document)
    db.commit()
    db.refresh(document)
    if document.extraction_status == ExtractionStatus.READY:
        return chunk_document(db, document)
    return document


def get_extracted_text(document: Document) -> tuple[str | None, str | None]:
    raw_text = None
    clean_text = None
    if document.extraction_raw_text_path and Path(document.extraction_raw_text_path).exists():
        raw_text = Path(document.extraction_raw_text_path).read_text(encoding="utf-8")
    if document.extraction_clean_text_path and Path(document.extraction_clean_text_path).exists():
        clean_text = Path(document.extraction_clean_text_path).read_text(encoding="utf-8")
    return raw_text, clean_text


def _extract_from_path(path: Path) -> ExtractionResult:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        raw_text, used_ocr = _extract_pdf_text(path)
    elif suffix == ".docx":
        raw_text = _extract_docx_text(path)
        used_ocr = False
    elif suffix == ".pptx":
        raw_text = _extract_pptx_text(path)
        used_ocr = False
    elif suffix in {".txt", ".md", ".markdown"}:
        raw_text = _read_text_file(path)
        used_ocr = False
    else:
        raise ExtractionError("Unsupported file type for extraction")

    clean_text = _clean_text(raw_text)
    if not clean_text.strip():
        if suffix == ".pdf" and not used_ocr:
            raise ExtractionError("No extractable text found in PDF and OCR did not produce usable text")
        raise ExtractionError("Document is empty or unreadable after cleaning")

    return ExtractionResult(raw_text=raw_text, clean_text=clean_text, used_ocr=used_ocr)


def _extract_pdf_text(path: Path) -> tuple[str, bool]:
    reader = PdfReader(str(path))
    page_texts = [(page.extract_text() or "").strip() for page in reader.pages]
    combined_text = "\n\n".join(text for text in _remove_repeated_page_lines(page_texts) if text)
    if combined_text.strip():
        return combined_text, False

    ocr_text = _extract_pdf_text_with_ocr(path)
    return ocr_text, True


def _extract_docx_text(path: Path) -> str:
    try:
        with zipfile.ZipFile(path) as archive:
            xml_bytes = archive.read("word/document.xml")
    except (KeyError, zipfile.BadZipFile) as exc:
        raise ExtractionError("Broken DOCX file") from exc

    try:
        root = ElementTree.fromstring(xml_bytes)
    except ElementTree.ParseError as exc:
        raise ExtractionError("Broken DOCX XML content") from exc

    paragraphs: list[str] = []
    for paragraph in root.findall(".//w:p", WORD_NAMESPACE):
        texts = [node.text or "" for node in paragraph.findall(".//w:t", WORD_NAMESPACE)]
        if texts:
            paragraphs.append("".join(texts))
    return "\n".join(paragraphs)


def _extract_pptx_text(path: Path) -> str:
    try:
        with zipfile.ZipFile(path) as archive:
            slide_names = sorted(
                name for name in archive.namelist() if name.startswith("ppt/slides/slide") and name.endswith(".xml")
            )
            slide_texts = []
            for slide_name in slide_names:
                root = ElementTree.fromstring(archive.read(slide_name))
                texts = [node.text or "" for node in root.findall(".//a:t", PPT_NAMESPACES)]
                slide_texts.append("\n".join(part for part in texts if part.strip()))
    except zipfile.BadZipFile as exc:
        raise ExtractionError("Broken PPTX file") from exc
    except ElementTree.ParseError as exc:
        raise ExtractionError("Broken PPTX XML content") from exc

    return "\n\n".join(text for text in slide_texts if text.strip())


def _read_text_file(path: Path) -> str:
    for encoding in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    raise ExtractionError("Unable to decode text file")


def _remove_repeated_page_lines(page_texts: list[str]) -> list[str]:
    if len(page_texts) < REPEATED_HEADER_MIN_OCCURRENCES:
        return page_texts

    header_counts: dict[str, int] = {}
    footer_counts: dict[str, int] = {}
    page_lines: list[list[str]] = []
    for page_text in page_texts:
        lines = [line.strip() for line in page_text.splitlines() if line.strip()]
        page_lines.append(lines)
        if lines:
            header_counts[lines[0]] = header_counts.get(lines[0], 0) + 1
            footer_counts[lines[-1]] = footer_counts.get(lines[-1], 0) + 1

    repeated_headers = {line for line, count in header_counts.items() if count >= REPEATED_HEADER_MIN_OCCURRENCES}
    repeated_footers = {line for line, count in footer_counts.items() if count >= REPEATED_HEADER_MIN_OCCURRENCES}

    cleaned_pages: list[str] = []
    for lines in page_lines:
        if lines and lines[0] in repeated_headers:
            lines = lines[1:]
        if lines and lines[-1] in repeated_footers:
            lines = lines[:-1]
        cleaned_pages.append("\n".join(lines))
    return cleaned_pages


def _clean_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\x0c", "\n")
    text = re.sub(r"[\u200b\u200c\u200d\ufeff]", "", text)
    text = re.sub(r"[^\S\n]+", " ", text)
    text = re.sub(r"[^\x09\x0A\x20-\x7E\u00A0-\u024F]", "", text)
    lines = [_clean_line(line) for line in text.split("\n")]
    text = "\n".join(line for line in lines if line is not None)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _clean_line(line: str) -> str | None:
    line = line.strip()
    if not line:
        return ""
    if re.fullmatch(r"[-=*_~.#\s]+", line):
        return None
    if re.fullmatch(r"page\s+\d+(\s+of\s+\d+)?", line, flags=re.IGNORECASE):
        return None
    return line


def _extract_pdf_text_with_ocr(path: Path) -> str:
    try:
        from PIL import Image
        import pytesseract
    except ImportError as exc:
        raise ExtractionError("OCR dependencies are not installed for scanned PDF support") from exc

    pdftoppm_path = shutil.which("pdftoppm")
    if not pdftoppm_path:
        raise ExtractionError("OCR requires the pdftoppm command from Poppler to be installed")

    tesseract_path = shutil.which("tesseract")
    if not tesseract_path:
        raise ExtractionError("OCR requires the Tesseract binary to be installed")

    with tempfile.TemporaryDirectory() as temp_dir:
        output_prefix = Path(temp_dir) / "page"
        try:
            subprocess.run(
                [pdftoppm_path, "-png", str(path), str(output_prefix)],
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as exc:
            raise ExtractionError("Unable to render scanned PDF for OCR") from exc

        image_paths = sorted(Path(temp_dir).glob("page-*.png"))
        if not image_paths:
            raise ExtractionError("No PDF pages were rendered for OCR")

        page_texts: list[str] = []
        for image_path in image_paths:
            with Image.open(image_path) as image:
                page_text = pytesseract.image_to_string(image)
            if page_text.strip():
                page_texts.append(page_text)

    combined_text = "\n\n".join(page_texts).strip()
    if not combined_text:
        raise ExtractionError("OCR completed but no readable text was found")
    return combined_text
