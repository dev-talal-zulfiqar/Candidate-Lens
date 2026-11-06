from app.models.enums import ExtractionStatus
from app.services.extraction import ExtractionLimits, extract_text
from tests.resume_fixtures import (
    make_corrupted_docx_bytes,
    make_corrupted_pdf_bytes,
    make_docx_bytes,
    make_encrypted_pdf_bytes,
    make_multi_page_pdf_bytes,
    make_pdf_bytes,
    make_scanned_pdf_bytes,
)

DEFAULT_LIMITS = ExtractionLimits(max_pdf_pages=25, max_extracted_chars=200_000)


def _write(tmp_path, name: str, data: bytes) -> str:
    path = tmp_path / name
    path.write_bytes(data)
    return str(path)


def test_extracts_text_from_valid_pdf(tmp_path):
    path = _write(tmp_path, "r.pdf", make_pdf_bytes("Python developer with 6 years experience"))
    result = extract_text(path, ".pdf", DEFAULT_LIMITS)
    assert result.status == ExtractionStatus.COMPLETED
    assert "Python developer" in result.text


def test_extracts_text_from_valid_docx(tmp_path):
    path = _write(tmp_path, "r.docx", make_docx_bytes("QA engineer with automation experience"))
    result = extract_text(path, ".docx", DEFAULT_LIMITS)
    assert result.status == ExtractionStatus.COMPLETED
    assert "QA engineer" in result.text


def test_scanned_pdf_with_no_text_fails(tmp_path):
    path = _write(tmp_path, "scanned.pdf", make_scanned_pdf_bytes())
    result = extract_text(path, ".pdf", DEFAULT_LIMITS)
    assert result.status == ExtractionStatus.FAILED
    assert "scanned" in result.error.lower() or "no extractable text" in result.error.lower()


def test_encrypted_pdf_fails(tmp_path):
    path = _write(tmp_path, "encrypted.pdf", make_encrypted_pdf_bytes())
    result = extract_text(path, ".pdf", DEFAULT_LIMITS)
    assert result.status == ExtractionStatus.FAILED
    assert "password" in result.error.lower()


def test_corrupted_pdf_fails(tmp_path):
    path = _write(tmp_path, "corrupted.pdf", make_corrupted_pdf_bytes())
    result = extract_text(path, ".pdf", DEFAULT_LIMITS)
    assert result.status == ExtractionStatus.FAILED
    assert "corrupted" in result.error.lower()


def test_corrupted_docx_fails(tmp_path):
    path = _write(tmp_path, "corrupted.docx", make_corrupted_docx_bytes())
    result = extract_text(path, ".docx", DEFAULT_LIMITS)
    assert result.status == ExtractionStatus.FAILED
    assert "corrupted" in result.error.lower()


def test_pdf_exceeding_max_page_count_fails(tmp_path):
    path = _write(tmp_path, "long.pdf", make_multi_page_pdf_bytes(5))
    limits = ExtractionLimits(max_pdf_pages=2, max_extracted_chars=200_000)
    result = extract_text(path, ".pdf", limits)
    assert result.status == ExtractionStatus.FAILED
    assert "page" in result.error.lower()


def test_extracted_text_is_truncated_to_max_chars(tmp_path):
    long_text = "A" * 500
    path = _write(tmp_path, "r.docx", make_docx_bytes(long_text))
    limits = ExtractionLimits(max_pdf_pages=25, max_extracted_chars=50)
    result = extract_text(path, ".docx", limits)
    assert result.status == ExtractionStatus.COMPLETED
    assert len(result.text) == 50
