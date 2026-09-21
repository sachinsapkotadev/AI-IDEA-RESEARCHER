"""Pydantic schemas for multi-agent analysis pipeline."""

from pydantic import BaseModel, Field


# --- Market Analyst ---

class MarketDemandSignal(BaseModel):
    """A single demand signal."""
    signal: str = Field(..., min_length=1, max_length=500)
    evidence: str = Field(default="", max_length=1000)
    source_refs: list[str] = Field(default_factory=list)


class MarketAnalysis(BaseModel):
    """Output of the Market Analyst agent."""
    market_problems: list[str] = Field(default_factory=list, max_length=20)
    target_user_groups: list[str] = Field(default_factory=list, max_length=10)
    demand_signals: list[MarketDemandSignal] = Field(default_factory=list, max_length=15)
    observed_trends: list[str] = Field(default_factory=list, max_length=15)
    market_size_note: str = Field(default="Not established from collected sources.", max_length=2000)
    assumptions: list[str] = Field(default_factory=list, max_length=15)
    uncertainties: list[str] = Field(default_factory=list, max_length=15)
    source_references: list[str] = Field(default_factory=list)


# --- Competitor Analyst ---

class Competitor(BaseModel):
    """A single competitor analysis."""
    name: str = Field(..., min_length=1, max_length=200)
    url: str | None = Field(default=None, max_length=2000)
    offering: str = Field(default="", max_length=1000)
    target_users: str = Field(default="", max_length=500)
    pricing: str = Field(default="Not found in sources", max_length=500)
    strengths: list[str] = Field(default_factory=list, max_length=10)
    weaknesses: list[str] = Field(default_factory=list, max_length=10)
    source_refs: list[str] = Field(default_factory=list)


class CompetitorAnalysis(BaseModel):
    """Output of the Competitor Analyst agent."""
    competitors: list[Competitor] = Field(default_factory=list, max_length=15)
    opportunity_gaps: list[str] = Field(default_factory=list, max_length=15)
    competitive_landscape_summary: str = Field(default="", max_length=2000)
    assumptions: list[str] = Field(default_factory=list, max_length=10)
    source_references: list[str] = Field(default_factory=list)


# --- Idea Generator ---

class Idea(BaseModel):
    """A single SaaS/software opportunity idea."""
    title: str = Field(..., min_length=1, max_length=200)
    problem: str = Field(..., min_length=1, max_length=2000)
    target_users: str = Field(..., min_length=1, max_length=1000)
    solution: str = Field(..., min_length=1, max_length=2000)
    core_features: list[str] = Field(default_factory=list, max_length=15)
    mvp: str = Field(default="", max_length=2000)
    differentiation: str = Field(default="", max_length=1500)
    monetization: str = Field(default="", max_length=1000)
    assumptions: list[str] = Field(default_factory=list, max_length=15)
    evidence: list[str] = Field(default_factory=list, max_length=15)
    risks: list[str] = Field(default_factory=list, max_length=15)


class IdeaGenerationResult(BaseModel):
    """Output of the Idea Generator agent."""
    ideas: list[Idea] = Field(default_factory=list, max_length=10)
    source_references: list[str] = Field(default_factory=list)


# --- Technical Analyst ---

class TechnicalIdeaAnalysis(BaseModel):
    """Technical analysis for a single idea."""
    idea_title: str = Field(..., min_length=1, max_length=200)
    architecture: str = Field(default="", max_length=2000)
    frontend_requirements: str = Field(default="", max_length=1000)
    backend_requirements: str = Field(default="", max_length=1000)
    database_requirements: str = Field(default="", max_length=1000)
    external_apis: list[str] = Field(default_factory=list, max_length=10)
    ai_requirements: str = Field(default="", max_length=1000)
    infrastructure: str = Field(default="", max_length=1000)
    complexity: str = Field(default="medium", pattern="^(low|medium|high)$")
    major_technical_risks: list[str] = Field(default_factory=list, max_length=10)
    estimated_development_scope: str = Field(default="", max_length=1000)
    assumptions: list[str] = Field(default_factory=list, max_length=10)


class TechnicalAnalysis(BaseModel):
    """Output of the Technical Analyst agent."""
    idea_analyses: list[TechnicalIdeaAnalysis] = Field(default_factory=list, max_length=10)
    source_references: list[str] = Field(default_factory=list)


# --- Validation Planner ---

class ValidationPlanItem(BaseModel):
    """Validation plan for a single idea."""
    idea_title: str = Field(..., min_length=1, max_length=200)
    target_user: str = Field(default="", max_length=1000)
    problem_hypothesis: str = Field(default="", max_length=2000)
    value_proposition_hypothesis: str = Field(default="", max_length=2000)
    validation_questions: list[str] = Field(default_factory=list, max_length=15)
    landing_page_test: str = Field(default="", max_length=1500)
    interview_plan: str = Field(default="", max_length=1500)
    prototype_test: str = Field(default="", max_length=1500)
    success_signals: list[str] = Field(default_factory=list, max_length=10)
    failure_signals: list[str] = Field(default_factory=list, max_length=10)
    next_step: str = Field(default="", max_length=1000)


class ValidationResult(BaseModel):
    """Output of the Validation Planner agent."""
    validation_plans: list[ValidationPlanItem] = Field(default_factory=list, max_length=10)
    source_references: list[str] = Field(default_factory=list)


# --- Pipeline Status ---

class AnalysisStatusResponse(BaseModel):
    """Response for analysis pipeline status."""
    research_id: int
    status: str
    current_agent: str | None = None
    completed_agents: int = 0
    total_agents: int = 5
    started_at: str | None = None
    completed_at: str | None = None
