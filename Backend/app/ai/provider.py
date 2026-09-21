"""Abstract AI provider and OpenRouter implementation."""

import json
import logging
import re
from abc import ABC, abstractmethod

from app.ai.client import OpenRouterClient
from app.ai.errors import AIResponseParsingError, AIResponseValidationError
from app.ai.schemas import AIResponse, AIUsage

logger = logging.getLogger(__name__)


class AIProvider(ABC):
    """Abstract interface for AI providers."""

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AIResponse:
        """Generate a response from the AI provider.

        Args:
            prompt: The user prompt.
            system_prompt: Optional system prompt.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens.

        Returns:
            AIResponse with content and usage info.
        """


def _extract_json_from_response(content: str) -> dict:
    """Extract JSON from AI response content.

    Handles:
    - Raw JSON
    - JSON wrapped in markdown code fences
    - Leading/trailing whitespace

    Raises:
        AIResponseParsingError: If JSON cannot be extracted or parsed.
    """
    stripped = content.strip()

    # Try direct parse first
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass

    # Try extracting from markdown code fences
    fence_pattern = r"```(?:json)?\s*\n?(.*?)\n?\s*```"
    match = re.search(fence_pattern, stripped, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Try finding first { ... } block
    brace_start = stripped.find("{")
    brace_end = stripped.rfind("}")
    if brace_start != -1 and brace_end > brace_start:
        try:
            return json.loads(stripped[brace_start : brace_end + 1])
        except json.JSONDecodeError:
            pass

    raise AIResponseParsingError(
        "Could not extract valid JSON from AI response."
    )


class OpenRouterProvider(AIProvider):
    """OpenRouter AI provider implementation."""

    def __init__(self) -> None:
        self._client = OpenRouterClient()

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AIResponse:
        """Generate a response via OpenRouter.

        Args:
            prompt: User prompt.
            system_prompt: Optional system prompt.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens.

        Returns:
            AIResponse with parsed content and usage.
        """
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        raw = await self._client.chat_completion(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        # Extract content
        try:
            content = raw["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise AIResponseParsingError(
                "Unexpected response structure from OpenRouter."
            ) from exc

        # Extract usage
        usage_data = raw.get("usage", {})
        usage = AIUsage(
            input_tokens=usage_data.get("prompt_tokens"),
            output_tokens=usage_data.get("completion_tokens"),
        )

        return AIResponse(
            content=content,
            model=raw.get("model"),
            usage=usage,
        )

    @property
    def model(self) -> str:
        """Return the configured model ID."""
        return self._client.model
