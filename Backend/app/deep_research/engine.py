"""Deep Research Engine — iterative 12-hour research loop.

Breaks a user topic into sub-queries, runs agents, searches for more info,
and iterates until convergence or 12-hour time limit.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.ai.provider import OpenRouterProvider
from app.agents.market import MarketAnalyst
from app.agents.competitor import CompetitorAnalyst
from app.agents.idea import IdeaGenerator
from app.agents.technical import TechnicalAnalyst
from app.agents.validation import ValidationPlanner
from app.agents.context_utils import build_source_context, build_source_references
from app.research.service import ResearchService
from app.database.models.research import ResearchRun, ResearchStatus
from app.database.models.source import ResearchSource

logger = logging.getLogger(__name__)

MAX_DURATION_HOURS = 12
MAX_ITERATIONS = 20
CONVERGENCE_THRESHOLD = 3  # iterations with no new info → stop


class DeepResearchJob:
    """Tracks a single deep research job."""

    def __init__(self, job_id: str, topic: str):
        self.job_id = job_id
        self.topic = topic
        self.status = "pending"  # pending | running | completed | failed | stopped
        self.current_iteration = 0
        self.max_iterations = MAX_ITERATIONS
        self.started_at: datetime | None = None
        self.completed_at: datetime | None = None
        self.sub_queries: list[str] = []
        self.iteration_log: list[dict[str, Any]] = []
        self.final_answer: str | None = None
        self.error: str | None = None
        self.sources_collected = 0
        self.agents_run = 0
        self.progress_pct = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "topic": self.topic,
            "status": self.status,
            "current_iteration": self.current_iteration,
            "max_iterations": self.max_iterations,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "elapsed_hours": round(
                ((self.completed_at or datetime.now(timezone.utc)) -
                 (self.started_at or datetime.now(timezone.utc))).total_seconds() / 3600, 2
            ) if self.started_at else 0,
            "sub_queries": self.sub_queries,
            "iteration_log": self.iteration_log[-10:],  # last 10 only
            "final_answer": self.final_answer,
            "error": self.error,
            "sources_collected": self.sources_collected,
            "agents_run": self.agents_run,
            "progress_pct": self.progress_pct,
        }


# In-memory job store (for free-tier Render — no Redis needed)
_jobs: dict[str, DeepResearchJob] = {}


def get_job(job_id: str) -> DeepResearchJob | None:
    return _jobs.get(job_id)


def list_jobs() -> list[dict[str, Any]]:
    return [j.to_dict() for j in sorted(_jobs.values(), key=lambda x: x.started_at or datetime.min.replace(tzinfo=timezone.utc), reverse=True)]


async def start_deep_research(topic: str, db: Session) -> DeepResearchJob:
    """Create and start a deep research job in the background."""
    import uuid
    job_id = f"dr_{uuid.uuid4().hex[:12]}"
    job = DeepResearchJob(job_id, topic)
    _jobs[job_id] = job

    # Launch background task
    asyncio.create_task(_run_deep_research(job, db))

    return job


async def stop_deep_research(job_id: str) -> bool:
    job = _jobs.get(job_id)
    if job and job.status == "running":
        job.status = "stopped"
        return True
    return False


async def _run_deep_research(job: DeepResearchJob, db: Session):
    """Main research loop — runs in background."""
    job.status = "running"
    job.started_at = datetime.now(timezone.utc)
    deadline = job.started_at + timedelta(hours=MAX_DURATION_HOURS)

    provider = OpenRouterProvider()
    market = MarketAnalyst(provider=provider)
    competitor = CompetitorAnalyst(provider=provider)
    idea_gen = IdeaGenerator(provider=provider)
    tech = TechnicalAnalyst(provider=provider)
    validation = ValidationPlanner(provider=provider)
    research_svc = ResearchService()

    all_findings: list[str] = []
    all_sources: list[dict] = []
    no_new_info_count = 0

    try:
        # Step 1: Break topic into sub-queries
        job.sub_queries = await _generate_sub_queries(topic, provider)
        job.progress_pct = 5.0

        for iteration in range(1, MAX_ITERATIONS + 1):
            if job.status == "stopped":
                break
            if datetime.now(timezone.utc) > deadline:
                logger.info("Deep research %s hit 12-hour deadline", job.job_id)
                break

            job.current_iteration = iteration
            iter_start = datetime.now(timezone.utc)
            iter_log: dict[str, Any] = {
                "iteration": iteration,
                "queries_used": [],
                "new_sources": 0,
                "agents_completed": [],
                "findings_count": 0,
            }

            # Pick sub-query for this iteration (round-robin)
            query = job.sub_queries[(iteration - 1) % len(job.sub_queries)]
            iter_log["queries_used"].append(query)

            # Search
            try:
                search_results = await research_svc.search(query, num_results=5)
                new_sources = len(search_results) if search_results else 0
                iter_log["new_sources"] = new_sources
                job.sources_collected += new_sources

                if search_results:
                    all_sources.extend([{
                        "title": s.get("title", ""),
                        "url": s.get("link", ""),
                        "snippet": s.get("snippet", ""),
                        "iteration": iteration,
                    } for s in search_results])
            except Exception as e:
                logger.warning("Search failed iteration %d: %s", iteration, str(e))

            # Run mini-agent pipeline on gathered data
            context = {
                "topic": topic,
                "source_context": _build_mini_context(all_sources[-10:]),
                "source_references": [s["url"] for s in all_sources[-10:] if s.get("url")],
                "current_findings": "\n".join(all_findings[-5:]),
                "iteration": str(iteration),
            }

            # Market analyst (quick pass)
            try:
                market_result, _ = await market.execute(
                    research_run_id=0, db=db, **context
                )
                if market_result:
                    iter_log["agents_completed"].append("MarketAnalyst")
                    job.agents_run += 1
                    finding = f"[Iter {iteration}] Market: {str(market_result)[:500]}"
                    all_findings.append(finding)
                    iter_log["findings_count"] += 1
            except Exception as e:
                logger.warning("Market analyst failed iter %d: %s", iteration, str(e))

            # Competitor analyst (quick pass)
            try:
                comp_result, _ = await competitor.execute(
                    research_run_id=0, db=db, **context
                )
                if comp_result:
                    iter_log["agents_completed"].append("CompetitorAnalyst")
                    job.agents_run += 1
                    finding = f"[Iter {iteration}] Competitor: {str(comp_result)[:500]}"
                    all_findings.append(finding)
                    iter_log["findings_count"] += 1
            except Exception as e:
                logger.warning("Competitor analyst failed iter %d: %s", iteration, str(e))

            # Idea generator (every 3rd iteration)
            if iteration % 3 == 0:
                try:
                    idea_result, _ = await idea_gen.execute(
                        research_run_id=0, db=db, num_ideas=2, **context
                    )
                    if idea_result:
                        iter_log["agents_completed"].append("IdeaGenerator")
                        job.agents_run += 1
                        finding = f"[Iter {iteration}] Ideas: {str(idea_result)[:500]}"
                        all_findings.append(finding)
                        iter_log["findings_count"] += 1
                except Exception as e:
                    logger.warning("Idea generator failed iter %d: %s", iteration, str(e))

            # Check convergence
            if iter_log["new_sources"] == 0 and iter_log["findings_count"] == 0:
                no_new_info_count += 1
            else:
                no_new_info_count = 0

            elapsed_pct = min(90, 5 + (iteration / MAX_ITERATIONS) * 85)
            job.progress_pct = round(elapsed_pct, 1)
            job.iteration_log.append(iter_log)

            # Regenerate sub-queries every 5 iterations based on findings
            if iteration % 5 == 0 and all_findings:
                try:
                    new_queries = await _refine_sub_queries(topic, all_findings[-5:], provider)
                    if new_queries:
                        job.sub_queries = new_queries
                        no_new_info_count = 0  # Reset on new direction
                except Exception:
                    pass

            if no_new_info_count >= CONVERGENCE_THRESHOLD:
                logger.info("Deep research %s converged at iteration %d", job.job_id, iteration)
                break

            # Brief pause between iterations
            await asyncio.sleep(2)

        # Step 3: Synthesize final answer
        job.progress_pct = 95.0
        job.final_answer = await _synthesize_answer(topic, all_findings, all_sources, provider)

        if job.status != "stopped":
            job.status = "completed"
        job.completed_at = datetime.now(timezone.utc)
        job.progress_pct = 100.0

        logger.info(
            "Deep research %s completed | iterations=%d | sources=%d | findings=%d",
            job.job_id, job.current_iteration, job.sources_collected, len(all_findings),
        )

    except Exception as e:
        job.status = "failed"
        job.error = str(e)
        job.completed_at = datetime.now(timezone.utc)
        logger.exception("Deep research %s failed", job.job_id)


async def _generate_sub_queries(topic: str, provider: OpenRouterProvider) -> list[str]:
    """Use LLM to break topic into 5-8 sub-queries."""
    from app.ai.client import OpenRouterClient
    client = OpenRouterClient(provider=provider)

    prompt = f"""Break this research topic into 5-8 specific sub-queries for web search.
