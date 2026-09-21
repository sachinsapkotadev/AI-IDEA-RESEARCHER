"""Report generator — renders structured research data into Markdown."""

import json
import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.database.models.agent_run import AgentRun
from app.database.models.idea import Idea
from app.database.models.research import ResearchRun
from app.database.models.source import ResearchSource
from app.reports.schemas import ReportContent, ReportMetadata

logger = logging.getLogger(__name__)


class ReportGenerator:
    """Generates Markdown research reports from database records.

    Only uses data actually stored in the database.
    Never fabricates sources, statistics, or claims.
    """

    def generate(
        self,
        research_run: ResearchRun,
        db: Session,
    ) -> ReportContent:
        """Generate report content from a completed ResearchRun.

        Args:
            research_run: The completed ResearchRun.
            db: Database session.

        Returns:
            ReportContent with all sections populated.
        """
        # Gather data
        sources = (
            db.query(ResearchSource)
            .filter(ResearchSource.research_run_id == research_run.id)
            .order_by(ResearchSource.rank)
            .all()
        )
        ideas = (
            db.query(Idea)
            .filter(Idea.research_run_id == research_run.id)
            .order_by(Idea.created_at)
            .all()
        )
        agent_runs = (
            db.query(AgentRun)
            .filter(AgentRun.research_run_id == research_run.id)
            .order_by(AgentRun.id)
            .all()
        )

        # Build metadata
        models_used = list({ar.model for ar in agent_runs if ar.model})
        agent_summary = []
        for ar in agent_runs:
            entry = {
                "agent": ar.agent_name,
                "model": ar.model or "unknown",
                "key_slot": ar.provider_key_slot or "N/A",
                "status": ar.status.value,
            }
            if ar.input_tokens is not None:
                entry["input_tokens"] = ar.input_tokens
            if ar.output_tokens is not None:
                entry["output_tokens"] = ar.output_tokens
            if ar.started_at and ar.completed_at:
                entry["duration_seconds"] = (
                    ar.completed_at - ar.started_at
                ).total_seconds()
            agent_summary.append(entry)

        now = datetime.now(timezone.utc)
        metadata = ReportMetadata(
            research_id=research_run.id,
            topic=research_run.topic,
            date=now.strftime("%Y-%m-%d"),
            status=research_run.status.value,
            models_used=models_used,
            agent_summary=agent_summary,
        )

        # Build sections
        executive_summary = self._build_executive_summary(research_run)
        sources_section = self._build_sources_section(sources)
        market_analysis = self._build_market_analysis(research_run, agent_runs)
        competitor_analysis = self._build_competitor_analysis(research_run, agent_runs)
        ideas_section = self._build_ideas_section(ideas)
        technical_analysis = self._build_technical_section(ideas)
        validation_plan = self._build_validation_section(ideas)
        agent_summary_section = self._build_agent_summary(agent_runs)
        uncertainties_section = self._build_uncertainties(research_run)

        return ReportContent(
            metadata=metadata,
            executive_summary=executive_summary,
            sources_section=sources_section,
            market_analysis=market_analysis,
            competitor_analysis=competitor_analysis,
            ideas_section=ideas_section,
            technical_analysis=technical_analysis,
            validation_plan=validation_plan,
            agent_summary_section=agent_summary_section,
            uncertainties_section=uncertainties_section,
        )

    def render_markdown(self, content: ReportContent) -> str:
        """Render ReportContent into a Markdown string.

        Args:
            content: The structured report content.

        Returns:
            Complete Markdown string.
        """
        m = content.metadata
        lines: list[str] = []

        lines.append("# AI IDEA RESEARCHER REPORT\n")
        lines.append(f"- **Research ID:** {m.research_id}")
        lines.append(f"- **Topic:** {m.topic}")
        lines.append(f"- **Date:** {m.date}")
        lines.append(f"- **Status:** {m.status}")
        if m.models_used:
            lines.append(f"- **Models Used:** {', '.join(m.models_used)}")
        lines.append("")

        lines.append("## Agent Execution Summary\n")
        lines.append("| Agent | Model | Key Slot | Status | Tokens (In/Out) | Duration |")
        lines.append("|-------|-------|----------|--------|-----------------|----------|")
        for entry in m.agent_summary:
            tokens = ""
            if "input_tokens" in entry and "output_tokens" in entry:
                tokens = f"{entry['input_tokens']}/{entry['output_tokens']}"
            duration = f"{entry.get('duration_seconds', 0):.1f}s" if "duration_seconds" in entry else "N/A"
            lines.append(
                f"| {entry['agent']} | {entry['model']} | {entry['key_slot']} | "
                f"{entry['status']} | {tokens} | {duration} |"
            )
        lines.append("")

        if content.executive_summary:
            lines.append("## Executive Summary\n")
            lines.append(content.executive_summary)
            lines.append("")

        if content.sources_section:
            lines.append("## Research Sources\n")
            lines.append(content.sources_section)
            lines.append("")

        if content.market_analysis:
            lines.append("## Market Analysis\n")
            lines.append(content.market_analysis)
            lines.append("")

        if content.competitor_analysis:
            lines.append("## Competitor Analysis\n")
            lines.append(content.competitor_analysis)
            lines.append("")

        if content.ideas_section:
            lines.append("## Opportunity Ideas\n")
            lines.append(content.ideas_section)
            lines.append("")

        if content.technical_analysis:
            lines.append("## Technical Analysis\n")
            lines.append(content.technical_analysis)
            lines.append("")

        if content.validation_plan:
            lines.append("## Validation Plan\n")
            lines.append(content.validation_plan)
            lines.append("")

        if content.uncertainties_section:
            lines.append("## Uncertainties and Limitations\n")
            lines.append(content.uncertainties_section)
            lines.append("")

        lines.append("---\n")
        lines.append("*This report was generated by AI Idea Researcher. "
                     "All claims are estimates or hypotheses requiring validation. "
                     "Do not treat this as guaranteed business advice.*\n")

        return "\n".join(lines)

    def _build_executive_summary(self, run: ResearchRun) -> str:
        """Build executive summary from the research result stored in report_path."""
        if not run.report_path:
            return "*No research result available.*\n"
        try:
            data = json.loads(run.report_path)
            summary = data.get("summary", "")
            if summary:
                return summary + "\n"
        except (json.JSONDecodeError, AttributeError):
            pass
        return "*Executive summary not available.*\n"

    def _build_sources_section(self, sources: list[ResearchSource]) -> str:
        """Build sources list section."""
        if not sources:
            return "*No sources collected.*\n"
        lines: list[str] = []
        for idx, src in enumerate(sources):
            source_id = f"S{idx + 1}"
            status_marker = "✓" if src.status.value == "success" else "✗"
            lines.append(f"- [{source_id}] {status_marker} {src.title} — {src.url or 'N/A'} ({src.quality or 'unknown'})")
        lines.append("")
        return "\n".join(lines)

    def _build_market_analysis(self, run: ResearchRun, agent_runs: list[AgentRun]) -> str:
        """Build market analysis section from agent run outputs."""
        market_run = next((ar for ar in agent_runs if ar.agent_name == "MarketAnalyst"), None)
        if not market_run or market_run.status.value != "completed":
            return "*Market analysis not available.*\n"
        return (
            "*Market analysis was completed by the MarketAnalyst agent. "
            "See the ideas section for synthesized findings.*\n"
        )

    def _build_competitor_analysis(self, run: ResearchRun, agent_runs: list[AgentRun]) -> str:
        """Build competitor analysis section."""
        comp_run = next((ar for ar in agent_runs if ar.agent_name == "CompetitorAnalyst"), None)
        if not comp_run or comp_run.status.value != "completed":
            return "*Competitor analysis not available.*\n"
        return (
            "*Competitor analysis was completed by the CompetitorAnalyst agent. "
            "See the ideas section for synthesized findings.*\n"
        )

    def _build_ideas_section(self, ideas: list[Idea]) -> str:
        """Build ideas section with full structured opportunity information."""
        if not ideas:
            return "*No ideas generated.*\n"
        lines: list[str] = []
        for idx, idea in enumerate(ideas, 1):
            lines.append(f"### {idx}. {idea.title}\n")
            if idea.problem:
                lines.append(f"**Problem:** {idea.problem}\n")
            if idea.solution:
                lines.append(f"**Solution:** {idea.solution}\n")
            if idea.target_users:
                lines.append(f"**Target Users:** {idea.target_users}\n")
            if idea.mvp:
                lines.append(f"**MVP:** {idea.mvp}\n")
            if idea.differentiation:
                lines.append(f"**Differentiation:** {idea.differentiation}\n")
            if idea.monetization:
                lines.append(f"**Monetization:** {idea.monetization}\n")
            if idea.technical_complexity:
                lines.append(f"**Technical Complexity:** {idea.technical_complexity}\n")
            if idea.risks:
                lines.append(f"**Risks:** {idea.risks}\n")
            if idea.validation_plan:
                lines.append(f"**Validation Plan:** {idea.validation_plan}\n")
            lines.append("")
        return "\n".join(lines)

    def _build_technical_section(self, ideas: list[Idea]) -> str:
        """Build technical analysis section."""
        tech_ideas = [i for i in ideas if i.technical_complexity]
        if not tech_ideas:
            return "*Technical analysis not available.*\n"
        lines: list[str] = []
        for idea in tech_ideas:
            lines.append(f"### {idea.title}\n")
            lines.append(f"{idea.technical_complexity}\n")
            lines.append("")
        return "\n".join(lines)

    def _build_validation_section(self, ideas: list[Idea]) -> str:
        """Build validation plan section."""
        val_ideas = [i for i in ideas if i.validation_plan]
        if not val_ideas:
            return "*Validation plans not available.*\n"
        lines: list[str] = []
        for idea in val_ideas:
            lines.append(f"### {idea.title}\n")
            lines.append(f"{idea.validation_plan}\n")
            lines.append("")
        return "\n".join(lines)

    def _build_agent_summary(self, agent_runs: list[AgentRun]) -> str:
        """Build agent execution summary section."""
        if not agent_runs:
            return "*No agent runs recorded.*\n"
        lines: list[str] = []
        for ar in agent_runs:
            duration = ""
            if ar.started_at and ar.completed_at:
                duration = f" ({(ar.completed_at - ar.started_at).total_seconds():.1f}s)"
            tokens = ""
            if ar.input_tokens is not None and ar.output_tokens is not None:
                tokens = f" | tokens: {ar.input_tokens}in/{ar.output_tokens}out"
            slot = f" | key_slot: {ar.provider_key_slot}" if ar.provider_key_slot else ""
            lines.append(
                f"- **{ar.agent_name}**: {ar.status.value}{duration}{tokens}{slot}"
            )
            if ar.error_message:
                lines.append(f"  - Error: {ar.error_message}")
        lines.append("")
        return "\n".join(lines)

    def _build_uncertainties(self, run: ResearchRun) -> str:
        """Build uncertainties section from research result."""
        if not run.report_path:
            return "*No research data available.*\n"
        try:
            data = json.loads(run.report_path)
            uncertainties = data.get("uncertainties", [])
            if uncertainties:
                lines = [f"- {u}" for u in uncertainties]
                lines.append("")
                return "\n".join(lines)
        except (json.JSONDecodeError, AttributeError):
            pass
        return "*Uncertainties not documented.*\n"
