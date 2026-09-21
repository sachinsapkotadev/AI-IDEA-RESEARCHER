"""Research pipeline error types."""


class ResearchError(Exception):
    """Base class for research-related errors."""


class SearchProviderError(ResearchError):
    """Raised when the search provider returns an error."""


class SearchConfigurationError(ResearchError):
    """Raised when search provider is not configured."""


class ContentExtractionError(ResearchError):
    """Raised when page content cannot be extracted."""


class NoUsableSourcesError(ResearchError):
    """Raised when zero usable sources are collected."""
