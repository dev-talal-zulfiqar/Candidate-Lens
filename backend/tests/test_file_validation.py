import struct
import zipfile
from io import BytesIO

import pytest

from app.services.file_validation import FileValidationError, UploadLimits, validate_resume_file
from tests.resume_fixtures import make_docx_bytes, make_pdf_bytes

DEFAULT_LIMITS = UploadLimits(
    max_size_bytes=5 * 1024 * 1024, max_docx_decompressed_bytes=50 * 1024 * 1024
)


def test_accepts_valid_pdf():
    validate_resume_file("resume.pdf", make_pdf_bytes(), DEFAULT_LIMITS)


def test_accepts_valid_docx():
    validate_resume_file("resume.docx", make_docx_bytes(), DEFAULT_LIMITS)


def test_rejects_unsupported_extension():
    with pytest.raises(FileValidationError, match="Unsupported file type"):
        validate_resume_file("resume.txt", b"plain text", DEFAULT_LIMITS)


def test_rejects_empty_file():
    with pytest.raises(FileValidationError, match="empty"):
        validate_resume_file("resume.pdf", b"", DEFAULT_LIMITS)


def test_rejects_oversized_file():
    tiny_limits = UploadLimits(max_size_bytes=10, max_docx_decompressed_bytes=1024)
    with pytest.raises(FileValidationError, match="exceeds the maximum size"):
        validate_resume_file("resume.pdf", make_pdf_bytes(), tiny_limits)


def test_rejects_pdf_with_mismatched_signature():
    docx_bytes = make_docx_bytes()
    with pytest.raises(FileValidationError, match="does not match a PDF"):
        validate_resume_file("resume.pdf", docx_bytes, DEFAULT_LIMITS)


def test_rejects_docx_with_mismatched_signature():
    pdf_bytes = make_pdf_bytes()
    with pytest.raises(FileValidationError, match="does not match a DOCX"):
        validate_resume_file("resume.docx", pdf_bytes, DEFAULT_LIMITS)


def test_rejects_docx_missing_required_entry():
    import io
    import zipfile

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("not_a_real_entry.txt", "hello")

    with pytest.raises(FileValidationError, match="not a valid DOCX"):
        validate_resume_file("resume.docx", buffer.getvalue(), DEFAULT_LIMITS)


def test_rejects_suspiciously_large_decompressed_docx():
    import io
    import zipfile

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", "x" * 1000)

    tight_limits = UploadLimits(max_size_bytes=5 * 1024 * 1024, max_docx_decompressed_bytes=100)
    with pytest.raises(FileValidationError, match="suspiciously large"):
        validate_resume_file("resume.docx", buffer.getvalue(), tight_limits)


def _docx_bytes_with_falsified_entry_size(entry_name: str, forged_size: int) -> bytes:
    """Builds a real DOCX whose central-directory record for `entry_name`
    declares `forged_size` as its uncompressed size instead of its true
    value, while the local header and actual compressed data are left
    untouched. This is the central-directory field a decompression-bomb
    check that only reads ZipInfo.file_size (rather than real bytes read
    on decompression) would be fooled by (QA-006).
    """
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr(entry_name, "A" * (2 * 1024 * 1024))

    data = bytearray(buffer.getvalue())
    idx = 0
    target = entry_name.encode()
    while True:
        idx = data.find(b"PK\x01\x02", idx)
        if idx == -1:
            break
        fname_len = struct.unpack_from("<H", data, idx + 28)[0]
        extra_len = struct.unpack_from("<H", data, idx + 30)[0]
        comment_len = struct.unpack_from("<H", data, idx + 32)[0]
        fname = bytes(data[idx + 46 : idx + 46 + fname_len])
        if fname == target:
            struct.pack_into("<I", data, idx + 24, forged_size)
        idx += 46 + fname_len + extra_len + comment_len
    return bytes(data)


def test_rejects_docx_with_falsified_entry_size_metadata():
    # Before this check decompressed and counted real bytes, a declared
    # ZipInfo.file_size far smaller than the entry's true decompressed
    # size would sail straight past the size-limit check — it's the
    # central-directory metadata field, not verified decompressed output.
    forged = _docx_bytes_with_falsified_entry_size("big.bin", forged_size=10)
    tight_limits = UploadLimits(max_size_bytes=5 * 1024 * 1024, max_docx_decompressed_bytes=1024)

    with pytest.raises(FileValidationError):
        validate_resume_file("resume.docx", forged, tight_limits)


def test_rejects_missing_filename():
    with pytest.raises(FileValidationError, match="Filename"):
        validate_resume_file("", make_pdf_bytes(), DEFAULT_LIMITS)


def test_rejects_excessively_long_filename():
    long_name = "a" * 300 + ".pdf"
    with pytest.raises(FileValidationError, match="too long"):
        validate_resume_file(long_name, make_pdf_bytes(), DEFAULT_LIMITS)
