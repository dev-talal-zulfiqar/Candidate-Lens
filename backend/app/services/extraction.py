from dataclasses import dataclass

import pymupdf
from docx import Document
from docx.opc.exceptions import PackageNotFoundError
from lxml.etree import XMLSyntaxError

from app.models.enums import ExtractionStatus

MIN_MEANINGFUL_CHARS = 20


@dataclass(frozen=True)
class ExtractionLimits:
    max_pdf_pages: int
    max_extracted_chars: int


@dataclass(frozen=True)
class ExtractionResult:
    status: ExtractionStatus
    text: str | None
    error: str | None = None


def extract_text(storage_path: str, extension: str, limits: ExtractionLimits) -> ExtractionResult:
    if extension == ".pdf":
        result = _extract_pdf(storage_path, limits)
    else:
        result = _extract_docx(storage_path)

    if result.status != ExtractionStatus.COMPLETED or result.text is None:
        return result

    text = result.text.strip()
    if len(text) < MIN_MEANINGFUL_CHARS:
        return ExtractionResult(
            status=ExtractionStatus.FAILED,
            text=None,
            error="No extractable text found — the document may be scanned or image-only",
        )

    truncated = text[: limits.max_extracted_chars]
    return ExtractionResult(status=ExtractionStatus.COMPLETED, text=truncated)


def _extract_pdf(storage_path: str, limits: ExtractionLimits) -> ExtractionResult:
    try:
        document = pymupdf.open(storage_path)
    except pymupdf.FileDataError:
        return ExtractionResult(
            status=ExtractionStatus.FAILED, text=None, error="Corrupted or unreadable PDF"
        )

    try:
        if document.needs_pass:
            return ExtractionResult(
                status=ExtractionStatus.FAILED,
                text=None,
                error="Password-protected PDFs are not supported",
            )

        if document.page_count > limits.max_pdf_pages:
            return ExtractionResult(
                status=ExtractionStatus.FAILED,
                text=None,
                error=f"PDF exceeds the maximum of {limits.max_pdf_pages} pages",
            )

        text = "\n".join(page.get_text() for page in document)
        return ExtractionResult(status=ExtractionStatus.COMPLETED, text=text)
    finally:
        document.close()


def _extract_docx(storage_path: str) -> ExtractionResult:
    try:
        document = Document(storage_path)
    # python-docx raises a mix of exception types for malformed packages
    # depending on exactly which part is broken; file_validation already
    # confirmed this is a well-formed zip with the required docx entry, so
    # any of these at this stage means genuinely corrupted document XML.
    except (PackageNotFoundError, KeyError, ValueError, XMLSyntaxError):
        return ExtractionResult(
            status=ExtractionStatus.FAILED, text=None, error="Corrupted or unreadable DOCX"
        )

    paragraphs = [p.text for p in document.paragraphs]
    table_cells = [
        cell.text for table in document.tables for row in table.rows for cell in row.cells
    ]
    text = "\n".join(paragraphs + table_cells)
    return ExtractionResult(status=ExtractionStatus.COMPLETED, text=text)
