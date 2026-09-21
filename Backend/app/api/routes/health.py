"""Health check routes."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.database import check_database_connection, get_db
from app.schemas.health import DatabaseHealthResponse, HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Return service health status."""
    return HealthResponse(status="ok")


@router.get("/health/database", response_model=DatabaseHealthResponse)
async def database_health(db: Session = Depends(get_db)) -> DatabaseHealthResponse:
    """Check database connectivity."""
    db_ok = check_database_connection()
    if not db_ok:
        return DatabaseHealthResponse(status="error", database="disconnected")
    return DatabaseHealthResponse(status="ok", database="connected")
