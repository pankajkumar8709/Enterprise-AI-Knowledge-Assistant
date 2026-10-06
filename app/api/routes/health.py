from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.session import get_db

router = APIRouter()


@router.get("/health", tags=["health"])
def health_check() -> dict[str, str]:
    """Liveness: process is up; must answer 200 without touching the DB."""

    return {"status": "ok"}


@router.get("/health/ready", tags=["health"], response_model=None)
def readiness_check(db: Session = Depends(get_db)) -> dict[str, str] | Response:
    """Readiness: verifies the database; 503 when it is unavailable (spec §8)."""

    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return Response(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content='{"detail":"database unavailable"}',
            media_type="application/json",
        )
    return {"status": "ready", "database": "connected"}
