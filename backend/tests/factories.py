from decimal import Decimal

from sqlalchemy.orm import Session

from app.models import Application, Candidate, Job, JobRequirement, Resume, UploadBatch
from app.models.enums import ExtractionStatus, RequirementCategory, ReviewStatus


def make_job(db: Session, **overrides) -> Job:
    job = Job(
        title=overrides.get("title", "Senior Backend Engineer"),
        description_md=overrides.get("description_md", "## Requirements\n- Python\n"),
        rubric_version=overrides.get("rubric_version", 1),
    )
    db.add(job)
    db.flush()
    return job


def make_job_requirement(db: Session, job: Job, **overrides) -> JobRequirement:
    requirement = JobRequirement(
        job_id=job.id,
        description=overrides.get("description", "5+ years of Python experience"),
        category=overrides.get("category", RequirementCategory.MANDATORY),
        weight=overrides.get("weight", Decimal("1.0")),
        sort_order=overrides.get("sort_order", 0),
    )
    db.add(requirement)
    db.flush()
    return requirement


def make_candidate(db: Session, **overrides) -> Candidate:
    candidate = Candidate(display_name=overrides.get("display_name", "Jane Doe"))
    db.add(candidate)
    db.flush()
    return candidate


def make_resume(db: Session, candidate: Candidate, **overrides) -> Resume:
    resume = Resume(
        candidate_id=candidate.id,
        original_filename=overrides.get("original_filename", "resume.pdf"),
        storage_path=overrides.get("storage_path", "/tmp/storage/resume.pdf"),
        file_hash=overrides.get("file_hash", "deadbeef"),
        extraction_status=overrides.get("extraction_status", ExtractionStatus.COMPLETED),
    )
    db.add(resume)
    db.flush()
    return resume


def make_application(
    db: Session, job: Job, candidate: Candidate, resume: Resume, **overrides
) -> Application:
    application = Application(
        job_id=job.id,
        candidate_id=candidate.id,
        resume_id=resume.id,
        batch_id=overrides.get("batch_id"),
        review_status=overrides.get("review_status", ReviewStatus.UNREVIEWED),
    )
    db.add(application)
    db.flush()
    return application


def make_upload_batch(db: Session, job: Job, **overrides) -> UploadBatch:
    batch = UploadBatch(
        job_id=job.id,
        total_count=overrides.get("total_count", 1),
    )
    db.add(batch)
    db.flush()
    return batch
