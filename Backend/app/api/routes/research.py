"""Research API routes."""

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
from app.core.config import get_settings
from app.database.database import get_db
from app.database.models.research import ResearchRun
from app.database.models.source import ResearchSource
from app.research.errors import NoUsableSourcesError, SearchConfigurationError, SearchProviderError
from app.research.service import ResearchService
from app.schemas.research import (
    AIErrorResponse,
    ResearchCreateRequest,
    ResearchListResponse,
    ResearchRunResponse,
    ResearchResultResponse,
    ResearchSourcesResponse,
    SourceResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/research", tags=["research"])


def _format_run(run: ResearchRun) -> ResearchRunResponse:
    """Format a ResearchRun for API response."""
    import json

    result = None
    sources_count = len(run.sources) if run.sources else 0
    sources_used = 0

    if run.report_path:
        try:
            result_data = json.loads(run.report_path)
            result = ResearchResultResponse(**result_data)
            sources_used = len(result.source_references)
        except Exception:
            pass

    return ResearchRunResponse(
        id=run.id,
        topic=run.topic,
        status=run.status.value,
        sources_found=sources_count,
        sources_used=sources_used,
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

    Performs real web search, content extraction, and AI analysis.
    """
    settings = get_settings()
    topic = request.topic.strip()

    # Basic concurrency check
    running_count = (
        db.query(ResearchRun)
        .filter(ResearchRun.status == "running")
        .count()
    )
    if running_count >= settings.MAX_CONCURRENT_RESEARCH:
        raise HTTPException(
            status_code=429,
            detail={
                "code": "TOO_MANY_RESEARCH_RUNS",
                "message": "Maximum concurrent research runs reached. Try again later.",
            },
        )

    # Create research run
    research_run = ResearchRun(topic=topic)
    db.add(research_run)
    db.flush()

    # Run the research pipeline
    service = ResearchService()
    try:
        result = await service.run(research_run, db)
    except SearchConfigurationError as exc:
        research_run.status = "failed"
        db.commit()
        raise HTTPException(
            status_code=503,
            detail={
                "code": "SEARCH_CONFIGURATION_ERROR",
                "message": "Search provider is not configured. Set SEARCH_API_KEY and SEARCH_ENGINE_ID.",
            },
        ) from exc
    except SearchProviderError as exc:
        research_run.status = "failed"
        db.commit()
        raise HTTPException(
            status_code=503,
            detail={
                "code": "SEARCH_PROVIDER_ERROR",
                "message": "Search provider error. Try again later.",
            },
        ) from exc
    except NoUsableSourcesError as exc:
        research_run.status = "failed"
        db.commit()
        raise HTTPException(
            status_code=422,
            detail={
                "code": "NO_USABLE_SOURCES",
                "message": str(exc),
            },
        ) from exc
    except AIConfigurationError as exc:
        research_run.status = "failed"
        db.commit()
        raise HTTPException(
            status_code=503,
            detail={
                "code": "AI_CONFIGURATION_ERROR",
                "message": "AI provider is not configured. Set OPENROUTER_API_KEY.",
            },
        ) from exc
    except AIRateLimitError as exc:
        research_run.status = "failed"
        db.commit()
        raise HTTPException(
            status_code=429,
            detail={
                "code": "AI_RATE_LIMIT_ERROR",
                "message": "AI provider rate limit exceeded. Try again later.",
            },
        ) from exc
    except AITimeoutError as exc:
        research_run.status = "failed"
        db.commit()
        raise HTTPException(
            status_code=504,
            detail={
                "code": "AI_TIMEOUT_ERROR",
                "message": "AI provider request timed out.",
            },
        ) from exc
    except AIResponseParsingError as exc:
        research_run.status = "failed"
        db.commit()
        raise HTTPException(
            status_code=502,
            detail={
                "code": "AI_RESPONSE_PARSE_ERROR",
                "message": "Could not parse AI response.",
            },
        ) from exc
    except AIResponseValidationError as exc:
        research_run.status = "failed"
        db.commit()
        raise HTTPException(
            status_code=502,
            detail={
                "code": "AI_RESPONSE_VALIDATION_ERROR",
                "message": "AI response failed validation.",
            },
        ) from exc
    except AIProviderError as exc:
        research_run.status = "failed"
        db.commit()
        raise HTTPException(
            status_code=503,
            detail={
                "code": "AI_PROVIDER_ERROR",
                "message": "The AI provider is temporarily unavailable.",
            },
        ) from exc

    # Refresh to get relationships
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
    run = (
        db.query(ResearchRun)
        .filter(ResearchRun.id == research_id)
        .first()
    )
    if not run:
        raise HTTPException(status_code=404, detail="Research run not found")
    return _format_run(run)


@router.get(
    "/{research_id}/sources",
    response_model=ResearchSourcesResponse,
    responses={404: {"description": "Research run not found"}},
)
async def get_research_sources(
    research_id: int,
    db: Session = Depends(get_db),
) -> ResearchSourcesResponse:
    """Get sources for a research run."""
    run = (
        db.query(ResearchRun)
        .filter(ResearchRun.id == research_id)
        .first()
    )
    if not run:
        raise HTTPException(status_code=404, detail="Research run not found")

    sources = (
        db.query(ResearchSource)
        .filter(ResearchSource.research_run_id == research_id)
        .order_by(ResearchSource.rank)
        .all()
    )

    source_list = [
        SourceResponse(
            id=s.id,
            title=s.title,
            url=s.url,
            source_type=s.source_type.value if s.source_type else "web",
            domain=s.domain,
            quality=s.quality,
            status=s.status.value if s.status else "unknown",
            word_count=s.word_count,
            rank=s.rank,
        )
        for s in sources
    ]

    return ResearchSourcesResponse(
        research_id=run.id,
        topic=run.topic,
        sources=source_list,
    )
