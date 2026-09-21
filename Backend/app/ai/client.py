"""OpenRouter HTTP client using httpx."""

import logging
from typing import Any

import httpx

from app.ai.errors import (
    AIConfigurationError,
    AIProviderError,
    AIRateLimitError,
    AITimeoutError,
)
from app.core.config import get_settings

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 60.0


class OpenRouterClient:
    """Low-level HTTP client for OpenRouter API."""

    def __init__(self) -> None:
        self._settings = get_settings()
        self._validate_config()

    def _validate_config(self) -> None:
        """Ensure required configuration is present."""
        if not self._settings.OPENROUTER_API_KEY:
            raise AIConfigurationError(
                "OPENROUTER_API_KEY is not configured. "
                "Set it in your .env file or environment."
            )
        if not self._settings.OPENROUTER_MODEL:
            raise AIConfigurationError(
                "OPENROUTER_MODEL is not configured. "
                "Set it in your .env file or environment."
            )

    @property
    def model(self) -> str:
        """Return the configured model ID."""
        return self._settings.OPENROUTER_MODEL

    async def chat_completion(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> dict[str, Any]:
        """Send a chat completion request to OpenRouter.

        Args:
            messages: List of message dicts with 'role' and 'content'.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens in response.

        Returns:
            Raw API response dict.

        Raises:
            AIConfigurationError: If config is missing.
            AIProviderError: On HTTP or API errors.
            AIRateLimitError: On rate limiting.
            AITimeoutError: On timeout.
        """
        url = f"{self._settings.OPENROUTER_BASE_URL}/chat/completions"

        headers = {
            "Authorization": f"Bearer {self._settings.OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://ai-idea-researcher.local",
            "X-Title": "AI Idea Researcher",
        }

        payload = {
            "model": self._settings.OPENROUTER_MODEL,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        try:
            async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
                response = await client.post(url, json=payload, headers=headers)

                if response.status_code == 429:
                    raise AIRateLimitError(
                        "Rate limited by OpenRouter. Try again later.",
                        status_code=429,
                    )

                if response.status_code == 401:
                    raise AIProviderError(
                        "Invalid OpenRouter API key.",
                        status_code=401,
                    )

                if response.status_code == 402:
                    raise AIProviderError(
                        "OpenRouter account has insufficient credits.",
                        status_code=402,
                    )

                if response.status_code >= 500:
                    raise AIProviderError(
                        "OpenRouter server error. Try again later.",
                        status_code=response.status_code,
                    )

                if response.status_code != 200:
                    raise AIProviderError(
                        f"OpenRouter returned status {response.status_code}.",
                        status_code=response.status_code,
                    )

                return response.json()

        except httpx.TimeoutException:
            raise AITimeoutError(
                f"OpenRouter request timed out after {DEFAULT_TIMEOUT}s.",
                status_code=408,
            )
        except httpx.ConnectError:
            raise AIProviderError(
                "Could not connect to OpenRouter. Check network.",
                status_code=503,
            )
        except (AIProviderError, AIRateLimitError, AITimeoutError, AIConfigurationError):
            raise
        except Exception as exc:
            raise AIProviderError(
                f"Unexpected error calling OpenRouter: {type(exc).__name__}",
            ) from exc
