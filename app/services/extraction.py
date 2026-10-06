from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from xml.etree import ElementTree

from pypdf import PdfReader
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.document import (
    Document,
    DocumentStatus,
    ExtractionStatus,
    refresh_document_status,
)
from app.services.chunking import chunk_document, reset_document_chunks

WORD_NAMESPACE = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
PPT_NAMESPACES = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
}
# Spec §7.2: a line counts as header/footer only when repeated on > 40% of pages
# and is <= 100 chars. A fixed count would delete legitimate lines on long documents.
REPEATED_HEADER_MAX_RATIO = 0.4
REPEATED_HEADER_MAX_CHARS = 100
# Control characters, zero-width/bidi marks and BOM are removed; every other
# character (currency signs, dashes, quotes, emoji, non-Latin scripts) is kept.
CONTROL_CHARS_PATTERN = re.compile(
    "[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f\u200b-\u200f\u2028\u2029\u202a-\u202e\u2060-\u206f\ufeff]"
)


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
    document.status = DocumentStatus.PROCESSING
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
    except Exception as exc:  # noqa: BLE001 - corrupt/encrypted files raise parser-specific
        # errors (pypdf EmptyFileError/PdfReadError/FileNotDecryptedError, zip/XML
        # errors, ...). They must surface as a failed document, never as an
        # unhandled 500 that leaves the row stuck in `processing` (audit F-002).
        document.extraction_status = ExtractionStatus.FAILED
        document.extraction_error = f"Unreadable or corrupt document ({type(exc).__name__}): {exc}"
        document.extraction_completed_at = datetime.now(UTC)

    db.add(document)
    db.commit()
    db.refresh(document)
    if document.extraction_status == ExtractionStatus.READY:
        document = chunk_document(db, document)
    else:
        refresh_document_status(document)
        db.add(document)
        db.commit()
        db.refresh(document)
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
        # Parsed from a server-extracted DOCX part, not raw client XML; stdlib
        # ElementTree does not resolve external entities.
        root = ElementTree.fromstring(xml_bytes)  # nosec B314
    except ElementTree.ParseError as exc:
        raise ExtractionError("Broken DOCX XML content") from exc

    body = root.find("w:body", WORD_NAMESPACE)
    if body is None:
        return ""

    lines: list[str] = []
    word_tag = WORD_NAMESPACE["w"]
    for child in body:
        tag = child.tag.rsplit("}", 1)[-1]
        if tag == "p":
            texts = [node.text or "" for node in child.findall(".//w:t", WORD_NAMESPACE)]
            text = "".join(texts).strip()
            if not text:
                continue
            style = child.find("w:pPr/w:pStyle", WORD_NAMESPACE)
            heading_level = 0
            if style is not None:
                style_value = style.get(f"{{{word_tag}}}val", "") or ""
                heading_match = re.match(r"(?i)heading\s*(\d)", style_value)
                if heading_match:
                    heading_level = min(int(heading_match.group(1)), 6)
                elif style_value.lower() == "title":
                    heading_level = 1
            if heading_level:
                # Mark headings so the chunker can use them as section titles.
                text = f"{'#' * heading_level} {text}"
            elif child.find("w:pPr/w:numPr", WORD_NAMESPACE) is not None:
                text = f"- {text}"
            lines.append(text)
        elif tag == "tbl":
            for row in child.findall("w:tr", WORD_NAMESPACE):
                cells: list[str] = []
                for cell in row.findall("w:tc", WORD_NAMESPACE):
                    cell_texts = [node.text or "" for node in cell.findall(".//w:t", WORD_NAMESPACE)]
                    cells.append("".join(cell_texts).strip())
                lines.append(" | ".join(cells))
    return "\n".join(lines)


def _pptx_name_sort_key(name: str) -> int:
    match = re.search(r"slide(\d+)", name)
    return int(match.group(1)) if match else 0


def _extract_pptx_text(path: Path) -> str:
    try:
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            slide_names = sorted(
                (name for name in names if name.startswith("ppt/slides/slide") and name.endswith(".xml")),
                key=_pptx_name_sort_key,
            )
            slide_texts = []
            for slide_name in slide_names:
                # Server-side PPTX part; external entities are not resolved.
                root = ElementTree.fromstring(archive.read(slide_name))  # nosec B314
                texts = [node.text or "" for node in root.findall(".//a:t", PPT_NAMESPACES)]
                slide_text = "\n".join(part for part in texts if part.strip())
                # Speaker notes for the same slide (audit F-016).
                slide_number = _pptx_name_sort_key(slide_name)
                notes_name = f"ppt/notesSlides/notesSlide{slide_number}.xml"
                if notes_name in names:
                    # Server-side PPTX notes part; external entities are not resolved.
                    notes_root = ElementTree.fromstring(archive.read(notes_name))  # nosec B314
                    notes_parts = [node.text or "" for node in notes_root.findall(".//a:t", PPT_NAMESPACES)]
                    notes_text = " ".join(part.strip() for part in notes_parts if part.strip())
                    if notes_text:
                        prefix = f"{slide_text}\n" if slide_text else ""
                        slide_text = f"{prefix}[speaker notes] {notes_text}"
                slide_texts.append(slide_text)
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
    if len(page_texts) < 2:
        return page_texts

    page_count = len(page_texts)
    header_counts: dict[str, int] = {}
    footer_counts: dict[str, int] = {}
    page_lines: list[list[str]] = []
    for page_text in page_texts:
        lines = [line.strip() for line in page_text.splitlines() if line.strip()]
        page_lines.append(lines)
        if lines:
            header_counts[lines[0]] = header_counts.get(lines[0], 0) + 1
            footer_counts[lines[-1]] = footer_counts.get(lines[-1], 0) + 1

    def _is_repeated_boilerplate(count: int) -> bool:
        return count > REPEATED_HEADER_MAX_RATIO * page_count

    repeated_headers = {
        line
        for line, count in header_counts.items()
        if len(line) <= REPEATED_HEADER_MAX_CHARS and _is_repeated_boilerplate(count)
    }
    repeated_footers = {
        line
        for line, count in footer_counts.items()
        if len(line) <= REPEATED_HEADER_MAX_CHARS and _is_repeated_boilerplate(count)
    }

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
    # Remove control and zero-width characters only; never strip currency signs,
    # dashes, quotes, emoji or non-Latin scripts (audit F-003 / spec §7.2).
    text = CONTROL_CHARS_PATTERN.sub("", text)
    # Rejoin hyphenated line wraps: "carry-\nforward" -> "carryforward";
    # real hyphens without a line break ("full-time") are untouched.
    text = re.sub(r"(?<=\w)-\n(?=[a-z])", "", text)
    text = re.sub(r"[^\S\n]+", " ", text)
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
        import pytesseract
        from PIL import Image
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
