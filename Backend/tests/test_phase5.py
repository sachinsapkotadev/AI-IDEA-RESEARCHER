"""Tests for Phase 5 — Multi-agent analysis pipeline and opportunity engine."""

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.database.base import Base


# Shared engine for client + db fixture coherence
_test_engine = None
_TestSession = None


def _make_test_engine():
    """Create a fresh in-memory SQLite engine with tables."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture(autouse=True)
def setup_db():
    """Create fresh DB and override get_db for all tests."""
    global _test_engine, _TestSession
    from app.database.database import get_db
    from app.main import app as _app

    _test_engine = _make_test_engine()
    _TestSession = sessionmaker(bind=_test_engine)

    def _override():
        db = _TestSession()
        try:
            yield db
        finally:
            db.close()

    _app.dependency_overrides[get_db] = _override
    yield
    _app.dependency_overrides.clear()
    _test_engine.dispose()
    _test_engine = None
    _TestSession = None


@pytest.fixture
def client():
    from app.main import app as _app
    return TestClient(_app)


@pytest.fixture
def db():
    """DB session sharing the same engine as the client."""
    session = _TestSession()
    yield session
    session.close()


def _create_completed_research(db, topic="Test topic"):
    """Helper to create a completed ResearchRun with sources."""
    from app.database.models.research import ResearchRun, ResearchStatus
    from app.database.models.source import ResearchSource, SourceStatus, SourceType

    run = ResearchRun(
        topic=topic,
        status=ResearchStatus.COMPLETED,
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
    )
    db.add(run)
    db.flush()

    source = ResearchSource(
        research_run_id=run.id,
        title="Test Source",
        url="https://example.com/test",
        source_type=SourceType.WEB,
        domain="example.com",
        snippet="Test snippet about the topic.",
        content="This is test content about SaaS opportunities for small businesses.",
        quality="blog",
        status=SourceStatus.SUCCESS,
        word_count=10,
        rank=1,
    )
    db.add(source)
    db.commit()
    db.refresh(run)
    return run


# ============================================
# 1. MarketAnalyst Schema Tests
# ============================================

class TestMarketAnalystSchema:
    def test_valid_market_analysis(self):
        from app.agents.schemas import MarketAnalysis, MarketDemandSignal
        ma = MarketAnalysis(
            market_problems=["Problem 1", "Problem 2"],
            target_user_groups=["Small businesses"],
            demand_signals=[
                MarketDemandSignal(signal="High search volume", evidence="Source data", source_refs=["S1"])
            ],
            observed_trends=["Growing trend"],
            market_size_note="$10B market [SOURCE: S1]",
            assumptions=["Assumption 1"],
            uncertainties=["Uncertainty 1"],
            source_references=["S1", "S2"],
        )
        assert len(ma.market_problems) == 2
        assert ma.market_size_note.startswith("$")

    def test_empty_market_analysis_valid(self):
        from app.agents.schemas import MarketAnalysis
        ma = MarketAnalysis()
        assert ma.market_problems == []
        assert ma.market_size_note == "Not established from collected sources."

    def test_demand_signal_validation(self):
        from app.agents.schemas import MarketDemandSignal
        with pytest.raises(ValidationError):
            MarketDemandSignal(signal="", evidence="test")


# ============================================
# 2. CompetitorAnalyst Schema Tests
# ============================================

class TestCompetitorAnalystSchema:
    def test_valid_competitor_analysis(self):
        from app.agents.schemas import CompetitorAnalysis, Competitor
        ca = CompetitorAnalysis(
            competitors=[
                Competitor(
                    name="Competitor A",
                    url="https://competitor.com",
                    offering="SaaS tool",
                    target_users="Developers",
                    pricing="$29/mo",
                    strengths=["Good UI"],
                    weaknesses=["Limited API"],
                    source_refs=["S1"],
                )
            ],
            opportunity_gaps=["No mobile app"],
            competitive_landscape_summary="Crowded market",
            assumptions=["Market is growing"],
            source_references=["S1"],
        )
        assert len(ca.competitors) == 1
        assert ca.competitors[0].name == "Competitor A"

    def test_competitor_no_pricing(self):
        from app.agents.schemas import Competitor
        c = Competitor(name="Test", offering="tool")
        assert c.pricing == "Not found in sources"

    def test_empty_competitor_analysis_valid(self):
        from app.agents.schemas import CompetitorAnalysis
        ca = CompetitorAnalysis()
        assert ca.competitors == []


# ============================================
# 3. IdeaGenerator Schema Tests
# ============================================

class TestIdeaGeneratorSchema:
    def test_valid_idea(self):
        from app.agents.schemas import Idea, IdeaGenerationResult
        idea = Idea(
            title="AI Content Writer",
            problem="Small businesses struggle with content creation",
            target_users="Small business owners",
            solution="AI-powered content writing tool",
            core_features=["Blog writer", "Social media posts"],
            mvp="Basic AI writer with templates",
            differentiation="Focus on small business tone",
            monetization="Subscription $19/mo",
            assumptions=["Users want AI help"],
            evidence=["Source S1 mentions content struggle"],
            risks=["AI quality concerns"],
        )
        result = IdeaGenerationResult(ideas=[idea], source_references=["S1"])
        assert len(result.ideas) == 1
        assert result.ideas[0].title == "AI Content Writer"

    def test_idea_requires_title_and_problem(self):
        from app.agents.schemas import Idea
        with pytest.raises(ValidationError):
            Idea(title="", problem="", target_users="u", solution="s")

    def test_empty_idea_generation_valid(self):
        from app.agents.schemas import IdeaGenerationResult
        igr = IdeaGenerationResult()
        assert igr.ideas == []


# ============================================
# 4. TechnicalAnalyst Schema Tests
# ============================================

class TestTechnicalAnalystSchema:
    def test_valid_technical_analysis(self):
        from app.agents.schemas import TechnicalAnalysis, TechnicalIdeaAnalysis
        ta = TechnicalAnalysis(
            idea_analyses=[
                TechnicalIdeaAnalysis(
                    idea_title="AI Content Writer",
                    architecture="React + FastAPI + PostgreSQL",
                    complexity="medium",
                    major_technical_risks=["AI API costs"],
                    estimated_development_scope="Estimate: 6-8 weeks for MVP",
                )
            ],
            source_references=["S1"],
        )
        assert len(ta.idea_analyses) == 1
        assert ta.idea_analyses[0].complexity == "medium"

    def test_complexity_enum_validation(self):
        from app.agents.schemas import TechnicalIdeaAnalysis
        with pytest.raises(ValidationError):
            TechnicalIdeaAnalysis(idea_title="Test", complexity="very_high")

    def test_complexity_valid_values(self):
        from app.agents.schemas import TechnicalIdeaAnalysis
        for c in ("low", "medium", "high"):
            ta = TechnicalIdeaAnalysis(idea_title="Test", complexity=c)
            assert ta.complexity == c


# ============================================
# 5. ValidationPlanner Schema Tests
# ============================================

class TestValidationPlannerSchema:
    def test_valid_validation_result(self):
        from app.agents.schemas import ValidationResult, ValidationPlanItem
        vr = ValidationResult(
            validation_plans=[
                ValidationPlanItem(
                    idea_title="AI Content Writer",
                    target_user="Small business owners",
                    problem_hypothesis="Small businesses need affordable content",
                    value_proposition_hypothesis="AI reduces content creation time",
                    validation_questions=["Do users want AI content?"],
                    landing_page_test="Create landing page",
                    interview_plan="Interview 10 SMB owners",
                    prototype_test="Build clickable prototype",
                    success_signals=["50% sign up rate"],
                    failure_signals=["< 5% interest"],
                    next_step="Create landing page",
                )
            ],
            source_references=["S1"],
        )
        assert len(vr.validation_plans) == 1
        assert vr.validation_plans[0].idea_title == "AI Content Writer"

    def test_empty_validation_result_valid(self):
        from app.agents.schemas import ValidationResult
        vr = ValidationResult()
        assert vr.validation_plans == []


# ============================================
# 6. Malformed/Invalid AI Output Tests
# ============================================

class TestMalformedAIOutput:
    def test_market_analysis_rejects_bad_json(self):
        from app.ai.provider import _extract_json_from_response
        with pytest.raises(Exception):
            _extract_json_from_response("not json at all {{{")

    def test_market_analysis_rejects_bad_complexity(self):
        from app.agents.schemas import TechnicalIdeaAnalysis
        with pytest.raises(ValidationError):
            TechnicalIdeaAnalysis(idea_title="T", complexity="invalid")

    def test_competitor_rejects_empty_name(self):
        from app.agents.schemas import Competitor
        with pytest.raises(ValidationError):
            Competitor(name="", offering="tool")

    def test_idea_generation_rejects_empty_title(self):
        from app.agents.schemas import Idea
        with pytest.raises(ValidationError):
            Idea(title="", problem="P", target_users="U", solution="S")

    def test_validation_plan_rejects_empty_idea_title(self):
        from app.agents.schemas import ValidationPlanItem
        with pytest.raises(ValidationError):
            ValidationPlanItem(idea_title="", target_user="U")


# ============================================
# 7. Successful Agent Execution Tests
# ============================================

class TestAgentExecution:
    @pytest.mark.asyncio
    async def test_market_analyst_execution(self, db):
        from app.agents.market import MarketAnalyst
        from app.agents.schemas import MarketAnalysis
        from app.database.models.research import ResearchStatus

        run = _create_completed_research(db)

        mock_provider = MagicMock()
        mock_provider._resolve_model = MagicMock(return_value="test-model")
        mock_provider.generate = AsyncMock(return_value=MagicMock(
            content=json.dumps({
                "market_problems": ["Problem 1"],
                "target_user_groups": ["Group 1"],
                "demand_signals": [],
                "observed_trends": ["Trend 1"],
                "market_size_note": "Not established from collected sources.",
                "assumptions": [],
                "uncertainties": [],
                "source_references": ["S1"],
            }),
            usage=MagicMock(input_tokens=100, output_tokens=200),
            key_slot="00",
        ))

        agent = MarketAnalyst(provider=mock_provider)
        result, agent_run = await agent.execute(
            research_run_id=run.id,
            db=db,
            topic="Test topic",
            source_context="[S1] Test content",
            source_references="[S1] Test Source",
        )

        assert result is not None
        assert isinstance(result, MarketAnalysis)
        assert result.market_problems == ["Problem 1"]
        assert agent_run.status.value == "completed"
        assert agent_run.input_tokens == 100
        assert agent_run.output_tokens == 200

    @pytest.mark.asyncio
    async def test_competitor_analyst_execution(self, db):
        from app.agents.competitor import CompetitorAnalyst
        from app.agents.schemas import CompetitorAnalysis

        run = _create_completed_research(db)

        mock_provider = MagicMock()
        mock_provider._resolve_model = MagicMock(return_value="test-model")
        mock_provider.generate = AsyncMock(return_value=MagicMock(
            content=json.dumps({
                "competitors": [],
                "opportunity_gaps": ["Gap 1"],
                "competitive_landscape_summary": "Summary",
                "assumptions": [],
                "source_references": ["S1"],
            }),
            usage=MagicMock(input_tokens=50, output_tokens=100),
            key_slot="01",
        ))

        agent = CompetitorAnalyst(provider=mock_provider)
        result, agent_run = await agent.execute(
            research_run_id=run.id,
            db=db,
            topic="Test",
            source_context="[S1] Content",
            source_references="[S1] Ref",
        )

        assert result is not None
        assert isinstance(result, CompetitorAnalysis)
        assert agent_run.status.value == "completed"

    @pytest.mark.asyncio
    async def test_idea_generator_execution(self, db):
        from app.agents.idea import IdeaGenerator
        from app.agents.schemas import IdeaGenerationResult

        run = _create_completed_research(db)

        mock_provider = MagicMock()
        mock_provider._resolve_model = MagicMock(return_value="test-model")
        mock_provider.generate = AsyncMock(return_value=MagicMock(
            content=json.dumps({
                "ideas": [
                    {
                        "title": "Test Idea",
                        "problem": "Test problem",
                        "target_users": "Users",
                        "solution": "Test solution",
                        "core_features": ["Feature 1"],
                        "mvp": "MVP description",
                        "differentiation": "Different",
                        "monetization": "Subscription",
                        "assumptions": [],
                        "evidence": [],
                        "risks": [],
                    }
                ],
                "source_references": ["S1"],
            }),
            usage=MagicMock(input_tokens=200, output_tokens=300),
            key_slot="02",
        ))

        agent = IdeaGenerator(provider=mock_provider)
        result, agent_run = await agent.execute(
            research_run_id=run.id,
            db=db,
            topic="Test",
            source_context="[S1] Content",
            source_references="[S1] Ref",
            market_analysis="{}",
            competitor_analysis="{}",
            num_ideas=1,
        )

        assert result is not None
        assert isinstance(result, IdeaGenerationResult)
        assert len(result.ideas) == 1
        assert result.ideas[0].title == "Test Idea"

    @pytest.mark.asyncio
    async def test_technical_analyst_execution(self, db):
        from app.agents.technical import TechnicalAnalyst
        from app.agents.schemas import TechnicalAnalysis

        run = _create_completed_research(db)

        mock_provider = MagicMock()
        mock_provider._resolve_model = MagicMock(return_value="test-model")
        mock_provider.generate = AsyncMock(return_value=MagicMock(
            content=json.dumps({
                "idea_analyses": [
                    {
                        "idea_title": "Test Idea",
                        "architecture": "React + FastAPI",
                        "complexity": "medium",
                        "major_technical_risks": [],
                        "estimated_development_scope": "Estimate: 4 weeks",
                        "assumptions": [],
                    }
                ],
                "source_references": ["S1"],
            }),
            usage=MagicMock(input_tokens=100, output_tokens=150),
            key_slot="03",
        ))

        agent = TechnicalAnalyst(provider=mock_provider)
        result, agent_run = await agent.execute(
            research_run_id=run.id,
            db=db,
            ideas_text='[{"title": "Test Idea"}]',
            research_context="[S1] Content",
        )

        assert result is not None
        assert isinstance(result, TechnicalAnalysis)
        assert result.idea_analyses[0].complexity == "medium"

    @pytest.mark.asyncio
    async def test_validation_planner_execution(self, db):
        from app.agents.validation import ValidationPlanner
        from app.agents.schemas import ValidationResult

        run = _create_completed_research(db)

        mock_provider = MagicMock()
        mock_provider._resolve_model = MagicMock(return_value="test-model")
        mock_provider.generate = AsyncMock(return_value=MagicMock(
            content=json.dumps({
                "validation_plans": [
                    {
                        "idea_title": "Test Idea",
                        "target_user": "Users",
                        "problem_hypothesis": "Hypothesis",
                        "value_proposition_hypothesis": "VP Hypothesis",
                        "validation_questions": ["Question 1"],
                        "landing_page_test": "LP test",
                        "interview_plan": "Interview plan",
                        "prototype_test": "Prototype test",
                        "success_signals": ["Signal 1"],
                        "failure_signals": ["Fail 1"],
                        "next_step": "Build landing page",
                    }
                ],
                "source_references": ["S1"],
            }),
            usage=MagicMock(input_tokens=100, output_tokens=150),
            key_slot="04",
        ))

        agent = ValidationPlanner(provider=mock_provider)
        result, agent_run = await agent.execute(
            research_run_id=run.id,
            db=db,
            ideas_text='[{"title": "Test Idea"}]',
            market_analysis="{}",
            competitor_analysis="{}",
            technical_analysis="{}",
        )

        assert result is not None
        assert isinstance(result, ValidationResult)
        assert len(result.validation_plans) == 1


# ============================================
# 8. Failed Agent Execution Tests
# ============================================

class TestAgentFailure:
    @pytest.mark.asyncio
    async def test_market_analyst_ai_error(self, db):
        from app.agents.market import MarketAnalyst
        from app.ai.errors import AIProviderError
        from app.database.models.agent_run import AgentRunStatus

        run = _create_completed_research(db)

        mock_provider = MagicMock()
        mock_provider._resolve_model = MagicMock(return_value="test-model")
        mock_provider.generate = AsyncMock(side_effect=AIProviderError("API down"))

        agent = MarketAnalyst(provider=mock_provider)
        result, agent_run = await agent.execute(
            research_run_id=run.id,
            db=db,
            topic="Test",
            source_context="",
            source_references="",
        )

        assert result is None
        assert agent_run.status.value == "failed"
        assert "AI error" in (agent_run.error_message or "")

    @pytest.mark.asyncio
    async def test_market_analyst_invalid_json(self, db):
        from app.agents.market import MarketAnalyst
        from app.database.models.agent_run import AgentRunStatus

        run = _create_completed_research(db)

        mock_provider = MagicMock()
        mock_provider._resolve_model = MagicMock(return_value="test-model")
        mock_provider.generate = AsyncMock(return_value=MagicMock(
            content="This is not JSON at all",
            usage=MagicMock(input_tokens=50, output_tokens=50),
        ))

        agent = MarketAnalyst(provider=mock_provider)
        result, agent_run = await agent.execute(
            research_run_id=run.id,
            db=db,
            topic="Test",
            source_context="",
            source_references="",
        )

        assert result is None
        assert agent_run.status.value == "failed"


# ============================================
# 9. AgentRun Persistence Tests
# ============================================

class TestAgentRunPersistence:
    @pytest.mark.asyncio
    async def test_agent_run_saved_to_db(self, db):
        from app.agents.market import MarketAnalyst
        from app.database.models.agent_run import AgentRun

        run = _create_completed_research(db)

        mock_provider = MagicMock()
        mock_provider._resolve_model = MagicMock(return_value="test-model")
        mock_provider.generate = AsyncMock(return_value=MagicMock(
            content=json.dumps({
                "market_problems": [],
                "target_user_groups": [],
                "demand_signals": [],
                "observed_trends": [],
                "source_references": [],
            }),
            usage=MagicMock(input_tokens=10, output_tokens=20),
            key_slot="00",
        ))

        agent = MarketAnalyst(provider=mock_provider)
        await agent.execute(
            research_run_id=run.id,
            db=db,
            topic="Test",
            source_context="",
            source_references="",
        )
        db.commit()

        agent_runs = db.query(AgentRun).filter(
            AgentRun.research_run_id == run.id
        ).all()
        assert len(agent_runs) == 1
        assert agent_runs[0].agent_name == "MarketAnalyst"
        assert agent_runs[0].model == "test-model"
        assert agent_runs[0].input_tokens == 10
        assert agent_runs[0].output_tokens == 20

    @pytest.mark.asyncio
    async def test_agent_run_failure_persisted(self, db):
        from app.agents.market import MarketAnalyst
        from app.ai.errors import AIProviderError
        from app.database.models.agent_run import AgentRun

        run = _create_completed_research(db)

        mock_provider = MagicMock()
        mock_provider._resolve_model = MagicMock(return_value="test-model")
        mock_provider.generate = AsyncMock(side_effect=AIProviderError("Error"))

        agent = MarketAnalyst(provider=mock_provider)
        await agent.execute(
            research_run_id=run.id,
            db=db,
            topic="Test",
            source_context="",
            source_references="",
        )
        db.commit()

        agent_run = db.query(AgentRun).filter(
            AgentRun.research_run_id == run.id
        ).first()
        assert agent_run.status.value == "failed"
        assert agent_run.error_message is not None


# ============================================
# 10. Orchestrator Dependency Ordering Tests
# ============================================

class TestOrchestratorOrdering:
    @pytest.mark.asyncio
    async def test_orchestrator_runs_in_order(self, db):
        from app.agents.orchestrator import AgentOrchestrator

        call_order = []

        def _make_mock(name):
            m = MagicMock()
            m.model = "test-model"
            m.execute = AsyncMock(return_value=(
                MagicMock(model_dump_json=MagicMock(return_value="{}")),
                MagicMock(status=MagicMock(value="completed")),
            ))
            original_execute = m.execute

            async def _tracked_execute(*args, **kwargs):
                call_order.append(name)
                return await original_execute(*args, **kwargs)

            m.execute = _tracked_execute
            return m

        run = _create_completed_research(db)

        orchestrator = AgentOrchestrator.__new__(AgentOrchestrator)
        orchestrator._provider = MagicMock(model="test-model")
        orchestrator._market_analyst = _make_mock("MarketAnalyst")
        orchestrator._competitor_analyst = _make_mock("CompetitorAnalyst")
        orchestrator._idea_generator = _make_mock("IdeaGenerator")
        orchestrator._technical_analyst = _make_mock("TechnicalAnalyst")
        orchestrator._validation_planner = _make_mock("ValidationPlanner")

        await orchestrator.run(run, db, num_ideas=1)

        assert call_order == [
            "MarketAnalyst",
            "CompetitorAnalyst",
            "IdeaGenerator",
            "TechnicalAnalyst",
            "ValidationPlanner",
        ]

    @pytest.mark.asyncio
    async def test_orchestrator_stops_on_failure(self, db):
        from app.agents.orchestrator import AgentOrchestrator
        from app.database.models.research import ResearchStatus

        call_order = []

        def _make_mock(name, fail=False):
            m = MagicMock()
            m.model = "test-model"
            if fail:
                m.execute = AsyncMock(return_value=(
                    None,
                    MagicMock(status=MagicMock(value="failed")),
                ))
            else:
                m.execute = AsyncMock(return_value=(
                    MagicMock(model_dump_json=MagicMock(return_value="{}")),
                    MagicMock(status=MagicMock(value="completed")),
                ))
            original_execute = m.execute

            async def _tracked_execute(*args, **kwargs):
                call_order.append(name)
                return await original_execute(*args, **kwargs)

            m.execute = _tracked_execute
            return m

        run = _create_completed_research(db)

        orchestrator = AgentOrchestrator.__new__(AgentOrchestrator)
        orchestrator._provider = MagicMock(model="test-model")
        orchestrator._market_analyst = _make_mock("MarketAnalyst")
        orchestrator._competitor_analyst = _make_mock("CompetitorAnalyst", fail=True)
        orchestrator._idea_generator = _make_mock("IdeaGenerator")
        orchestrator._technical_analyst = _make_mock("TechnicalAnalyst")
        orchestrator._validation_planner = _make_mock("ValidationPlanner")

        result = await orchestrator.run(run, db, num_ideas=1)

        assert "MarketAnalyst" in call_order
        assert "CompetitorAnalyst" in call_order
        assert "IdeaGenerator" not in call_order
        assert "TechnicalAnalyst" not in call_order
        assert "ValidationPlanner" not in call_order
        assert result["status"] == "failed"


# ============================================
# 11. Token Usage Persistence Tests
# ============================================

class TestTokenUsagePersistence:
    @pytest.mark.asyncio
    async def test_token_usage_saved(self, db):
        from app.agents.market import MarketAnalyst
        from app.database.models.agent_run import AgentRun

        run = _create_completed_research(db)

        mock_provider = MagicMock()
        mock_provider._resolve_model = MagicMock(return_value="test-model")
        mock_provider.generate = AsyncMock(return_value=MagicMock(
            content=json.dumps({
                "market_problems": [],
                "target_user_groups": [],
                "demand_signals": [],
                "observed_trends": [],
                "source_references": [],
            }),
            usage=MagicMock(input_tokens=1234, output_tokens=5678),
            key_slot="00",
        ))

        agent = MarketAnalyst(provider=mock_provider)
        await agent.execute(
            research_run_id=run.id,
            db=db,
            topic="Test",
            source_context="",
            source_references="",
        )
        db.commit()

        ar = db.query(AgentRun).filter(AgentRun.research_run_id == run.id).first()
        assert ar.input_tokens == 1234
        assert ar.output_tokens == 5678

    @pytest.mark.asyncio
    async def test_token_usage_none_on_error(self, db):
        from app.agents.market import MarketAnalyst
        from app.ai.errors import AIProviderError
        from app.database.models.agent_run import AgentRun

        run = _create_completed_research(db)

        mock_provider = MagicMock()
        mock_provider._resolve_model = MagicMock(return_value="test-model")
        mock_provider.generate = AsyncMock(side_effect=AIProviderError("Error"))

        agent = MarketAnalyst(provider=mock_provider)
        await agent.execute(
            research_run_id=run.id,
            db=db,
            topic="Test",
            source_context="",
            source_references="",
        )
        db.commit()

        ar = db.query(AgentRun).filter(AgentRun.research_run_id == run.id).first()
        assert ar.input_tokens is None
        assert ar.output_tokens is None


# ============================================
# 12. POST /api/research/{id}/analyze
# ============================================

class TestAnalyzeEndpoint:
    def test_analyze_completed_research(self, client, db):
        run = _create_completed_research(db)

        with patch("app.api.routes.analysis.run_analysis_pipeline") as mock_pipeline:
            mock_pipeline.return_value = {
                "research_id": run.id,
                "status": "completed",
                "ideas_generated": 3,
            }
            r = client.post(f"/api/research/{run.id}/analyze")
            assert r.status_code == 202
            d = r.json()
            assert d["status"] == "accepted"
            assert d["research_id"] == run.id

    def test_analyze_not_found(self, client):
        r = client.post("/api/research/99999/analyze")
        assert r.status_code == 404

    def test_analyze_already_analyzing(self, client, db):
        """Should reject if agent is already running."""
        from app.database.models.agent_run import AgentRun, AgentRunStatus

        run = _create_completed_research(db)
        db.add(AgentRun(
            research_run_id=run.id,
            agent_name="MarketAnalyst",
            model="test-model",
            status=AgentRunStatus.RUNNING,
            started_at=datetime.now(timezone.utc),
        ))
        db.commit()

        r = client.post(f"/api/research/{run.id}/analyze")
        assert r.status_code == 409
        assert r.json()["detail"]["code"] == "ANALYSIS_IN_PROGRESS"


# ============================================
# 13. GET /api/ideas
# ============================================

class TestListIdeas:
    def test_list_ideas_empty(self, client):
        r = client.get("/api/ideas")
        assert r.status_code == 200
        d = r.json()
        assert d["items"] == []
        assert d["total"] == 0

    def test_list_ideas_with_data(self, client, db):
        from app.database.models.idea import Idea as IdeaModel, IdeaStatus

        run = _create_completed_research(db)
        idea = IdeaModel(
            research_run_id=run.id,
            title="Test Idea",
            problem="Problem",
            solution="Solution",
            status=IdeaStatus.NEW,
        )
        db.add(idea)
        db.commit()

        r = client.get("/api/ideas")
        assert r.status_code == 200
        d = r.json()
        assert d["total"] == 1
        assert d["items"][0]["title"] == "Test Idea"

    def test_list_ideas_filter_by_status(self, client, db):
        from app.database.models.idea import Idea as IdeaModel, IdeaStatus

        run = _create_completed_research(db)
        db.add(IdeaModel(research_run_id=run.id, title="Idea 1", problem="P", solution="S", status=IdeaStatus.NEW))
        db.add(IdeaModel(research_run_id=run.id, title="Idea 2", problem="P", solution="S", status=IdeaStatus.REJECTED))
        db.commit()

        r = client.get("/api/ideas?status=new")
        assert r.status_code == 200
        assert r.json()["total"] == 1

    def test_list_ideas_invalid_status(self, client):
        r = client.get("/api/ideas?status=invalid_status")
        assert r.status_code == 422

    def test_list_ideas_pagination(self, client, db):
        from app.database.models.idea import Idea as IdeaModel, IdeaStatus

        run = _create_completed_research(db)
        for i in range(5):
            db.add(IdeaModel(research_run_id=run.id, title=f"Idea {i}", problem="P", solution="S", status=IdeaStatus.NEW))
        db.commit()

        r = client.get("/api/ideas?page=1&page_size=2")
        assert r.status_code == 200
        d = r.json()
        assert len(d["items"]) == 2
        assert d["total"] == 5


# ============================================
# 14. GET /api/ideas/{idea_id}
# ============================================

class TestGetIdea:
    def test_get_idea_found(self, client, db):
        from app.database.models.idea import Idea as IdeaModel, IdeaStatus

        run = _create_completed_research(db)
        idea = IdeaModel(
            research_run_id=run.id,
            title="Test Idea",
            problem="Problem",
            solution="Solution",
            target_users="Users",
            status=IdeaStatus.NEW,
        )
        db.add(idea)
        db.commit()
        db.refresh(idea)

        r = client.get(f"/api/ideas/{idea.id}")
        assert r.status_code == 200
        d = r.json()
        assert d["title"] == "Test Idea"
        assert d["problem"] == "Problem"

    def test_get_idea_not_found(self, client):
        r = client.get("/api/ideas/99999")
        assert r.status_code == 404


# ============================================
# 15. GET /api/research/{research_id}/ideas
# ============================================

class TestResearchIdeas:
    def test_research_ideas_found(self, client, db):
        from app.database.models.idea import Idea as IdeaModel, IdeaStatus

        run = _create_completed_research(db)
        db.add(IdeaModel(research_run_id=run.id, title="Idea 1", problem="P", solution="S", status=IdeaStatus.NEW))
        db.add(IdeaModel(research_run_id=run.id, title="Idea 2", problem="P", solution="S", status=IdeaStatus.NEW))
        db.commit()

        r = client.get(f"/api/research/{run.id}/ideas")
        assert r.status_code == 200
        d = r.json()
        assert len(d["ideas"]) == 2
        assert d["research_id"] == run.id

    def test_research_ideas_not_found(self, client):
        r = client.get("/api/research/99999/ideas")
        assert r.status_code == 404

    def test_research_ideas_empty(self, client, db):
        run = _create_completed_research(db)
        r = client.get(f"/api/research/{run.id}/ideas")
        assert r.status_code == 200
        assert r.json()["ideas"] == []


# ============================================
# 16. GET /api/research/{research_id}/agents
# ============================================

class TestAgentRunsEndpoint:
    def test_agent_runs_found(self, client, db):
        from app.database.models.agent_run import AgentRun, AgentRunStatus

        run = _create_completed_research(db)
        db.add(AgentRun(
            research_run_id=run.id,
            agent_name="MarketAnalyst",
            model="test-model",
            status=AgentRunStatus.COMPLETED,
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            input_tokens=100,
            output_tokens=200,
        ))
        db.commit()

        r = client.get(f"/api/research/{run.id}/agents")
        assert r.status_code == 200
        d = r.json()
        assert len(d["agents"]) == 1
        assert d["agents"][0]["agent_name"] == "MarketAnalyst"
        assert d["agents"][0]["input_tokens"] == 100

    def test_agent_runs_not_found(self, client):
        r = client.get("/api/research/99999/agents")
        assert r.status_code == 404

    def test_agent_runs_empty(self, client, db):
        run = _create_completed_research(db)
        r = client.get(f"/api/research/{run.id}/agents")
        assert r.status_code == 200
        assert r.json()["agents"] == []


# ============================================
# 17. GET /api/research/{research_id}/analysis-status
# ============================================

class TestAnalysisStatusEndpoint:
    def test_analysis_status_idle(self, client, db):
        run = _create_completed_research(db)
        r = client.get(f"/api/research/{run.id}/analysis-status")
        assert r.status_code == 200
        d = r.json()
        assert d["status"] == "idle"
        assert d["completed_agents"] == 0
        assert d["total_agents"] == 5

    def test_analysis_status_not_found(self, client):
        r = client.get("/api/research/99999/analysis-status")
        assert r.status_code == 404

    def test_analysis_status_completed(self, client, db):
        from app.database.models.agent_run import AgentRun, AgentRunStatus

        run = _create_completed_research(db)
        agents = ["MarketAnalyst", "CompetitorAnalyst", "IdeaGenerator", "TechnicalAnalyst", "ValidationPlanner"]
        for name in agents:
            db.add(AgentRun(
                research_run_id=run.id,
                agent_name=name,
                model="test-model",
                status=AgentRunStatus.COMPLETED,
                started_at=datetime.now(timezone.utc),
                completed_at=datetime.now(timezone.utc),
            ))
        db.commit()

        r = client.get(f"/api/research/{run.id}/analysis-status")
        assert r.status_code == 200
        d = r.json()
        assert d["status"] == "completed"
        assert d["completed_agents"] == 5

    def test_analysis_status_running(self, client, db):
        from app.database.models.agent_run import AgentRun, AgentRunStatus

        run = _create_completed_research(db)
        db.add(AgentRun(
            research_run_id=run.id,
            agent_name="MarketAnalyst",
            model="test-model",
            status=AgentRunStatus.COMPLETED,
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
        ))
        db.add(AgentRun(
            research_run_id=run.id,
            agent_name="CompetitorAnalyst",
            model="test-model",
            status=AgentRunStatus.RUNNING,
            started_at=datetime.now(timezone.utc),
        ))
        db.commit()

        r = client.get(f"/api/research/{run.id}/analysis-status")
        assert r.status_code == 200
        d = r.json()
        assert d["status"] == "running"
        assert d["current_agent"] == "CompetitorAnalyst"
        assert d["completed_agents"] == 1

    def test_analysis_status_failed(self, client, db):
        from app.database.models.agent_run import AgentRun, AgentRunStatus

        run = _create_completed_research(db)
        db.add(AgentRun(
            research_run_id=run.id,
            agent_name="MarketAnalyst",
            model="test-model",
            status=AgentRunStatus.COMPLETED,
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
        ))
        db.add(AgentRun(
            research_run_id=run.id,
            agent_name="CompetitorAnalyst",
            model="test-model",
            status=AgentRunStatus.FAILED,
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            error_message="AI error",
        ))
        db.commit()

        r = client.get(f"/api/research/{run.id}/analysis-status")
        assert r.status_code == 200
        d = r.json()
        assert d["status"] == "failed"


# ============================================
# 18. Context Utils Tests
# ============================================

class TestContextUtils:
    def test_build_source_context(self):
        from app.agents.context_utils import build_source_context
        from app.database.models.source import ResearchSource, SourceStatus, SourceType

        source = ResearchSource(
            research_run_id=1,
            title="Test Source",
            url="https://example.com",
            source_type=SourceType.WEB,
            domain="example.com",
            snippet="Snippet",
            content="Content text",
            quality="blog",
            status=SourceStatus.SUCCESS,
        )
        ctx = build_source_context([source])
        assert "[S1]" in ctx
        assert "Test Source" in ctx

    def test_build_source_references(self):
        from app.agents.context_utils import build_source_references
        from app.database.models.source import ResearchSource, SourceStatus, SourceType

        source = ResearchSource(
            research_run_id=1,
            title="Test Source",
            url="https://example.com",
            source_type=SourceType.WEB,
            domain="example.com",
            quality="blog",
            status=SourceStatus.SUCCESS,
        )
        refs = build_source_references([source])
        assert "[S1]" in refs
        assert "Test Source" in refs

    def test_truncate_text(self):
        from app.agents.context_utils import truncate_text
        assert truncate_text(None) == ""
        assert truncate_text("short") == "short"
        long_text = "x" * 10000
        result = truncate_text(long_text, max_length=100)
        assert len(result) < 120
        assert "truncated" in result
