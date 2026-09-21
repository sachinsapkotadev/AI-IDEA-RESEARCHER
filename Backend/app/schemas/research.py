"""API request/response schemas for research endpoints."""

from pydantic import BaseModel, Field


class ResearchCreateRequest(BaseModel):
    """Request body for creating a new research run."""

    topic: str = Field(
        ...,
        min_length=3,
        max_length=500,
        description="The research topic to investigate.",
        examples=["SaaS opportunities for small businesses"],
    )


class SourceDetailResponse(BaseModel):
    """A source in the research result."""

    id: int
    title: str
    url: str | None = None
    source_type: str = "web"
    domain: str | None = None
    snippet: str | None = None
    quality: str | None = None
    status: str = "success"
    word_count: int | None = None
    rank: int | None = None
    published_at: str | None = None
    retrieved_at: str | None = None


class SourceResponse(BaseModel):
    """A source summary in the research result (no content)."""

    id: int
    title: str
    url: str | None = None
    source_type: str = "web"
    domain: str | None = None
    quality: str | None = None
    status: str = "success"
    word_count: int | None = None
    rank: int | None = None


class ResearchResultResponse(BaseModel):
    """Structured research result."""

    topic: str
    summary: str
    findings: list[str] = []
    problems: list[str] = []
    opportunities: list[str] = []
    source_references: list[str] = []
    uncertainties: list[str] = []


class ResearchRunResponse(BaseModel):
    """Response for a research run."""

    id: int
    topic: str
    status: str
    sources_found: int = 0
    sources_used: int = 0
    result: ResearchResultResponse | None = None
    started_at: str | None = None
    completed_at: str | None = None
    created_at: str


class ResearchListResponse(BaseModel):
    """Paginated list of research runs."""

    items: list[ResearchRunResponse]
    total: int
    page: int
    page_size: int


class ResearchSourcesResponse(BaseModel):
    """List of sources for a research run."""

    research_id: int
    topic: str
    sources: list[SourceResponse]


class AIErrorDetail(BaseModel):
    """Error detail for AI-related errors."""

    code: str
    message: str


class AIErrorResponse(BaseModel):
    """Error response for AI failures."""

    detail: AIErrorDetail
