"""Research Agent — reuses existing research pipeline analysis."""

from typing import Any

from app.agents.base import BaseAgent
from app.agents.schemas import MarketAnalysis
from app.database.models.research import ResearchRun


class ResearchAgent(BaseAgent):
    """Analyzes collected research sources into structured findings.

    This is the existing research agent from Phase 3/4, adapted to the
    new agent architecture for pipeline integration.
    """

    AGENT_NAME = "ResearchAgent"

    def build_prompt(self, **kwargs: Any) -> str:
        """Build research analysis prompt."""
        topic = kwargs.get("topic", "")
        source_context = kwargs.get("source_context", "")
        source_references = kwargs.get("source_references", "")

        return f"""Analyze the following research topic using the provided source material.

Topic: {topic}

Source Material:
{source_context}

Source References:
{source_references}

Instructions:
1. Analyze the source material above carefully.
2. Identify key findings, problems, and opportunities.
3. Cite sources using [S1], [S2], etc. when referencing specific information.
4. Clearly separate facts backed by sources from your own analysis.
5. Identify areas of uncertainty or conflicting information.

Return a JSON object with exactly these fields:
- "topic": the topic string
- "summary": a concise summary of your analysis (2-4 paragraphs)
- "findings": array of key findings as strings (cite sources where relevant)
- "problems": array of concrete problems identified
- "opportunities": array of potential software/business opportunities
- "source_references": array of source IDs (like "S1", "S2") you used
- "uncertainties": array of things you are uncertain about

Rules:
- Only reference sources actually provided above
- Mark assumptions clearly with [HYPOTHESIS]
- Do not invent statistics or data
- Return ONLY the JSON object, no other text"""
