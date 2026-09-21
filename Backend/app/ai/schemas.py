"""Pydantic schemas for AI request/response data."""

from pydantic import BaseModel, Field


class SourceInfo(BaseModel):
    """A single source referenced in AI research output."""

    title: str = Field(..., min_length=1, max_length=500)
    url: str | None = Field(default=None, max_length=2000)
    source_type: str = Field(default="web", max_length=50)


class ResearchResult(BaseModel):
    """Validated structured research output from the AI."""

    topic: str = Field(..., min_length=1, max_length=500)
    summary: str = Field(..., min_length=1)
    findings: list[str] = Field(default_factory=list)
    problems: list[str] = Field(default_factory=list)
    opportunities: list[str] = Field(default_factory=list)
    sources: list[SourceInfo] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)


class AIUsage(BaseModel):
    """Token usage information from an AI response."""

    input_tokens: int | None = None
    output_tokens: int | None = None


class AIResponse(BaseModel):
    """Raw response from an AI provider before validation."""

    content: str
    model: str | None = None
    usage: AIUsage = Field(default_factory=AIUsage)
