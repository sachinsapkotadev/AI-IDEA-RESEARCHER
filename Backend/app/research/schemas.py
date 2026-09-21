"""Pydantic schemas for research pipeline data."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, field_validator


class SourceQuality(str, Enum):
    """Basic source quality classification."""
    OFFICIAL = "official"
    NEWS = "news"
    COMMUNITY = "community"
    BLOG = "blog"
    DOCUMENTATION = "documentation"
    UNKNOWN = "unknown"


class SearchResult(BaseModel):
    """A single search result from a search provider."""

    title: str = Field(..., min_length=1, max_length=500)
    url: str = Field(..., min_length=1, max_length=2000)
    snippet: str = Field(default="", max_length=2000)
    source_domain: str = Field(default="", max_length=200)
    published_at: datetime | None = None
    rank: int = Field(default=0, ge=0)

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Ensure URL is well-formed."""
        if not v.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        return v


class WebDocument(BaseModel):
    """Extracted content from a web page."""

    url: str
    title: str = ""
    domain: str = ""
    text: str = ""
    retrieved_at: datetime | None = None
    content_type: str = "text/html"
    word_count: int = 0
    status: str = "success"  # success | failed | skipped
    error: str | None = None


class ResearchContext(BaseModel):
    """Prepared context for the AI research agent."""

    topic: str
    search_results: list[SearchResult] = Field(default_factory=list)
    documents: list[WebDocument] = Field(default_factory=list)
    source_count: int = 0
    documents_fetched: int = 0
    documents_failed: int = 0
    characters_sent: int = 0
    source_references: list[dict] = Field(default_factory=list)


class ResearchMetrics(BaseModel):
    """Metrics collected during a research run."""

    sources_found: int = 0
    sources_used: int = 0
    documents_fetched: int = 0
    documents_failed: int = 0
    characters_sent: int = 0
    duration_seconds: float = 0.0
