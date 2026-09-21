"""Pydantic schemas for report generation."""

from pydantic import BaseModel, Field


class ReportMetadata(BaseModel):
    """Metadata included in the report header."""

    research_id: int
    topic: str
    date: str
    status: str
    models_used: list[str] = Field(default_factory=list)
    agent_summary: list[dict] = Field(default_factory=list)


class ReportContent(BaseModel):
    """Structured content for the Markdown report."""

    metadata: ReportMetadata
    executive_summary: str = ""
    sources_section: str = ""
    market_analysis: str = ""
    competitor_analysis: str = ""
    ideas_section: str = ""
    technical_analysis: str = ""
    validation_plan: str = ""
    agent_summary_section: str = ""
    uncertainties_section: str = ""


class ReportGenerationRequest(BaseModel):
    """Request to generate a report."""

    force: bool = Field(
        default=False,
        description="Regenerate even if a completed report exists.",
    )


class ReportResponse(BaseModel):
    """API response for report metadata."""

    research_id: int
    report_status: str
    report_path: str | None = None
    report_generated_at: str | None = None
    error: str | None = None


class ReportContentResponse(BaseModel):
    """API response for report content."""

    research_id: int
    report_status: str
    content: str | None = None
    report_path: str | None = None
