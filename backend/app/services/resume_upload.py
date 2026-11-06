import contextlib
import logging
import uuid
from collections.abc import Generator
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.session import get_session_factory
from app.models.application import Application
from app.models.candidate import Candidate
from app.models.enums import BatchStatus, ExtractionStatus
from app.models.job import Job
from app.models.resume import Resume
from app.models.upload_batch import UploadBatch
from app.services.evaluation import run_preliminary_evaluation
from app.services.extraction import ExtractionLimits, extract_text
from app.services.file_validation import FileValidationError, UploadLimits, validate_resume_file
from app.services.storage import compute_file_hash, save_resume_file

logger = logging.getLogger(__name__)

OutcomeStatus = Literal["processed", "duplicate", "failed"]


@dataclass(frozen=True)
class ResumeUploadOutcome:
    filename: str
    status: OutcomeStatus
    candidate_id: uuid.UUID | None = None
    resume_id: uuid.UUID | None = None
    application_id: uuid.UUID | None = None
    error: str | None = None


def create_batch(db: Session, job: Job, total_count: int) -> UploadBatch:
    batch = UploadBatch(job_id=job.id, status=BatchStatus.PROCESSING, total_count=total_count)
    db.add(batch)
    db.commit()
    return batch


def process_uploaded_file(
    db: Session,
    job: Job,
    batch: UploadBatch,
    filename: str,
    contents: bytes,
    settings: Settings,
) -> ResumeUploadOutcome:
    """Validate, store, extract, and persist a single uploaded resume.

    Commits after this one file so a crash mid-batch does not lose already
    processed files, and so batch progress is visible to other connections
    as soon as each file finishes — not just at the end of the whole upload.
    """
    outcome = _process_file(db, job, batch, filename, contents, settings)
    _record_outcome(db, batch, outcome)
    return outcome


def _process_file(
    db: Session,
    job: Job,
    batch: UploadBatch,
    filename: str,
    contents: bytes,
    settings: Settings,
) -> ResumeUploadOutcome:
    upload_limits = UploadLimits(
        max_size_bytes=settings.max_upload_size_bytes,
        max_docx_decompressed_bytes=settings.max_docx_decompressed_bytes,
    )
    try:
        validate_resume_file(filename, contents, upload_limits)
    except FileValidationError as error:
        return ResumeUploadOutcome(filename=filename, status="failed", error=str(error))

    extension = Path(filename).suffix.lower()
    file_hash = compute_file_hash(contents)

    existing_resume = db.execute(
        select(Resume).where(Resume.file_hash == file_hash)
    ).scalar_one_or_none()

    if existing_resume is not None:
        return _attach_existing_resume(db, job, batch, filename, existing_resume)

    return _store_and_extract_new_resume(db, job, batch, filename, contents, extension, settings)


def _attach_existing_resume(
    db: Session, job: Job, batch: UploadBatch, filename: str, resume: Resume
) -> ResumeUploadOutcome:
    existing_application = db.execute(
        select(Application).where(
            Application.job_id == job.id, Application.resume_id == resume.id
        )
    ).scalar_one_or_none()

    if existing_application is not None:
        return ResumeUploadOutcome(
            filename=filename,
            status="duplicate",
            candidate_id=resume.candidate_id,
            resume_id=resume.id,
            application_id=existing_application.id,
        )

    application = Application(
        job_id=job.id, candidate_id=resume.candidate_id, resume_id=resume.id, batch_id=batch.id
    )
    db.add(application)
    db.flush()
    run_preliminary_evaluation(db, application, job, job.requirements)
    return ResumeUploadOutcome(
        filename=filename,
        status="processed",
        candidate_id=resume.candidate_id,
        resume_id=resume.id,
        application_id=application.id,
    )


def _store_and_extract_new_resume(
    db: Session,
    job: Job,
    batch: UploadBatch,
    filename: str,
    contents: bytes,
    extension: str,
    settings: Settings,
) -> ResumeUploadOutcome:
    candidate = Candidate()
    db.add(candidate)
    db.flush()

    storage_path = save_resume_file(contents, extension, settings.resume_storage_dir)
    extraction_limits = ExtractionLimits(
        max_pdf_pages=settings.max_pdf_pages, max_extracted_chars=settings.max_extracted_chars
    )
    extraction = extract_text(storage_path, extension, extraction_limits)

    file_hash = compute_file_hash(contents)
    resume = Resume(
        candidate_id=candidate.id,
        original_filename=filename[:255],
        storage_path=storage_path,
        file_hash=file_hash,
        extracted_text=extraction.text,
        extraction_status=extraction.status,
    )
    db.add(resume)
    try:
        db.flush()
    except IntegrityError:
        # Lost a race against a near-simultaneous upload of the identical
        # file content — the unique constraint on resumes.file_hash caught
        # it. The extraction work above wasn't wasted (it's cheap and the
        # stored file is simply orphaned, not harmful), but we must not
        # create a second Resume/Candidate for what the other request
        # already established is the same resume — attach to its result
        # instead, same as the normal duplicate-hash path.
        db.rollback()
        existing_resume = db.execute(
            select(Resume).where(Resume.file_hash == file_hash)
        ).scalar_one_or_none()
        if existing_resume is not None:
            return _attach_existing_resume(db, job, batch, filename, existing_resume)
        raise

    application = Application(
        job_id=job.id, candidate_id=candidate.id, resume_id=resume.id, batch_id=batch.id
    )
    db.add(application)
    db.flush()
    run_preliminary_evaluation(db, application, job, job.requirements)

    if extraction.status == ExtractionStatus.FAILED:
        return ResumeUploadOutcome(
            filename=filename,
            status="failed",
            candidate_id=candidate.id,
            resume_id=resume.id,
            application_id=application.id,
            error=extraction.error,
        )

    return ResumeUploadOutcome(
        filename=filename,
        status="processed",
        candidate_id=candidate.id,
        resume_id=resume.id,
        application_id=application.id,
    )


