import zipfile
from dataclasses import dataclass
from io import BytesIO

PDF_SIGNATURE = b"%PDF-"
ZIP_SIGNATURE = b"PK\x03\x04"
DOCX_REQUIRED_ENTRY = "[Content_Types].xml"

SUPPORTED_EXTENSIONS = {".pdf", ".docx"}


class FileValidationError(Exception):
    """A resume file failed validation before it was stored or extracted."""


@dataclass(frozen=True)
class UploadLimits:
    max_size_bytes: int
    max_docx_decompressed_bytes: int


def _extension_of(filename: str) -> str:
    dot_index = filename.rfind(".")
    return filename[dot_index:].lower() if dot_index != -1 else ""


def validate_resume_file(filename: str, contents: bytes, limits: UploadLimits) -> None:
    """Validate a resume file before it is stored or extracted.

    Raises FileValidationError with a human-readable reason on any failure.
    Does not attempt to parse the document — that happens during extraction,
    after the file has been proven to be a well-formed PDF or DOCX.
    """
    if not filename or len(filename) > 255:
        raise FileValidationError("Filename is missing or too long")

    extension = _extension_of(filename)
    if extension not in SUPPORTED_EXTENSIONS:
        raise FileValidationError(
            f"Unsupported file type '{extension or 'unknown'}' — only .pdf and .docx are accepted"
        )

    if len(contents) == 0:
        raise FileValidationError("File is empty")

    if len(contents) > limits.max_size_bytes:
        max_mb = limits.max_size_bytes / (1024 * 1024)
        raise FileValidationError(f"File exceeds the maximum size of {max_mb:.0f} MB")

    if extension == ".pdf":
        _validate_pdf_signature(contents)
    else:
        _validate_docx_container(contents, limits)


def _validate_pdf_signature(contents: bytes) -> None:
    if not contents.startswith(PDF_SIGNATURE):
        raise FileValidationError(
            "File content does not match a PDF — the extension may be misleading"
        )


def _validate_docx_container(contents: bytes, limits: UploadLimits) -> None:
    if not contents.startswith(ZIP_SIGNATURE):
        raise FileValidationError(
            "File content does not match a DOCX — the extension may be misleading"
        )

    try:
        with zipfile.ZipFile(BytesIO(contents)) as archive:
            names = archive.namelist()
            if DOCX_REQUIRED_ENTRY not in names:
                raise FileValidationError("File is not a valid DOCX document")

            _enforce_decompressed_size_limit(archive, limits.max_docx_decompressed_bytes)
    except zipfile.BadZipFile as error:
        raise FileValidationError(
            "File is not a valid DOCX document (corrupted archive)"
        ) from error


_DECOMPRESS_CHUNK_BYTES = 1024 * 1024


def _enforce_decompressed_size_limit(archive: zipfile.ZipFile, max_bytes: int) -> None:
    """Decompresses every entry in bounded chunks, aborting as soon as the
    running total crosses the limit.

    ZipInfo.file_size is metadata read from the archive's central
    directory — it's attacker-controlled and not guaranteed to match what
    actually comes out on decompression, so a zip bomb can under-report it
    and sail past a check based on that field alone. Reading in fixed-size
    chunks and counting real bytes also keeps this check's own memory use
    bounded regardless of how large a malicious entry claims (or turns
    out) to be.
    """
    total = 0
    for entry in archive.infolist():
        with archive.open(entry) as member:
            while True:
                chunk = member.read(_DECOMPRESS_CHUNK_BYTES)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise FileValidationError(
                        "DOCX content is suspiciously large once decompressed"
                    )
