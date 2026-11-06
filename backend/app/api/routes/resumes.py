import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services import resume_upload

router = APIRouter(prefix="/api/resumes", tags=["resumes"])

_MEDIA_TYPES = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


@router.get("/{resume_id}/file")
def get_resume_file(resume_id: uuid.UUID, db: Session = Depends(get_db)) -> FileResponse:
    resume = resume_upload.get_resume(db, resume_id)
    if resume is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found")

    path = Path(resume.storage_path)
    if not path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Stored resume file is missing"
        )

    extension = path.suffix.lower()
    return FileResponse(
        path,
        media_type=_MEDIA_TYPES.get(extension, "application/octet-stream"),
        filename=resume.original_filename,
        content_disposition_type="inline",
    )
