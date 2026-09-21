"""Google Custom Search JSON API provider."""

import logging
from urllib.parse import urlparse

import httpx

from app.core.config import get_settings
from app.research.errors import SearchConfigurationError, SearchProviderError
from app.research.normalizer import extract_domain
from app.research.schemas import SearchResult
from app.research.sources.base import SearchProvider

logger = logging.getLogger(__name__)

GOOGLE_SEARCH_URL = "https://www.googleapis.com/customsearch/v1"
DEFAULT_TIMEOUT = 15.0


class GoogleSearchProvider(SearchProvider):
    """Google Custom Search JSON API implementation.

    Requires:
    - SEARCH_API_KEY: Google API key
    - SEARCH_ENGINE_ID: Custom Search Engine ID

    Optional:
    - SEARCH_DEFAULT_NUM: Default number of results (default: 10)
    """

    def __init__(self) -> None:
        self._settings = get_settings()
        self._validate_config()

    def _validate_config(self) -> None:
        """Ensure required configuration is present."""
        if not getattr(self._settings, "SEARCH_API_KEY", ""):
            raise SearchConfigurationError(
                "SEARCH_API_KEY is not configured. "
                "Set it in your .env file or environment."
            )
        if not getattr(self._settings, "SEARCH_ENGINE_ID", ""):
            raise SearchConfigurationError(
                "SEARCH_ENGINE_ID is not configured. "
                "Set it in your .env file or environment."
            )

    async def search(
        self,
        query: str,
        max_results: int = 10,
    ) -> list[SearchResult]:
        """Execute a Google Custom Search and return results.

        Args:
            query: Search query string.
            max_results: Maximum results (max 10 per API call).

        Returns:
            List of SearchResult objects.

        Raises:
            SearchProviderError: On API or network errors.
            SearchConfigurationError: On missing config.
        """
        # Google Custom Search returns max 10 per call
        # For more, we'd need pagination, but 10 is sufficient for Phase 4
        num = min(max_results, 10)

        params = {
            "key": self._settings.SEARCH_API_KEY,
            "cx": self._settings.SEARCH_ENGINE_ID,
            "q": query,
            "num": num,
        }

        try:
            async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
                response = await client.get(GOOGLE_SEARCH_URL, params=params)

                if response.status_code == 429:
                    raise SearchProviderError(
                        "Google Search API rate limit exceeded.",
                        status_code=429,
                    )

                if response.status_code == 403:
                    raise SearchProviderError(
                        "Google Search API access denied. Check API key.",
                        status_code=403,
                    )

                if response.status_code != 200:
                    raise SearchProviderError(
                        f"Google Search API returned status {response.status_code}.",
                        status_code=response.status_code,
                    )

                data = response.json()

        except httpx.TimeoutException:
            raise SearchProviderError(
                f"Google Search API timed out after {DEFAULT_TIMEOUT}s."
            )
        except httpx.ConnectError:
            raise SearchProviderError(
                "Could not connect to Google Search API."
            )
        except SearchProviderError:
            raise
        except Exception as exc:
            raise SearchProviderError(
                f"Unexpected error calling Google Search: {type(exc).__name__}"
            ) from exc

        # Parse results
        results: list[SearchResult] = []
        items = data.get("items", [])

        for idx, item in enumerate(items):
            url = item.get("link", "")
            if not url:
                continue

            title = item.get("title", "").strip()
            snippet = item.get("snippet", "").strip()
            domain = extract_domain(url)

            result = SearchResult(
                title=title[:500],
                url=url,
                snippet=snippet[:2000],
                source_domain=domain,
                rank=idx + 1,
            )
            results.append(result)

        logger.info(
            "Google search completed | query=%s | results=%d",
            query[:80], len(results),
        )

        return results
