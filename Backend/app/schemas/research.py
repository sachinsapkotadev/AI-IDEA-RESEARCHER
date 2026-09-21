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


class SourceResponse(BaseModel):
    """A source in the research result."""

    title: str
    url: str | None = None
    source_type: str = "web"


class ResearchResultResponse(BaseModel):
    """Structured research result."""

    topic: str
    summary: str
    findings: list[str] = []
    problems: list[str] = []
    opportunities: list[str] = []
    sources: list[SourceResponse] = []
    uncertainties: list[str] = []


class ResearchRunResponse(BaseModel):
    """Response for a research run."""

    id: int
    topic: str
    status: str
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


class AIErrorDetail(BaseModel):
    """Error detail for AI-related errors."""

    code: str
    message: str


class AIErrorResponse(BaseModel):
    """Error response for AI failures."""

    detail: AIErrorDetail
