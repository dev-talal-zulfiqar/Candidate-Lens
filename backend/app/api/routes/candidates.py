import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.candidate_detail import CandidateDetail
from app.services import candidate_detail as candidate_detail_service

router = APIRouter(prefix="/api/candidates", tags=["candidates"])


@router.get("/{candidate_id}", response_model=CandidateDetail)
def get_candidate(candidate_id: uuid.UUID, db: Session = Depends(get_db)) -> CandidateDetail:
    detail = candidate_detail_service.get_candidate_detail(db, candidate_id)
    if detail is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found")
    return detail
