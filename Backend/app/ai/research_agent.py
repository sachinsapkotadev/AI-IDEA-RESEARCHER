"""Research Agent — orchestrates AI-powered research on a topic."""

import json
import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.ai.errors import AIError
from app.ai.prompts import RESEARCH_PROMPT_TEMPLATE, SYSTEM_PROMPT
from app.ai.provider import OpenRouterProvider, _extract_json_from_response
from app.ai.schemas import ResearchResult
from app.database.models.agent_run import AgentRun, AgentRunStatus
from app.database.models.research import ResearchRun, ResearchStatus

logger = logging.getLogger(__name__)


class ResearchAgent:
    """Conducts AI-powered research on a given topic.

    Responsibilities:
    - Construct research prompt
    - Call AI provider
    - Parse and validate response
    - Record agent run metrics

    Not responsible for:
    - Database commits (caller handles this)
    - GitHub integration
    - Notifications
    - HTTP routing
    """

    AGENT_NAME = "ResearchAgent"

    def __init__(self, provider: OpenRouterProvider | None = None) -> None:
        self._provider = provider or OpenRouterProvider()

    async def run(
        self,
        research_run: ResearchRun,
        db: Session,
    ) -> ResearchResult:
        """Execute research on the topic of the given ResearchRun.

        Args:
            research_run: The ResearchRun instance (must have a topic).
            db: Database session for recording agent runs.

        Returns:
            Validated ResearchResult.

        Raises:
            AIError: On any AI-related failure.
        """
        topic = research_run.topic
        logger.info(
            "ResearchAgent started | topic=%s | model=%s",
            topic[:80],
            self._provider.model,
        )

        # Create agent run record
        agent_run = AgentRun(
            research_run_id=research_run.id,
            agent_name=self.AGENT_NAME,
            model=self._provider.model,
            status=AgentRunStatus.RUNNING,
            started_at=datetime.now(timezone.utc),
        )
        db.add(agent_run)
        db.flush()

        try:
            # Update research run status
            research_run.status = ResearchStatus.RUNNING
            research_run.started_at = datetime.now(timezone.utc)
            db.flush()

            # Build prompt
            prompt = RESEARCH_PROMPT_TEMPLATE.format(topic=topic)

            # Call AI provider
            response = await self._provider.generate(
                prompt=prompt,
                system_prompt=SYSTEM_PROMPT,
            )

            # Parse JSON from response
            raw_json = _extract_json_from_response(response.content)

            # Validate with Pydantic
            result = ResearchResult.model_validate(raw_json)

            # Update agent run with success
            agent_run.status = AgentRunStatus.COMPLETED
            agent_run.completed_at = datetime.now(timezone.utc)
            agent_run.input_tokens = response.usage.input_tokens
            agent_run.output_tokens = response.usage.output_tokens

            # Update research run
            research_run.status = ResearchStatus.COMPLETED
            research_run.completed_at = datetime.now(timezone.utc)

            logger.info(
                "ResearchAgent completed | topic=%s | duration=%.1fs",
                topic[:80],
                (agent_run.completed_at - agent_run.started_at).total_seconds(),
            )

            return result

        except AIError:
            # Update agent run with failure
            agent_run.status = AgentRunStatus.FAILED
            agent_run.completed_at = datetime.now(timezone.utc)
            agent_run.error_message = "AI provider error"

            # Update research run
            research_run.status = ResearchStatus.FAILED
            research_run.completed_at = datetime.now(timezone.utc)

            logger.exception(
                "ResearchAgent failed | topic=%s",
                topic[:80],
            )
            raise

        except Exception as exc:
            agent_run.status = AgentRunStatus.FAILED
            agent_run.completed_at = datetime.now(timezone.utc)
            agent_run.error_message = f"Unexpected error: {type(exc).__name__}"

            research_run.status = ResearchStatus.FAILED
            research_run.completed_at = datetime.now(timezone.utc)

            logger.exception(
                "ResearchAgent unexpected failure | topic=%s",
                topic[:80],
            )
            raise
