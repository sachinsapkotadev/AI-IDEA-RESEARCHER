"""Abstract search provider interface."""

from abc import ABC, abstractmethod

from app.research.schemas import SearchResult


class SearchProvider(ABC):
    """Abstract interface for web search providers.

    All search providers must implement this interface.
    The provider receives a query and returns validated SearchResult objects.
    """

    @abstractmethod
    async def search(
        self,
        query: str,
        max_results: int = 10,
    ) -> list[SearchResult]:
        """Execute a web search and return results.

        Args:
            query: The search query string.
            max_results: Maximum number of results to return.

        Returns:
            List of validated SearchResult objects.

        Raises:
            SearchProviderError: On API errors.
            SearchConfigurationError: On missing configuration.
        """
