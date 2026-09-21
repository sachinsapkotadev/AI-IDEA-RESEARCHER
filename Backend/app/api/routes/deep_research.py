"""Deep Research API routes — 12-hour iterative research loop."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.deep_research.engine import start_deep_research, get_job, list_jobs, stop_deep_research

router = APIRouter()


class DeepResearchCreateRequest(BaseModel):
    topic: str = Field(..., min_length=3, max_length=1000, description="Research topic")


class DeepResearchCreateResponse(BaseModel):
    job_id: str
    topic: str
    status: str
    message: str


class DeepResearchStatusResponse(BaseModel):
    job_id: str
    topic: str
    status: str
    current_iteration: int
    max_iterations: int
    started_at: str | None
    completed_at: str | None
    elapsed_hours: float
    sub_queries: list[str]
    iteration_log: list[dict]
    final_answer: str | None
    error: str | None
    sources_collected: int
    agents_run: int
    progress_pct: float


@router.post("/api/deep-research", response_model=DeepResearchCreateResponse)
async def create_deep_research(
    body: DeepResearchCreateRequest,
    db: Session = Depends(get_db),
) -> DeepResearchCreateResponse:
    """Start a deep research job (runs for up to 12 hours in background)."""
    job = await start_deep_research(body.topic, db)
    return DeepResearchCreateResponse(
        job_id=job.job_id,
        topic=job.topic,
        status=job.status,
        message="Deep research started. Poll /api/deep-research/{job_id} for progress.",
    )


@router.get("/api/deep-research/{job_id}", response_model=DeepResearchStatusResponse)
async def get_deep_research_status(job_id: str) -> DeepResearchStatusResponse:
    """Get status of a deep research job."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    d = job.to_dict()
    return DeepResearchStatusResponse(**d)


@router.post("/api/deep-research/{job_id}/stop")
async def stop_deep_research_job(job_id: str) -> dict:
    """Stop a running deep research job."""
    stopped = await stop_deep_research(job_id)
    if not stopped:
        raise HTTPException(status_code=404, detail="Job not found or not running")
    return {"job_id": job_id, "status": "stopped", "message": "Research stopped"}


@router.get("/api/deep-research")
async def list_deep_research_jobs() -> dict:
    """List all deep research jobs."""
    jobs = list_jobs()
    return {"jobs": jobs, "total": len(jobs)}
