"""Model registry — maps agent names to model configurations."""

import logging
from dataclasses import dataclass

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# Agent name → env var mapping (matches .env MODEL_* vars)
_AGENT_MODEL_VARS: dict[str, str] = {
    "MarketAnalyst": "MODEL_MARKET_ANALYST",
    "CompetitorAnalyst": "MODEL_COMPETITOR_ANALYST",
    "IdeaGenerator": "MODEL_IDEA_GENERATOR",
    "TechnicalAnalyst": "MODEL_TECHNICAL_ANALYST",
    "ValidationPlanner": "MODEL_VALIDATION_PLANNER",
}

# All 20 free models available
ALL_FREE_MODELS = [
    "inclusionai/ling-3.0-flash-vl:free",
    "nex-agi/nex-n2.5-mini:free",
    "nex-agi/nex-n2.5-pro:free",
    "inclusionai/ling-3.0-flash-sante:free",
    "inclusionai/ling-3.0-flash-fin:free",
    "qwen/qwen3.8-27b:free",
    "deepgram/flux-tts:free",
    "nvidia/nemotron-3.5-lightning:free",
    "thinkingmachines/inkling-small:free",
    "fish-audio/s2.1-pro-free:free",
    "nvidia/nemotron-3-embed-1b:free",
    "thinkingmachines/inkling:free",
    "poolside/laguna-s-2.1:free",
    "poolside/laguna-xs-2.1:free",
    "cohere/north-mini-code:free",
    "z-ai/glm-5.2:free",
    "nvidia/llama-nemotron-rerank-vl-1b-v2:free",
    "nvidia/nemotron-3-ultra-550b-a55b:free",
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
    "nvidia/llama-nemotron-embed-vl-1b-v2:free",
]


@dataclass
class ModelConfig:
    """Configuration for a specific model usage."""

    model_id: str
    agent_name: str
    temperature: float = 0.7
    max_tokens: int = 4096


class ModelRegistry:
    """Maps agent names to their configured models.

    Falls back to OPENROUTER_MODEL if no agent-specific model is set.
    """

    def __init__(self) -> None:
        self._settings = get_settings()
        self._default_model = self._settings.OPENROUTER_MODEL

    def get_model(self, agent_name: str) -> str:
        """Get the model ID for a given agent.

        Args:
            agent_name: Name of the agent (e.g., 'MarketAnalyst').

        Returns:
            Model ID string.

        Raises:
            ValueError: If no model is configured at all.
        """
        env_var = _AGENT_MODEL_VARS.get(agent_name)
        if env_var:
            agent_model = getattr(self._settings, env_var, "")
            if agent_model and agent_model.strip():
                return agent_model.strip()

        if self._default_model and self._default_model.strip():
            return self._default_model.strip()

        raise ValueError(
            f"No model configured for agent '{agent_name}'. "
            f"Set {env_var or 'OPENROUTER_MODEL'} in your environment."
        )

    def get_model_config(self, agent_name: str) -> ModelConfig:
        """Get full model configuration for an agent."""
        return ModelConfig(
            model_id=self.get_model(agent_name),
            agent_name=agent_name,
        )

    def is_configured(self) -> bool:
        """Check if any model is configured."""
        return bool(self._default_model and self._default_model.strip())

    def get_all_configured_models(self) -> dict[str, str]:
        """Return mapping of agent names to their configured models."""
        result: dict[str, str] = {}
        for agent_name in _AGENT_MODEL_VARS:
            try:
                result[agent_name] = self.get_model(agent_name)
            except ValueError:
                result[agent_name] = "(not configured)"
        return result