Return ONLY a JSON array of strings. No explanation.

Topic: {topic}

Example format: ["query 1", "query 2", "query 3"]"""

    try:
        response = await client.chat(prompt, model=None, max_tokens=500)
        # Parse JSON array from response
        text = response.strip()
        # Find JSON array in response
        start = text.find("[")
        end = text.rfind("]") + 1
        if start >= 0 and end > start:
            queries = json.loads(text[start:end])
            if isinstance(queries, list) and len(queries) >= 3:
                return queries[:8]
    except Exception as e:
        logger.warning("Failed to generate sub-queries: %s", str(e))

    # Fallback: generate basic sub-queries
    return [
        f"{topic} market analysis 2026",
        f"{topic} competitors landscape",
        f"{topic} technology trends",
        f"{topic} user problems pain points",
        f"{topic} revenue models pricing",
        f"{topic} startup opportunities",
        f"{topic} technical feasibility",
        f"{topic} market size growth rate",
    ]


async def _refine_sub_queries(topic: str, recent_findings: list[str], provider: OpenRouterProvider) -> list[str]:
    """Refine sub-queries based on recent findings."""
    from app.ai.client import OpenRouterClient
    client = OpenRouterClient(provider=provider)

    findings_text = "\n".join(recent_findings[:3])
    prompt = f"""Based on these recent research findings about "{topic}", generate 5-8 refined sub-queries
