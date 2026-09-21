"""Ideas API routes — list and retrieve generated ideas."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.database.models.idea import Idea as IdeaModel, IdeaStatus
from app.database.models.research import ResearchRun

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["ideas"])


def _format_idea(idea: IdeaModel) -> dict:
    """Format an Idea model for API response."""
    return {
        "id": idea.id,
        "research_run_id": idea.research_run_id,
        "title": idea.title,
        "problem": idea.problem,
        "solution": idea.solution,
        "target_users": idea.target_users,
        "mvp": idea.mvp,
        "monetization": idea.monetization,
        "differentiation": idea.differentiation,
        "technical_complexity": idea.technical_complexity,
        "risks": idea.risks,
        "validation_plan": idea.validation_plan,
        "status": idea.status.value,
        "created_at": idea.created_at.isoformat() if idea.created_at else None,
        "updated_at": idea.updated_at.isoformat() if idea.updated_at else None,
    }


@router.get("/ideas")
async def list_ideas(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    status: str | None = Query(None, description="Filter by status"),
    db: Session = Depends(get_db),
) -> dict:
    """List all ideas with optional status filtering."""
    query = db.query(IdeaModel)

    if status:
        try:
            status_enum = IdeaStatus(status)
            query = query.filter(IdeaModel.status == status_enum)
        except ValueError:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid status '{status}'. Must be one of: {', '.join(s.value for s in IdeaStatus)}",
            )

    total = query.count()
    ideas = (
        query.order_by(IdeaModel.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return {
        "items": [_format_idea(i) for i in ideas],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get(
    "/ideas/{idea_id}",
    responses={404: {"description": "Idea not found"}},
)
async def get_idea(
    idea_id: int,
    db: Session = Depends(get_db),
) -> dict:
    """Get a single idea by ID with full structured opportunity information."""
    idea = db.query(IdeaModel).filter(IdeaModel.id == idea_id).first()
    if not idea:
        raise HTTPException(status_code=404, detail="Idea not found")

    return _format_idea(idea)


@router.get(
    "/research/{research_id}/ideas",
    responses={404: {"description": "Research run not found"}},
)
async def get_research_ideas(
    research_id: int,
    db: Session = Depends(get_db),
) -> dict:
    """Get all ideas generated from a specific research run."""
    run = db.query(ResearchRun).filter(ResearchRun.id == research_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Research run not found")

    ideas = (
        db.query(IdeaModel)
        .filter(IdeaModel.research_run_id == research_id)
        .order_by(IdeaModel.created_at.desc())
        .all()
    )

    return {
        "research_id": research_id,
        "topic": run.topic,
        "ideas": [_format_idea(i) for i in ideas],
    }
