"""OpenRouter API key pool with rotation, retry, and failure tracking."""

import logging
import time
from dataclasses import dataclass, field

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# Keys marked unavailable for this duration after a transient failure (seconds)
COOLDOWN_SECONDS = 60.0
# Maximum consecutive failures before marking key permanently unavailable
MAX_FAILURES = 5


@dataclass
class KeyState:
    """State tracking for a single API key slot."""

    slot: str
    key: str
    failures: int = 0
    last_failure_time: float = 0.0
    temporarily_unavailable: bool = False


class OpenRouterKeyPool:
    """Manages a pool of OpenRouter API keys with rotation and failure handling.

    Responsibilities:
    - Load configured keys from environment
    - Rotate keys deterministically
    - Track failures per key
    - Apply cooldown for temporarily failed keys
    - Provide safe health/status info without revealing secrets
    """

    def __init__(self) -> None:
        settings = get_settings()
        raw_keys = settings.get_api_keys()
        self._keys: list[KeyState] = [
            KeyState(slot=slot, key=key) for slot, key in raw_keys
        ]
        self._index = 0
        logger.info(
            "KeyPool initialized | configured_keys=%d | slots=%s",
            len(self._keys),
            [ks.slot for ks in self._keys],
        )

    @property
    def configured_count(self) -> int:
        """Number of configured keys."""
        return len(self._keys)

    @property
    def available_count(self) -> int:
        """Number of currently available (not cooldown-blocked) keys."""
        now = time.time()
        count = 0
        for ks in self._keys:
            if not ks.temporarily_unavailable:
                count += 1
            elif ks.last_failure_time and (now - ks.last_failure_time) >= COOLDOWN_SECONDS:
                count += 1
        return count

    def get_key(self) -> tuple[str, str]:
        """Select the next available key.

        Returns:
            Tuple of (slot, key_value).

        Raises:
            RuntimeError: If no keys are configured.
            RuntimeError: If all keys are temporarily unavailable.
        """
        if not self._keys:
            raise RuntimeError(
                "No API keys configured. "
                "Set OPENROUTER_API_KEY_01 through OPENROUTER_API_KEY_12."
            )

        now = time.time()
        total = len(self._keys)

        # Try each key once, starting from current index
        for _ in range(total):
            ks = self._keys[self._index % total]
            self._index = (self._index + 1) % total

            # Check if key is temporarily unavailable due to cooldown
            if ks.temporarily_unavailable:
                if ks.last_failure_time and (now - ks.last_failure_time) >= COOLDOWN_SECONDS:
                    # Cooldown expired, try this key
                    ks.temporarily_unavailable = False
                    logger.info("Key slot %s cooldown expired, retrying", ks.slot)
                else:
                    continue

            return ks.slot, ks.key

        # All keys are in cooldown — try the least-recently-failed one
        best = min(self._keys, key=lambda k: k.last_failure_time or 0)
        if best.last_failure_time and (now - best.last_failure_time) >= COOLDOWN_SECONDS:
            best.temporarily_unavailable = False
            return best.slot, best.key

        raise RuntimeError(
            f"All {total} API keys are temporarily unavailable. "
            "Wait for cooldown or configure additional keys."
        )

    def mark_success(self, slot: str) -> None:
        """Mark a key as successfully used (reset failure count)."""
        for ks in self._keys:
            if ks.slot == slot:
                ks.failures = 0
                ks.temporarily_unavailable = False
                return

    def mark_failure(self, slot: str, retryable: bool = True) -> None:
        """Mark a key as failed.

        Args:
            slot: The key slot that failed.
            retryable: Whether this failure type allows retry with another key.
        """
        for ks in self._keys:
            if ks.slot == slot:
                ks.failures += 1
                ks.last_failure_time = time.time()
                if not retryable or ks.failures >= MAX_FAILURES:
                    ks.temporarily_unavailable = True
                    logger.warning(
                        "Key slot %s marked unavailable | failures=%d | retryable=%s",
                        slot, ks.failures, retryable,
                    )
                else:
                    ks.temporarily_unavailable = True
                    logger.info(
                        "Key slot %s temporarily failed | failures=%d",
                        slot, ks.failures,
                    )
                return

    def get_status(self) -> dict:
        """Return safe status information without revealing secrets."""
        return {
            "provider": "openrouter",
            "configured_key_slots": self.configured_count,
            "available_key_slots": self.available_count,
            "status": "ready" if self.configured_count > 0 else "not_configured",
        }