to explore gaps and new angles. Return ONLY a JSON array of strings.

Recent findings:
{findings_text}

Format: ["query 1", "query 2"]"""

    try:
        response = await client.chat(prompt, model=None, max_tokens=500)
        text = response.strip()
        start = text.find("[")
        end = text.rfind("]") + 1
        if start >= 0 and end > start:
            queries = json.loads(text[start:end])
            if isinstance(queries, list) and len(queries) >= 3:
                return queries[:8]
    except Exception:
        pass

    return []


async def _synthesize_answer(
    topic: str,
    findings: list[str],
    sources: list[dict],
    provider: OpenRouterProvider,
) -> str:
    """Use LLM to synthesize all findings into a comprehensive answer."""
    from app.ai.client import OpenRouterClient
    client = OpenRouterClient(provider=provider)

    findings_text = "\n\n".join(findings[-20:])  # Last 20 findings
    source_list = "\n".join([f"- {s['title']}: {s['url']}" for s in sources[:20] if s.get("url")])

    prompt = f"""You are an expert research analyst. Synthesize ALL of the following research findings
into a comprehensive, well-structured analysis report for the topic: "{topic}"

RESEARCH FINDINGS:
{findings_text}

SOURCES USED:
{source_list}

Provide a thorough analysis covering:
1. Executive Summary
2. Market Overview & Trends
3. Competitive Landscape
4. Key Problems & Opportunities
5. Technical Feasibility
6. Revenue & Business Models
7. Risk Assessment
8. Recommendations & Next Steps

Be specific, cite sources where possible, and provide actionable insights."""

    try:
        answer = await client.chat(prompt, model=None, max_tokens=4000)
        return answer
    except Exception as e:
        # Return what we have
        return f"Research completed with {len(findings)} findings from {len(sources)} sources.\n\nRaw findings:\n{findings_text[:2000]}"


def _build_mini_context(sources: list[dict]) -> str:
    """Build a compact context string from sources."""
    parts = []
    for s in sources:
        title = s.get("title", "Untitled")
        snippet = s.get("snippet", "")
        parts.append(f"**{title}**\n{snippet}")
    return "\n\n".join(parts)
