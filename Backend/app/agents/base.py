"""Base agent class for the multi-agent pipeline."""

import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.ai.errors import AIError
from app.ai.provider import OpenRouterProvider, _extract_json_from_response
from app.database.models.agent_run import AgentRun, AgentRunStatus

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """Base class for all analysis agents.

    Responsibilities:
    - Manage AgentRun lifecycle (create, update status, record metrics)
    - Call AI provider with system + user prompts
    - Parse and validate AI JSON output into Pydantic models
    - Handle errors consistently

    Subclasses must provide:
    - AGENT_NAME: unique identifier
    - SYSTEM_PROMPT: instructions for the AI
    - OUTPUT_MODEL: Pydantic model for validated output
    - build_prompt(): method to construct the user prompt
    """

    AGENT_NAME: str = ""
    SYSTEM_PROMPT: str = ""
    OUTPUT_MODEL: type[BaseModel] | None = None

    def __init__(self, provider: OpenRouterProvider | None = None) -> None:
        self._provider = provider or OpenRouterProvider()

    async def execute(
        self,
        research_run_id: int,
        db: Session,
        **kwargs: Any,
    ) -> tuple[BaseModel | None, AgentRun]:
        """Execute the agent with full lifecycle management.

        Args:
            research_run_id: ID of the parent research run.
            db: Database session.
            **kwargs: Agent-specific input data.

        Returns:
            Tuple of (validated output or None if failed, agent_run record).
        """
        resolved_model = self._provider._resolve_model(None, self.AGENT_NAME)

        logger.info(
            "%s started | research_run_id=%d | model=%s",
            self.AGENT_NAME, research_run_id, resolved_model,
        )

        agent_run = AgentRun(
            research_run_id=research_run_id,
            agent_name=self.AGENT_NAME,
            model=resolved_model,
            status=AgentRunStatus.RUNNING,
            started_at=datetime.now(timezone.utc),
        )
        db.add(agent_run)
        db.flush()

        try:
            prompt = self.build_prompt(**kwargs)
            response = await self._provider.generate(
                prompt=prompt,
                system_prompt=self.SYSTEM_PROMPT,
                agent_name=self.AGENT_NAME,
            )

            raw_json = _extract_json_from_response(response.content)
            result = self.OUTPUT_MODEL.model_validate(raw_json)

            agent_run.status = AgentRunStatus.COMPLETED
            agent_run.completed_at = datetime.now(timezone.utc)
            agent_run.input_tokens = response.usage.input_tokens
            agent_run.output_tokens = response.usage.output_tokens
            agent_run.provider_key_slot = response.key_slot

            duration = (agent_run.completed_at - agent_run.started_at).total_seconds()
            logger.info(
                "%s completed | research_run_id=%d | model=%s | key_slot=%s | "
                "duration=%.1fs | input_tokens=%s | output_tokens=%s",
                self.AGENT_NAME, research_run_id, resolved_model,
                response.key_slot, duration,
                response.usage.input_tokens, response.usage.output_tokens,
            )

            return result, agent_run

        except AIError as exc:
            agent_run.status = AgentRunStatus.FAILED
            agent_run.completed_at = datetime.now(timezone.utc)
            agent_run.error_message = f"AI error: {type(exc).__name__}: {exc}"
            logger.exception(
                "%s AI error | research_run_id=%d",
                self.AGENT_NAME, research_run_id,
            )
            return None, agent_run

        except Exception as exc:
            agent_run.status = AgentRunStatus.FAILED
            agent_run.completed_at = datetime.now(timezone.utc)
            agent_run.error_message = f"Unexpected error: {type(exc).__name__}: {exc}"
            logger.exception(
                "%s unexpected error | research_run_id=%d",
                self.AGENT_NAME, research_run_id,
            )
            return None, agent_run

    @abstractmethod
    def build_prompt(self, **kwargs: Any) -> str:
        """Build the user prompt from input data.

        Must be implemented by each agent subclass.
        """
