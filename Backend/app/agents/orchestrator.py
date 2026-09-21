"""Agent Orchestrator — manages the multi-agent analysis pipeline."""

import json
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.agents.context_utils import build_source_context, build_source_references
from app.agents.market import MarketAnalyst
from app.agents.competitor import CompetitorAnalyst
from app.agents.idea import IdeaGenerator
from app.agents.technical import TechnicalAnalyst
from app.agents.validation import ValidationPlanner
from app.ai.provider import OpenRouterProvider
from app.database.models.agent_run import AgentRun, AgentRunStatus
from app.database.models.idea import Idea as IdeaModel, IdeaStatus
from app.database.models.research import ResearchRun, ResearchStatus
from app.database.models.source import ResearchSource

logger = logging.getLogger(__name__)

# Pipeline agent ordering
PIPELINE_AGENTS = [
    "MarketAnalyst",
    "CompetitorAnalyst",
    "IdeaGenerator",
    "TechnicalAnalyst",
    "ValidationPlanner",
]


class AgentOrchestrator:
    """Orchestrates the multi-agent analysis pipeline.

    Pipeline:
    1. Load research data (ResearchRun + ResearchSource records)
    2. Build compact source context
    3. Run Market Analyst
    4. Run Competitor Analyst
    5. Run Idea Generator
    6. Run Technical Analyst
    7. Run Validation Planner
    8. Save results to database (Idea model)
    9. Record overall status

    Failure handling:
    - If any required agent fails, stop the pipeline
    - Record the failure in AgentRun
    - Mark the research run appropriately
    """

    def __init__(self, provider: OpenRouterProvider | None = None) -> None:
        self._provider = provider or OpenRouterProvider()
        self._market_analyst = MarketAnalyst(provider=self._provider)
        self._competitor_analyst = CompetitorAnalyst(provider=self._provider)
        self._idea_generator = IdeaGenerator(provider=self._provider)
        self._technical_analyst = TechnicalAnalyst(provider=self._provider)
        self._validation_planner = ValidationPlanner(provider=self._provider)

    async def run(
        self,
        research_run: ResearchRun,
        db: Session,
        num_ideas: int = 4,
    ) -> dict[str, Any]:
        """Execute the full multi-agent analysis pipeline.

        Args:
            research_run: The completed ResearchRun to analyze.
            db: Database session.
            num_ideas: Number of ideas to generate (default 4).

        Returns:
            Dict with status, ideas_generated, and other metadata.

        Raises:
            ValueError: If research_run is not completed.
        """
        if research_run.status != ResearchStatus.COMPLETED:
            raise ValueError(
                f"ResearchRun must be completed before analysis. "
                f"Current status: {research_run.status.value}"
            )

        start_time = datetime.now(timezone.utc)
        logger.info(
            "Pipeline started | research_run_id=%d | topic=%s",
            research_run.id, research_run.topic[:80],
        )

        # Update research run status
        research_run.status = ResearchStatus.RUNNING
        db.flush()

        # Load sources
        sources = (
            db.query(ResearchSource)
            .filter(ResearchSource.research_run_id == research_run.id)
            .filter(ResearchSource.status == "success")
            .order_by(ResearchSource.rank)
            .all()
        )

        if not sources:
            research_run.status = ResearchStatus.FAILED
            research_run.completed_at = datetime.now(timezone.utc)
            db.flush()
            db.commit()
            raise ValueError("No successful sources found for analysis.")

        # Build compact context
        source_context = build_source_context(sources)
        source_references = build_source_references(sources)

        topic = research_run.topic
        context: dict[str, Any] = {
            "topic": topic,
            "source_context": source_context,
            "source_references": source_references,
        }

        agent_runs: list[AgentRun] = []
        completed_agents: list[str] = []
        pipeline_failed = False

        # --- Stage 1: Market Analyst ---
        logger.info("Stage 1: MarketAnalyst | research_run_id=%d", research_run.id)
        market_result, market_run = await self._market_analyst.execute(
            research_run_id=research_run.id, db=db, **context,
        )
        agent_runs.append(market_run)
        if market_result is None:
            pipeline_failed = True
            logger.error("Pipeline stopped: MarketAnalyst failed")
        else:
            completed_agents.append("MarketAnalyst")
            context["market_analysis"] = market_result.model_dump_json(indent=2)

        # --- Stage 2: Competitor Analyst ---
        if not pipeline_failed:
            logger.info("Stage 2: CompetitorAnalyst | research_run_id=%d", research_run.id)
            comp_result, comp_run = await self._competitor_analyst.execute(
                research_run_id=research_run.id, db=db, **context,
            )
            agent_runs.append(comp_run)
            if comp_result is None:
                pipeline_failed = True
                logger.error("Pipeline stopped: CompetitorAnalyst failed")
            else:
                completed_agents.append("CompetitorAnalyst")
                context["competitor_analysis"] = comp_result.model_dump_json(indent=2)

        # --- Stage 3: Idea Generator ---
        if not pipeline_failed:
            logger.info("Stage 3: IdeaGenerator | research_run_id=%d", research_run.id)
            idea_result, idea_run = await self._idea_generator.execute(
                research_run_id=research_run.id, db=db,
                num_ideas=num_ideas, **context,
            )
            agent_runs.append(idea_run)
            if idea_result is None:
                pipeline_failed = True
                logger.error("Pipeline stopped: IdeaGenerator failed")
            else:
                completed_agents.append("IdeaGenerator")
                # Format ideas for downstream agents
                ideas_text = "\n\n".join(
                    json.dumps(idea.model_dump(), indent=2)
                    for idea in idea_result.ideas
                )
                context["ideas_text"] = ideas_text
                context["idea_result"] = idea_result

        # --- Stage 4: Technical Analyst ---
        if not pipeline_failed:
            logger.info("Stage 4: TechnicalAnalyst | research_run_id=%d", research_run.id)
            tech_result, tech_run = await self._technical_analyst.execute(
                research_run_id=research_run.id, db=db, **context,
            )
            agent_runs.append(tech_run)
            if tech_result is None:
                pipeline_failed = True
                logger.error("Pipeline stopped: TechnicalAnalyst failed")
            else:
                completed_agents.append("TechnicalAnalyst")
                context["technical_analysis"] = tech_result.model_dump_json(indent=2)

        # --- Stage 5: Validation Planner ---
        if not pipeline_failed:
            logger.info("Stage 5: ValidationPlanner | research_run_id=%d", research_run.id)
            val_result, val_run = await self._validation_planner.execute(
                research_run_id=research_run.id, db=db, **context,
            )
            agent_runs.append(val_run)
            if val_result is None:
                pipeline_failed = True
                logger.error("Pipeline stopped: ValidationPlanner failed")
            else:
                completed_agents.append("ValidationPlanner")

        # --- Save Ideas to Database ---
        ideas_generated = 0
        if not pipeline_failed and "idea_result" in context:
            idea_result = context["idea_result"]
            validation_result = context.get("validation_analysis")
            tech_result = context.get("technical_analysis")

            for idx, idea in enumerate(idea_result.ideas):
                # Find matching validation plan
                validation_plan_text = ""
                if val_result:
                    for vp in val_result.validation_plans:
                        if vp.idea_title.lower() == idea.title.lower():
                            validation_plan_text = json.dumps(vp.model_dump(), indent=2)
                            break

                # Find matching technical analysis
                tech_analysis_text = ""
                if tech_result:
                    for ta in tech_result.idea_analyses:
                        if ta.idea_title.lower() == idea.title.lower():
                            tech_analysis_text = json.dumps(ta.model_dump(), indent=2)
                            break

                # Build full analysis JSON for the idea
                full_analysis = {
                    "idea": idea.model_dump(),
                    "technical_analysis": json.loads(tech_analysis_text) if tech_analysis_text else None,
                    "validation_plan": json.loads(validation_plan_text) if validation_plan_text else None,
                    "market_analysis_summary": context.get("market_analysis", "")[:2000],
                    "competitor_analysis_summary": context.get("competitor_analysis", "")[:2000],
                }

                db_idea = IdeaModel(
                    research_run_id=research_run.id,
                    title=idea.title,
                    problem=idea.problem,
                    solution=idea.solution,
                    target_users=idea.target_users,
                    mvp=idea.mvp,
                    monetization=idea.monetization,
                    differentiation=idea.differentiation,
                    technical_complexity=tech_analysis_text[:2000] if tech_analysis_text else None,
                    risks="\n".join(idea.risks) if idea.risks else None,
                    validation_plan=validation_plan_text if validation_plan_text else None,
                    status=IdeaStatus.NEW,
                )
                db.add(db_idea)
                ideas_generated += 1

            logger.info("Saved %d ideas to database", ideas_generated)

        # --- Finalize ---
        elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()

        if pipeline_failed:
            research_run.status = ResearchStatus.FAILED
            research_run.completed_at = datetime.now(timezone.utc)
        else:
            research_run.status = ResearchStatus.COMPLETED
            research_run.completed_at = datetime.now(timezone.utc)

        db.flush()
        db.commit()

        logger.info(
            "Pipeline completed | research_run_id=%d | status=%s | "
            "completed_agents=%d | ideas=%d | duration=%.1fs",
            research_run.id,
            "completed" if not pipeline_failed else "failed",
            len(completed_agents),
            ideas_generated,
            elapsed,
        )

        return {
            "research_id": research_run.id,
            "status": "completed" if not pipeline_failed else "failed",
            "ideas_generated": ideas_generated,
            "completed_agents": completed_agents,
            "duration_seconds": elapsed,
        }


async def run_analysis_pipeline(
    research_id: int,
    db: Session,
    num_ideas: int = 4,
) -> dict[str, Any]:
    """Convenience function to run the analysis pipeline.

    Args:
        research_id: ID of the ResearchRun to analyze.
        db: Database session.
        num_ideas: Number of ideas to generate.

    Returns:
        Pipeline result dict.
    """
    research_run = db.query(ResearchRun).filter(ResearchRun.id == research_id).first()
    if not research_run:
        raise ValueError(f"ResearchRun {research_id} not found")

    orchestrator = AgentOrchestrator()
    return await orchestrator.run(research_run, db, num_ideas=num_ideas)