def _outcome_to_json(outcome: ResumeUploadOutcome) -> dict:
    data = asdict(outcome)
    for key in ("candidate_id", "resume_id", "application_id"):
        if data[key] is not None:
            data[key] = str(data[key])
    return data


def _record_outcome(db: Session, batch: UploadBatch, outcome: ResumeUploadOutcome) -> None:
    if outcome.status == "failed":
        batch.failed_count += 1
    else:
        batch.processed_count += 1
    # Reassign rather than .append() — SQLAlchemy's change tracking for a
    # plain JSONB column only fires on attribute assignment, not on
    # mutating the Python list object in place.
    batch.results_json = [*batch.results_json, _outcome_to_json(outcome)]
    db.commit()


def get_resume(db: Session, resume_id: uuid.UUID) -> Resume | None:
    return db.execute(select(Resume).where(Resume.id == resume_id)).scalar_one_or_none()


def get_batch(db: Session, job_id: uuid.UUID, batch_id: uuid.UUID) -> UploadBatch | None:
    return db.execute(
        select(UploadBatch).where(UploadBatch.id == batch_id, UploadBatch.job_id == job_id)
    ).scalar_one_or_none()


def finalize_batch(db: Session, batch: UploadBatch) -> UploadBatch:
    if batch.failed_count == 0:
        batch.status = BatchStatus.COMPLETED
    elif batch.processed_count == 0:
        batch.status = BatchStatus.FAILED
    else:
        batch.status = BatchStatus.PARTIAL
    batch.completed_at = datetime.now(UTC)
    db.commit()
    return batch


def process_batch_files(
    db: Session,
    job: Job,
    batch: UploadBatch,
    files: list[tuple[str, bytes]],
    settings: Settings,
) -> None:
    """Drives one upload batch to completion, one file at a time.

    An unexpected exception while processing one file must not abort the
    rest of the batch or leave it stuck in "processing" forever — same
    resilience pattern as run_ai_evaluations_for_job (QA-004). Roll back
    just the broken file, record it as failed, and continue.
    """
    for filename, contents in files:
        try:
            process_uploaded_file(db, job, batch, filename, contents, settings)
        except Exception:
            db.rollback()
            logger.exception(
                "resume_upload_unexpected_failure filename=%s batch_id=%s job_id=%s",
                filename,
                batch.id,
                job.id,
            )
            _record_outcome(
                db,
                batch,
                ResumeUploadOutcome(
                    filename=filename,
                    status="failed",
                    error="An unexpected error occurred while processing this file.",
                ),
            )
    finalize_batch(db, batch)


@contextlib.contextmanager
def open_background_session() -> Generator[Session, None, None]:
    """Acquires a database session for background batch processing.

    A dedicated seam rather than calling get_session_factory() directly:
    FastAPI tears down request-scoped dependencies (including the `db`
    session from get_db) as part of sending the response, before running
    background tasks, so a background task needs a session of its own
    rather than reusing an already-closed one. Tests, which run an entire
    request inside one shared, SAVEPOINT-wrapped session for isolation,
    override this to yield that same session instead — a disconnected one
    would never see a test's not-yet-(really)-committed data.
    """
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()


def run_upload_batch_in_background(
    job_id: uuid.UUID,
    batch_id: uuid.UUID,
    files: list[tuple[str, bytes]],
    settings: Settings,
) -> None:
    """Background-task entry point, run after the upload response is sent."""
    with open_background_session() as db:
        try:
            job = db.execute(select(Job).where(Job.id == job_id)).scalar_one_or_none()
            batch = db.execute(
                select(UploadBatch).where(UploadBatch.id == batch_id)
            ).scalar_one_or_none()
            if job is None or batch is None:
                logger.error(
                    "resume_upload_background_missing_row job_id=%s batch_id=%s",
                    job_id,
                    batch_id,
                )
                return
            process_batch_files(db, job, batch, files, settings)
        except Exception:
            # Last-resort net: process_batch_files already isolates per-file
            # failures, so reaching here means something broke outside that
            # loop (e.g. the DB connection itself). Still try to close out
            # the batch rather than leaving it stuck in "processing" forever.
            logger.exception(
                "resume_upload_background_task_crashed job_id=%s batch_id=%s", job_id, batch_id
            )
            db.rollback()
            batch = db.execute(
                select(UploadBatch).where(UploadBatch.id == batch_id)
            ).scalar_one_or_none()
            if batch is not None:
                finalize_batch(db, batch)
