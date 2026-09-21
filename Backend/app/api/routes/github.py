"""GitHub integration API routes."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.database.models.research import ResearchRun
from app.github.errors import (
    GitHubAuthenticationError,
    GitHubConfigurationError,
    GitHubRepositoryNotFoundError,
    GitHubPublicationError,
)
from app.github.service import GitHubService
from app.schemas.research import AIErrorResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/research", tags=["github"])


@router.post(
    "/{research_id}/github",
    responses={
        404: {"description": "Research run not found"},
        503: {"model": AIErrorResponse, "description": "GitHub configuration error"},
    },
)
async def publish_to_github(
    research_id: int,
    db: Session = Depends(get_db),
) -> dict:
    """Publish the research report to a GitHub branch.

    Creates a research/YYYY-MM-DD branch and commits the report file.
    Human review is required before merging to main.
    Idempotent: returns existing publication if already published.
    """
    run = db.query(ResearchRun).filter(ResearchRun.id == research_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Research run not found")

    service = GitHubService()
    try:
        return await service.publish_report(research_id, db)
    except GitHubConfigurationError as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "GITHUB_CONFIGURATION_ERROR",
                "message": str(exc),
            },
        ) from exc
    except GitHubAuthenticationError as exc:
        raise HTTPException(
            status_code=401,
            detail={
                "code": "GITHUB_AUTH_ERROR",
                "message": "GitHub authentication failed. Check GITHUB_TOKEN.",
            },
        ) from exc
    except GitHubRepositoryNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "GITHUB_REPO_NOT_FOUND",
                "message": str(exc),
            },
        ) from exc
    except GitHubPublicationError as exc:
        raise HTTPException(
            status_code=500,
            detail={
                "code": "GITHUB_PUBLICATION_ERROR",
                "message": str(exc),
            },
        ) from exc


@router.get(
    "/{research_id}/github",
    responses={404: {"description": "Research run not found"}},
)
async def get_github_status(
    research_id: int,
    db: Session = Depends(get_db),
) -> dict:
    """Get GitHub publication status for a research run."""
    run = db.query(ResearchRun).filter(ResearchRun.id == research_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Research run not found")

    service = GitHubService()
    result = await service.get_publication_status(research_id, db)
    if result is None:
        return {"research_id": research_id, "status": "not_published"}
    return result
