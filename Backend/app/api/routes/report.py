"""Report generation API routes."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.database.models.research import ResearchRun
from app.reports.errors import ReportAlreadyExistsError, ReportGenerationError, ReportNotFoundError
from app.reports.service import ReportService
from app.schemas.research import AIErrorResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/research", tags=["report"])


@router.post(
    "/{research_id}/report",
    responses={
        404: {"description": "Research run not found"},
        500: {"model": AIErrorResponse, "description": "Report generation error"},
    },
)
async def generate_report(
    research_id: int,
    db: Session = Depends(get_db),
) -> dict:
    """Generate a Markdown research report for a completed analysis.

    The report is generated from data stored in the database.
    Idempotent: returns existing report metadata if already generated.
    Use force=true to regenerate.
    """
    run = db.query(ResearchRun).filter(ResearchRun.id == research_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Research run not found")

    service = ReportService()
    try:
        result = service.generate_report(research_id, db)
    except ReportNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ReportGenerationError as exc:
        raise HTTPException(
            status_code=500,
            detail={
                "code": "REPORT_GENERATION_ERROR",
                "message": str(exc),
            },
        ) from exc

    return result


@router.get(
    "/{research_id}/report",
    responses={
        404: {"description": "Research run not found"},
    },
)
async def get_report(
    research_id: int,
    db: Session = Depends(get_db),
) -> dict:
    """Get the generated report content for a research run.

    Returns the Markdown content if available.
    """
    run = db.query(ResearchRun).filter(ResearchRun.id == research_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Research run not found")

    service = ReportService()
    try:
        return service.get_report_content(research_id, db)
    except ReportNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
