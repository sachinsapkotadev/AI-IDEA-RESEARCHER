"""Research API routes."""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.ai.errors import (
    AIConfigurationError,
    AIProviderError,
    AIResponseParsingError,
    AIResponseValidationError,
    AIRateLimitError,
    AITimeoutError,
)
from app.ai.research_agent import ResearchAgent
from app.database.database import get_db
from app.database.models.research import ResearchRun
from app.schemas.research import (
    AIErrorResponse,
    ResearchCreateRequest,
    ResearchListResponse,
    ResearchRunResponse,
    ResearchResultResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/research", tags=["research"])


def _format_run(run: ResearchRun) -> ResearchRunResponse:
    """Format a ResearchRun for API response."""
    result = None
    if run.report_path:
        try:
            result_data = json.loads(run.report_path)
            result = ResearchResultResponse(**result_data)
        except (json.JSONDecodeError, Exception):
            pass

    return ResearchRunResponse(
        id=run.id,
        topic=run.topic,
        status=run.status.value,
        result=result,
        started_at=run.started_at.isoformat() if run.started_at else None,
        completed_at=run.completed_at.isoformat() if run.completed_at else None,
        created_at=run.created_at.isoformat(),
    )


@router.post(
    "",
    response_model=ResearchRunResponse,
    status_code=201,
    responses={
        422: {"description": "Validation error"},
        503: {"model": AIErrorResponse, "description": "AI provider error"},
    },
)
async def create_research(
    request: ResearchCreateRequest,
    db: Session = Depends(get_db),
) -> ResearchRunResponse:
    """Start a new research run on the given topic.

    Creates a ResearchRun, invokes the AI Research Agent,
    validates the result, and saves it.
    """
    topic = request.topic.strip()

    # Create research run
    research_run = ResearchRun(topic=topic)
    db.add(research_run)
    db.flush()

    # Run the research agent
    agent = ResearchAgent()
    try:
        result = await agent.run(research_run, db)
    except AIConfigurationError as exc:
        research_run.status = "failed"
        db.flush()
        raise HTTPException(
            status_code=503,
            detail={
                "code": "AI_CONFIGURATION_ERROR",
                "message": "AI provider is not configured. Set OPENROUTER_API_KEY.",
            },
        ) from exc
    except AIRateLimitError as exc:
        research_run.status = "failed"
        db.flush()
        raise HTTPException(
            status_code=429,
            detail={
                "code": "AI_RATE_LIMIT_ERROR",
                "message": "AI provider rate limit exceeded. Try again later.",
            },
        ) from exc
    except AITimeoutError as exc:
        research_run.status = "failed"
        db.flush()
        raise HTTPException(
            status_code=504,
            detail={
                "code": "AI_TIMEOUT_ERROR",
                "message": "AI provider request timed out.",
            },
        ) from exc
    except AIResponseParsingError as exc:
        research_run.status = "failed"
        db.flush()
        raise HTTPException(
            status_code=502,
            detail={
                "code": "AI_RESPONSE_PARSE_ERROR",
                "message": "Could not parse AI response.",
            },
        ) from exc
    except AIResponseValidationError as exc:
        research_run.status = "failed"
        db.flush()
        raise HTTPException(
            status_code=502,
            detail={
                "code": "AI_RESPONSE_VALIDATION_ERROR",
                "message": "AI response failed validation.",
            },
        ) from exc
    except AIProviderError as exc:
        research_run.status = "failed"
        db.flush()
        raise HTTPException(
            status_code=503,
            detail={
                "code": "AI_PROVIDER_ERROR",
                "message": "The AI provider is temporarily unavailable.",
            },
        ) from exc

    # Save the result as JSON in report_path
    research_run.report_path = result.model_dump_json()
    db.commit()
    db.refresh(research_run)

    return _format_run(research_run)


@router.get("", response_model=ResearchListResponse)
async def list_research(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
) -> ResearchListResponse:
    """List research runs with pagination."""
    offset = (page - 1) * page_size

    total = db.query(ResearchRun).count()
    runs = (
        db.query(ResearchRun)
        .order_by(ResearchRun.created_at.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )

    return ResearchListResponse(
        items=[_format_run(r) for r in runs],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{research_id}",
    response_model=ResearchRunResponse,
    responses={404: {"description": "Research run not found"}},
)
async def get_research(
    research_id: int,
    db: Session = Depends(get_db),
) -> ResearchRunResponse:
    """Get a single research run by ID."""
    run = db.query(ResearchRun).filter(ResearchRun.id == research_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Research run not found")
    return _format_run(run)
