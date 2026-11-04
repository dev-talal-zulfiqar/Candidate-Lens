from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from app.db.session import check_database_connection

router = APIRouter()


class HealthResponse(BaseModel):
    status: Literal["ok"]
    database: Literal["ok", "error"]


@router.get("/health", response_model=HealthResponse)
def get_health() -> HealthResponse:
    database_status: Literal["ok", "error"] = (
        "ok" if check_database_connection() else "error"
    )
    return HealthResponse(status="ok", database=database_status)
