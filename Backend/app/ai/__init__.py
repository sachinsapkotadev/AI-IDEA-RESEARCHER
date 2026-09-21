"""AI engine — provider abstraction, client, key pool, and model registry."""

from app.ai.errors import (
    AIAllKeysExhausted,
    AIConfigurationError,
    AIProviderError,
    AIResponseParsingError,
    AIResponseValidationError,
    AIRateLimitError,
    AITimeoutError,
)
from app.ai.key_pool import OpenRouterKeyPool
from app.ai.model_registry import ModelRegistry
from app.ai.provider import AIProvider, OpenRouterProvider
from app.ai.research_agent import ResearchAgent

__all__ = [
    "AIProvider",
    "OpenRouterProvider",
    "OpenRouterKeyPool",
    "ModelRegistry",
    "ResearchAgent",
    "AIAllKeysExhausted",
    "AIConfigurationError",
    "AIProviderError",
    "AIResponseParsingError",
    "AIResponseValidationError",
    "AIRateLimitError",
    "AITimeoutError",
]
