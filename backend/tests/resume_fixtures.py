import io

import pymupdf
from docx import Document


def make_pdf_bytes(text: str = "Experienced Python developer with 6 years of experience.") -> bytes:
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), text)
    data = document.tobytes()
    document.close()
    return data


def make_scanned_pdf_bytes() -> bytes:
    """A PDF with a page but no text layer, simulating a scanned resume."""
    document = pymupdf.open()
    document.new_page()
    data = document.tobytes()
    document.close()
    return data


def make_multi_page_pdf_bytes(page_count: int) -> bytes:
    document = pymupdf.open()
    for _ in range(page_count):
        page = document.new_page()
        page.insert_text((72, 72), "Filler page content for page count testing.")
    data = document.tobytes()
    document.close()
    return data


def make_encrypted_pdf_bytes() -> bytes:
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), "Secret resume content.")
    buffer = io.BytesIO()
    document.save(
        buffer,
        encryption=pymupdf.PDF_ENCRYPT_AES_256,
        owner_pw="owner-secret",
        user_pw="user-secret",
    )
    document.close()
    return buffer.getvalue()


def make_corrupted_pdf_bytes() -> bytes:
    return b"%PDF-1.4\n" + b"not a real pdf body" * 5


def make_docx_bytes(
    text: str = "Senior QA engineer with extensive automation testing experience.",
) -> bytes:
    document = Document()
    document.add_paragraph(text)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def make_corrupted_docx_bytes() -> bytes:
    # A valid zip with the required docx marker entry, but garbage XML inside
    # the entry python-docx actually parses — triggers a real parse failure
    # rather than being caught by the earlier container-level validation.
    import zipfile

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("[Content_Types].xml", "not valid xml <<<")
    return buffer.getvalue()
