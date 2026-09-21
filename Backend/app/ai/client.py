"""OpenRouter HTTP client using httpx with key pool rotation."""

import logging
from typing import Any

import httpx

from app.ai.errors import (
    AIAllKeysExhausted,
    AIConfigurationError,
    AIProviderError,
    AIRateLimitError,
    AITimeoutError,
)
from app.ai.key_pool import OpenRouterKeyPool

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 60.0


class OpenRouterClient:
    """Low-level HTTP client for OpenRouter API with key rotation."""

    def __init__(self, key_pool: OpenRouterKeyPool | None = None) -> None:
        self._key_pool = key_pool or OpenRouterKeyPool()
        if self._key_pool.configured_count == 0:
            raise AIConfigurationError(
                "No OpenRouter API keys configured. "
                "Set OPENROUTER_API_KEY_01 through OPENROUTER_API_KEY_12."
            )

    async def chat_completion(
        self,
        messages: list[dict[str, str]],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> dict[str, Any]:
        """Send a chat completion request to OpenRouter.

        Args:
            messages: List of message dicts with 'role' and 'content'.
            model: The model ID to use.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens in response.

        Returns:
            Raw API response dict with added 'key_slot' field.

        Raises:
            AIConfigurationError: If config is missing.
            AIProviderError: On HTTP or API errors.
            AIRateLimitError: On rate limiting.
            AITimeoutError: On timeout.
            AIAllKeysExhausted: When no keys are available.
        """
        url = "https://openrouter.ai/api/v1/chat/completions"

        last_error: Exception | None = None
        max_retries = min(self._key_pool.configured_count, 3)

        for attempt in range(max_retries):
            try:
                slot, api_key = self._key_pool.get_key()
            except RuntimeError as exc:
                raise AIAllKeysExhausted(str(exc)) from exc

            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://ai-idea-researcher.local",
                "X-Title": "AI Idea Researcher",
            }

            payload = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }

            try:
                async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
                    response = await client.post(url, json=payload, headers=headers)

                    if response.status_code == 401:
                        self._key_pool.mark_failure(slot, retryable=True)
                        last_error = AIProviderError(
                            f"Invalid API key (slot {slot}).",
                            status_code=401,
                        )
                        logger.warning(
                            "OpenRouter 401 | slot=%s | attempt=%d",
                            slot, attempt + 1,
                        )
                        continue

                    if response.status_code == 403:
                        self._key_pool.mark_failure(slot, retryable=True)
                        last_error = AIProviderError(
                            f"API key forbidden (slot {slot}).",
                            status_code=403,
                        )
                        logger.warning(
                            "OpenRouter 403 | slot=%s | attempt=%d",
                            slot, attempt + 1,
                        )
                        continue

                    if response.status_code == 429:
                        self._key_pool.mark_failure(slot, retryable=True)
                        last_error = AIRateLimitError(
                            f"Rate limited (slot {slot}).",
                            status_code=429,
                        )
                        logger.warning(
                            "OpenRouter 429 | slot=%s | attempt=%d",
                            slot, attempt + 1,
                        )
                        continue

                    if response.status_code == 402:
                        self._key_pool.mark_failure(slot, retryable=True)
                        last_error = AIProviderError(
                            f"Insufficient credits (slot {slot}).",
                            status_code=402,
                        )
                        logger.warning(
                            "OpenRouter 402 | slot=%s | attempt=%d",
                            slot, attempt + 1,
                        )
                        continue

                    if response.status_code >= 500:
                        self._key_pool.mark_failure(slot, retryable=True)
                        last_error = AIProviderError(
                            f"Server error (slot {slot}).",
                            status_code=response.status_code,
                        )
                        logger.warning(
                            "OpenRouter %d | slot=%s | attempt=%d",
                            response.status_code, slot, attempt + 1,
                        )
                        continue

                    if response.status_code != 200:
                        self._key_pool.mark_failure(slot, retryable=False)
                        raise AIProviderError(
                            f"OpenRouter returned status {response.status_code} (slot {slot}).",
                            status_code=response.status_code,
                        )

                    # Success
                    self._key_pool.mark_success(slot)
                    result = response.json()
                    result["_key_slot"] = slot
                    return result

            except httpx.TimeoutException:
                self._key_pool.mark_failure(slot, retryable=True)
                last_error = AITimeoutError(
                    f"Request timed out after {DEFAULT_TIMEOUT}s (slot {slot}).",
                    status_code=408,
                )
                logger.warning(
                    "OpenRouter timeout | slot=%s | attempt=%d",
                    slot, attempt + 1,
                )
                continue

            except httpx.ConnectError:
                self._key_pool.mark_failure(slot, retryable=True)
                last_error = AIProviderError(
                    "Could not connect to OpenRouter. Check network.",
                    status_code=503,
                )
                logger.warning(
                    "OpenRouter connection error | slot=%s | attempt=%d",
                    slot, attempt + 1,
                )
                continue

            except (AIProviderError, AIRateLimitError, AITimeoutError, AIConfigurationError, AIAllKeysExhausted):
                raise

            except Exception as exc:
                self._key_pool.mark_failure(slot, retryable=False)
                raise AIProviderError(
                    f"Unexpected error calling OpenRouter: {type(exc).__name__} (slot {slot})",
                ) from exc

        # All retries exhausted
        if last_error:
            raise last_error
        raise AIAllKeysExhausted("All API key retries exhausted.")
