"""Analysis API routes — multi-agent pipeline and status."""

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.agents.orchestrator import AgentOrchestrator, run_analysis_pipeline
from app.database.database import get_db
from app.database.models.agent_run import AgentRun
from app.database.models.research import ResearchRun, ResearchStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/research", tags=["analysis"])


async def _run_pipeline_background(research_id: int) -> None:
    """Run the analysis pipeline in the background.

    NOTE: This is a FastAPI BackgroundTask — not a durable worker.
    If the process crashes, the pipeline is lost.
    Future phase: move to Celery/Redis for durable execution.
    """
    from app.database.database import _get_engine
    from sqlalchemy.orm import sessionmaker

    engine = _get_engine()
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    db = SessionLocal()
    try:
        result = await run_analysis_pipeline(research_id, db, num_ideas=4)
        logger.info("Background pipeline completed | result=%s", result)
    except Exception:
        logger.exception("Background pipeline failed | research_id=%d", research_id)
    finally:
        db.close()


@router.post(
    "/{research_id}/analyze",
    status_code=202,
    responses={
        404: {"description": "Research run not found"},
        409: {"description": "Research run is not completed or already analyzing"},
    },
)
async def analyze_research(
    research_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> dict:
    """Run the multi-agent analysis pipeline for a completed research run.

    Runs asynchronously in the background. Check status via
    GET /api/research/{research_id}/analysis-status.
    """
    run = db.query(ResearchRun).filter(ResearchRun.id == research_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Research run not found")

    if run.status not in (ResearchStatus.COMPLETED, ResearchStatus.FAILED):
        raise HTTPException(
            status_code=409,
            detail={
                "code": "RESEARCH_NOT_READY",
                "message": f"Research run is in '{run.status.value}' state. "
                           "Must be 'completed' to analyze.",
            },
        )

    # Check if analysis is already running
    running_agents = (
        db.query(AgentRun)
        .filter(
            AgentRun.research_run_id == research_id,
            AgentRun.status == "running",
        )
        .count()
    )
    if running_agents > 0:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "ANALYSIS_IN_PROGRESS",
                "message": "Analysis pipeline is already running for this research.",
            },
        )

    background_tasks.add_task(_run_pipeline_background, research_id)

    return {
        "research_id": research_id,
        "status": "accepted",
        "message": "Analysis pipeline started in background.",
    }


@router.get(
    "/{research_id}/analysis-status",
    responses={404: {"description": "Research run not found"}},
)
async def get_analysis_status(
    research_id: int,
    db: Session = Depends(get_db),
) -> dict:
    """Get the current status of the analysis pipeline for a research run."""
    run = db.query(ResearchRun).filter(ResearchRun.id == research_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Research run not found")

    agent_runs = (
        db.query(AgentRun)
        .filter(AgentRun.research_run_id == research_id)
        .order_by(AgentRun.id)
        .all()
    )

    completed_names = [ar.agent_name for ar in agent_runs if ar.status.value == "completed"]
    running = [ar for ar in agent_runs if ar.status.value == "running"]
    current_agent = running[0].agent_name if running else None

    # Determine overall pipeline status
    pipeline_status = "idle"
    if running:
        pipeline_status = "running"
    elif any(ar.status.value == "failed" for ar in agent_runs):
        pipeline_status = "failed"
    elif len(completed_names) >= 5:
        pipeline_status = "completed"

    total_agents = 5

    return {
        "research_id": research_id,
        "status": pipeline_status,
        "current_agent": current_agent,
        "completed_agents": len(completed_names),
        "total_agents": total_agents,
        "started_at": agent_runs[0].started_at.isoformat() if agent_runs and agent_runs[0].started_at else None,
        "completed_at": (
            agent_runs[-1].completed_at.isoformat()
            if agent_runs and agent_runs[-1].completed_at and pipeline_status != "running"
            else None
        ),
    }


@router.get(
    "/{research_id}/agents",
    responses={404: {"description": "Research run not found"}},
)
async def get_agent_runs(
    research_id: int,
    db: Session = Depends(get_db),
) -> dict:
    """Get agent execution history for a research run."""
    run = db.query(ResearchRun).filter(ResearchRun.id == research_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Research run not found")

    agent_runs = (
        db.query(AgentRun)
        .filter(AgentRun.research_run_id == research_id)
        .order_by(AgentRun.id)
        .all()
    )

    return {
        "research_id": research_id,
        "agents": [
            {
                "agent_name": ar.agent_name,
                "status": ar.status.value,
                "model": ar.model,
                "started_at": ar.started_at.isoformat() if ar.started_at else None,
                "completed_at": ar.completed_at.isoformat() if ar.completed_at else None,
                "input_tokens": ar.input_tokens,
                "output_tokens": ar.output_tokens,
            }
            for ar in agent_runs
        ],
    }
