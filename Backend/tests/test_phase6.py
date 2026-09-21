"""Tests for Phase 6 — Key pool, model registry, report generation, GitHub integration, AI status."""

import asyncio
import json
import os
import time
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
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


def _make_settings(**overrides):
    """Create a Settings object that ignores .env file for clean test isolation."""
    from app.core.config import Settings
    # Use _env_file=None to prevent reading from .env
    return Settings(_env_file=None, **overrides)


# ============================================
# 1. OpenRouterKeyPool Tests
# ============================================

class TestOpenRouterKeyPool:
    def test_key_pool_init_with_keys(self):
        """Key pool initializes with configured keys."""
        from app.ai.key_pool import OpenRouterKeyPool

        with patch("app.ai.key_pool.get_settings") as mock_settings:
            mock_settings.return_value.get_api_keys.return_value = [
                ("01", "key-01-value"),
                ("02", "key-02-value"),
                ("03", "key-03-value"),
            ]
            pool = OpenRouterKeyPool()
            assert pool.configured_count == 3

    def test_key_pool_init_empty(self):
        """Key pool initializes with zero keys."""
        from app.ai.key_pool import OpenRouterKeyPool

        with patch("app.ai.key_pool.get_settings") as mock_settings:
            mock_settings.return_value.get_api_keys.return_value = []
            pool = OpenRouterKeyPool()
            assert pool.configured_count == 0

    def test_get_key_returns_slot_and_key(self):
        """get_key returns (slot, key) tuple."""
        from app.ai.key_pool import OpenRouterKeyPool

        with patch("app.ai.key_pool.get_settings") as mock_settings:
            mock_settings.return_value.get_api_keys.return_value = [
                ("01", "secret-key-01"),
                ("02", "secret-key-02"),
            ]
            pool = OpenRouterKeyPool()
            slot, key = pool.get_key()
            assert slot in ("01", "02")
            assert key.startswith("secret-key-")

    def test_get_key_rotation(self):
        """get_key rotates through keys on successive calls."""
        from app.ai.key_pool import OpenRouterKeyPool

        with patch("app.ai.key_pool.get_settings") as mock_settings:
            mock_settings.return_value.get_api_keys.return_value = [
                ("01", "key-01"),
                ("02", "key-02"),
                ("03", "key-03"),
            ]
            pool = OpenRouterKeyPool()
            slots = [pool.get_key()[0] for _ in range(6)]
            assert slots[:3] == ["01", "02", "03"]
            assert slots[3:6] == ["01", "02", "03"]

    def test_get_key_no_keys_raises(self):
        """get_key raises RuntimeError when no keys configured."""
        from app.ai.key_pool import OpenRouterKeyPool

        with patch("app.ai.key_pool.get_settings") as mock_settings:
            mock_settings.return_value.get_api_keys.return_value = []
            pool = OpenRouterKeyPool()
            with pytest.raises(RuntimeError, match="No API keys configured"):
                pool.get_key()

    def test_get_key_all_unavailable_raises(self):
        """get_key raises RuntimeError when all keys in cooldown."""
        from app.ai.key_pool import OpenRouterKeyPool

        with patch("app.ai.key_pool.get_settings") as mock_settings:
            mock_settings.return_value.get_api_keys.return_value = [
                ("01", "key-01"),
            ]
            pool = OpenRouterKeyPool()
            pool.mark_failure("01")
            with pytest.raises(RuntimeError, match="temporarily unavailable"):
                pool.get_key()

    def test_mark_success_resets_failures(self):
        """mark_success resets failure count and availability."""
        from app.ai.key_pool import OpenRouterKeyPool

        with patch("app.ai.key_pool.get_settings") as mock_settings:
            mock_settings.return_value.get_api_keys.return_value = [
                ("01", "key-01"),
                ("02", "key-02"),
            ]
            pool = OpenRouterKeyPool()
            pool.mark_failure("01")
            pool.mark_failure("01")
            slot, _ = pool.get_key()
            assert slot == "02"
            pool.mark_success("01")
            assert pool.available_count == 2

    def test_mark_failure_sets_cooldown(self):
        """mark_failure marks key as temporarily unavailable."""
        from app.ai.key_pool import OpenRouterKeyPool

        with patch("app.ai.key_pool.get_settings") as mock_settings:
            mock_settings.return_value.get_api_keys.return_value = [
                ("01", "key-01"),
                ("02", "key-02"),
            ]
            pool = OpenRouterKeyPool()
            pool.mark_failure("01")
            assert pool.available_count == 1

    def test_mark_failure_non_retryable(self):
        """Non-retryable failure marks key unavailable immediately."""
        from app.ai.key_pool import OpenRouterKeyPool

        with patch("app.ai.key_pool.get_settings") as mock_settings:
            mock_settings.return_value.get_api_keys.return_value = [
                ("01", "key-01"),
            ]
            pool = OpenRouterKeyPool()
            pool.mark_failure("01", retryable=False)
            assert pool.available_count == 0

    def test_cooldown_expiry(self):
        """Key becomes available again after cooldown expires."""
        from app.ai.key_pool import OpenRouterKeyPool, COOLDOWN_SECONDS

        with patch("app.ai.key_pool.get_settings") as mock_settings:
            mock_settings.return_value.get_api_keys.return_value = [
                ("01", "key-01"),
            ]
            pool = OpenRouterKeyPool()
            pool.mark_failure("01")
            assert pool.available_count == 0
            pool._keys[0].last_failure_time = time.time() - COOLDOWN_SECONDS - 1
            assert pool.available_count == 1

    def test_get_status_no_secrets(self):
        """get_status never exposes API key values."""
        from app.ai.key_pool import OpenRouterKeyPool

        with patch("app.ai.key_pool.get_settings") as mock_settings:
            mock_settings.return_value.get_api_keys.return_value = [
                ("01", "super-secret-key-123"),
            ]
            pool = OpenRouterKeyPool()
            status = pool.get_status()
            assert "super-secret-key" not in json.dumps(status)
            assert status["configured_key_slots"] == 1
            assert status["provider"] == "openrouter"

    def test_available_count_reflects_cooldown_state(self):
        """available_count returns correct count based on cooldown state."""
        from app.ai.key_pool import OpenRouterKeyPool, COOLDOWN_SECONDS

        with patch("app.ai.key_pool.get_settings") as mock_settings:
            mock_settings.return_value.get_api_keys.return_value = [
                ("01", "key-01"),
                ("02", "key-02"),
                ("03", "key-03"),
            ]
            pool = OpenRouterKeyPool()
            assert pool.available_count == 3
            pool.mark_failure("01")
            pool.mark_failure("02")
            assert pool.available_count == 1
            pool._keys[0].last_failure_time = time.time() - COOLDOWN_SECONDS - 1
            pool._keys[1].last_failure_time = time.time() - COOLDOWN_SECONDS - 1
            assert pool.available_count == 3


# ============================================
# 2. ModelRegistry Tests
# ============================================

class TestModelRegistry:
    def _make_registry(self, **model_overrides):
        """Create a ModelRegistry with a mocked Settings, bypassing lru_cache."""
        from app.ai.model_registry import ModelRegistry

        # Build a mock settings with all required attrs
        ms = MagicMock()
        ms.OPENROUTER_MODEL = model_overrides.get("OPENROUTER_MODEL", "default-model")
        ms.MODEL_MARKET_ANALYST = model_overrides.get("MODEL_MARKET_ANALYST", "")
        ms.MODEL_COMPETITOR_ANALYST = model_overrides.get("MODEL_COMPETITOR_ANALYST", "")
        ms.MODEL_IDEA_GENERATOR = model_overrides.get("MODEL_IDEA_GENERATOR", "")
        ms.MODEL_TECHNICAL_ANALYST = model_overrides.get("MODEL_TECHNICAL_ANALYST", "")
        ms.MODEL_VALIDATION_PLANNER = model_overrides.get("MODEL_VALIDATION_PLANNER", "")

        with patch("app.ai.model_registry.get_settings", return_value=ms):
            # Clear the lru_cache so our patch is used
            from app.core.config import get_settings
            get_settings.cache_clear()
            try:
                registry = ModelRegistry()
            finally:
                get_settings.cache_clear()
        return registry

    def test_get_model_agent_specific(self):
        """Returns agent-specific model when configured."""
        registry = self._make_registry(
            OPENROUTER_MODEL="default-model",
            MODEL_MARKET_ANALYST="custom-market-model",
        )
        model = registry.get_model("MarketAnalyst")
        assert model == "custom-market-model"

    def test_get_model_falls_back_to_default(self):
        """Falls back to OPENROUTER_MODEL when no agent-specific model."""
        registry = self._make_registry(
            OPENROUTER_MODEL="fallback-model",
            MODEL_MARKET_ANALYST="",
        )
        model = registry.get_model("MarketAnalyst")
        assert model == "fallback-model"

    def test_get_model_no_model_raises(self):
        """Raises ValueError when no model configured at all."""
        registry = self._make_registry(OPENROUTER_MODEL="")
        with pytest.raises(ValueError, match="No model configured"):
            registry.get_model("MarketAnalyst")

    def test_get_model_default_key(self):
        """get_model('default') returns OPENROUTER_MODEL."""
        registry = self._make_registry(OPENROUTER_MODEL="the-default")
        model = registry.get_model("default")
        assert model == "the-default"

    def test_get_model_config(self):
        """get_model_config returns full ModelConfig."""
        registry = self._make_registry(OPENROUTER_MODEL="test-model")
        config = registry.get_model_config("MarketAnalyst")
        assert config.model_id == "test-model"
        assert config.agent_name == "MarketAnalyst"

    def test_is_configured_true(self):
        """is_configured returns True when model is set."""
        registry = self._make_registry(OPENROUTER_MODEL="some-model")
        assert registry.is_configured() is True

    def test_is_configured_false(self):
        """is_configured returns False when no model set."""
        registry = self._make_registry(OPENROUTER_MODEL="")
        assert registry.is_configured() is False

    def test_get_all_configured_models(self):
        """Returns dict of all agent names to models."""
        registry = self._make_registry(
            OPENROUTER_MODEL="default-model",
            MODEL_MARKET_ANALYST="market-model",
            MODEL_COMPETITOR_ANALYST="",
            MODEL_IDEA_GENERATOR="idea-model",
            MODEL_TECHNICAL_ANALYST="",
            MODEL_VALIDATION_PLANNER="",
        )
        models = registry.get_all_configured_models()
        assert models["MarketAnalyst"] == "market-model"
        assert models["IdeaGenerator"] == "idea-model"
        # Falls back to default when agent-specific is empty
        assert models["CompetitorAnalyst"] == "default-model"


# ============================================
# 3. Config Tests
# ============================================

class TestConfig:
    def test_get_api_keys_filters_empty(self):
        """get_api_keys filters out empty keys."""
        s = _make_settings(
            OPENROUTER_API_KEY_01="key-01",
            OPENROUTER_API_KEY_02="",
            OPENROUTER_API_KEY_03="key-03",
        )
        keys = s.get_api_keys()
        assert len(keys) == 2
        assert keys[0] == ("01", "key-01")
        assert keys[1] == ("03", "key-03")

    def test_get_api_keys_all_empty(self):
        """get_api_keys returns empty list when no keys set."""
        s = _make_settings()
        keys = s.get_api_keys()
        assert len(keys) == 0

    def test_openrouter_api_keys_filters_placeholders(self):
        """openrouter_api_keys filters placeholder values."""
        s = _make_settings(
            OPENROUTER_API_KEY_01="real-key-123",
            OPENROUTER_API_KEY_02="YOUR_KEY_HERE",
            OPENROUTER_API_KEY_03="xxxxxxxxxxxx",
        )
        keys = s.openrouter_api_keys
        assert len(keys) == 1
        assert keys[0] == "real-key-123"

    def test_get_agent_model(self):
        """get_agent_model returns correct agent-specific model."""
        s = _make_settings(
            MODEL_MARKET_ANALYST="market-m",
            MODEL_COMPETITOR_ANALYST="comp-m",
            MODEL_IDEA_GENERATOR="idea-m",
            MODEL_TECHNICAL_ANALYST="tech-m",
            MODEL_VALIDATION_PLANNER="val-m",
            DEFAULT_MODEL="default-m",
        )
        assert s.get_agent_model("MarketAnalyst") == "market-m"
        assert s.get_agent_model("CompetitorAnalyst") == "comp-m"
        assert s.get_agent_model("IdeaGenerator") == "idea-m"
        assert s.get_agent_model("TechnicalAnalyst") == "tech-m"
        assert s.get_agent_model("ValidationPlanner") == "val-m"
        assert s.get_agent_model("UnknownAgent") == "default-m"

    def test_reports_dir_default(self):
        """REPORTS_DIR has a default value."""
        s = _make_settings()
        assert s.REPORTS_DIR == "./reports"

    def test_github_config_defaults(self):
        """GitHub config has expected defaults."""
        s = _make_settings()
        assert s.GITHUB_DEFAULT_BRANCH == "main"
        assert s.GITHUB_RESEARCH_BRANCH_PREFIX == "research/"
        assert s.GITHUB_TOKEN == ""
        assert s.GITHUB_OWNER == ""
        assert s.GITHUB_REPO == ""

    def test_cors_origin_list(self):
        """cors_origin_list parses comma-separated origins."""
        s = _make_settings(CORS_ORIGINS="http://a.com,http://b.com")
        assert s.cors_origin_list == ["http://a.com", "http://b.com"]


# ============================================
# 4. Report Generator Tests
# ============================================

class TestReportGenerator:
    def test_render_markdown_basic(self):
        """render_markdown produces valid markdown output."""
        from app.reports.generator import ReportGenerator
        from app.reports.schemas import ReportContent, ReportMetadata

        gen = ReportGenerator()
        content = ReportContent(
            metadata=ReportMetadata(
                research_id=1,
                topic="Test Topic",
                date="2026-01-01",
                status="completed",
                models_used=["model-a"],
                agent_summary=[
                    {
                        "agent": "MarketAnalyst",
                        "model": "model-a",
                        "key_slot": "00",
                        "status": "completed",
                        "input_tokens": 100,
                        "output_tokens": 200,
                        "duration_seconds": 5.2,
                    }
                ],
            ),
            executive_summary="This is a summary.\n",
            sources_section="- [S1] Source 1\n",
        )
        md = gen.render_markdown(content)
        assert "# AI IDEA RESEARCHER REPORT" in md
        assert "Test Topic" in md
        assert "2026-01-01" in md
        assert "model-a" in md
        assert "MarketAnalyst" in md
        # Table header is "Key Slot", data row has "00"
        assert "Key Slot" in md
        assert "00" in md
        assert "This is a summary" in md
        assert "[S1]" in md
        assert "Do not treat this as guaranteed business advice" in md

    def test_render_markdown_empty_sections(self):
        """render_markdown handles empty optional sections."""
        from app.reports.generator import ReportGenerator
        from app.reports.schemas import ReportContent, ReportMetadata

        gen = ReportGenerator()
        content = ReportContent(
            metadata=ReportMetadata(
                research_id=2,
                topic="Empty",
                date="2026-01-01",
                status="completed",
            ),
        )
        md = gen.render_markdown(content)
        assert "# AI IDEA RESEARCHER REPORT" in md
        assert "## Executive Summary" not in md
        assert "## Market Analysis" not in md

    def test_build_sources_section_with_sources(self):
        """_build_sources_section formats sources correctly."""
        from app.reports.generator import ReportGenerator

        gen = ReportGenerator()
        src = MagicMock()
        src.status.value = "success"
        src.title = "Source A"
        src.url = "https://example.com"
        src.quality = "blog"
        result = gen._build_sources_section([src])
        assert "[S1]" in result
        assert "✓" in result
        assert "Source A" in result

    def test_build_sources_section_empty(self):
        """_build_sources_section returns placeholder for no sources."""
        from app.reports.generator import ReportGenerator

        gen = ReportGenerator()
        result = gen._build_sources_section([])
        assert "No sources collected" in result

    def test_build_ideas_section_empty(self):
        """_build_ideas_section returns placeholder for no ideas."""
        from app.reports.generator import ReportGenerator

        gen = ReportGenerator()
        result = gen._build_ideas_section([])
        assert "No ideas generated" in result

    def test_build_agent_summary_empty(self):
        """_build_agent_summary returns placeholder for no runs."""
        from app.reports.generator import ReportGenerator

        gen = ReportGenerator()
        result = gen._build_agent_summary([])
        assert "No agent runs recorded" in result


# ============================================
# 5. Report Service Tests
# ============================================

class TestReportService:
    def test_generate_report_not_found(self):
        """generate_report raises for non-existent research."""
        from app.reports.service import ReportService
        from app.reports.errors import ReportNotFoundError

        mock_settings = MagicMock()
        mock_settings.REPORTS_DIR = "./reports"
        with patch("app.reports.service.get_settings", return_value=mock_settings):
            service = ReportService()
            # Mock db returns None for non-existent run
            mock_db = MagicMock()
            mock_db.query.return_value.filter.return_value.first.return_value = None
            with pytest.raises(ReportNotFoundError):
                service.generate_report(99999, mock_db)

    def test_generate_report_idempotent(self):
        """generate_report returns existing if already completed."""
        from app.reports.service import ReportService
        from app.database.models.research import ReportStatus

        run = MagicMock()
        run.report_status = ReportStatus.COMPLETED
        run.report_path = "/some/path/report.md"
        run.report_generated_at = datetime.now(timezone.utc)

        mock_settings = MagicMock()
        mock_settings.REPORTS_DIR = "./reports"
        with patch("app.reports.service.get_settings", return_value=mock_settings), \
             patch("app.reports.service.os.path.exists", return_value=True):
            service = ReportService()
            mock_db = MagicMock()
            mock_db.query.return_value.filter.return_value.first.return_value = run
            result = service.generate_report(1, mock_db)
            assert result["report_status"] == "completed"

    def test_build_report_path(self):
        """_build_report_path creates correct directory structure."""
        from app.reports.service import ReportService

        mock_settings = MagicMock()
        mock_settings.REPORTS_DIR = os.path.join("tmp", "test-reports")
        with patch("app.reports.service.get_settings", return_value=mock_settings):
            service = ReportService()
            path = service._build_report_path(42, "2026-01-15")
            assert "research-42.md" in path
            assert "2026" in path
            assert "01" in path
            assert "2026-01-15" in path

    def test_build_report_path_prevents_escape(self):
        """_build_report_path rejects path traversal attempts."""
        from app.reports.service import ReportService
        from app.reports.errors import ReportGenerationError

        mock_settings = MagicMock()
        mock_settings.REPORTS_DIR = os.path.join("tmp", "test-reports")
        with patch("app.reports.service.get_settings", return_value=mock_settings):
            service = ReportService()
            # Path structure is {REPORTS_DIR}/{year}/{month}/{date}/research-{id}.md
            # That's 3 levels deep, so we need 3+ ".." to escape above REPORTS_DIR
            traversal = os.path.join("..", "..", "..", "etc", "passwd")
            with pytest.raises(ReportGenerationError, match="path escape"):
                service._build_report_path(1, traversal)


# ============================================
# 6. GitHub Service Tests
# ============================================

class TestGitHubService:
    def _make_service(self, **cfg_overrides):
        """Create a GitHubService with mocked settings."""
        from app.github.service import GitHubService

        ms = MagicMock()
        ms.GITHUB_TOKEN = cfg_overrides.get("GITHUB_TOKEN", "ghp_test")
        ms.GITHUB_OWNER = cfg_overrides.get("GITHUB_OWNER", "test-owner")
        ms.GITHUB_REPO = cfg_overrides.get("GITHUB_REPO", "test-repo")
        with patch("app.github.service.get_settings", return_value=ms):
            return GitHubService()

    def test_is_configured_true(self):
        """is_configured returns True when all GitHub env vars set."""
        service = self._make_service()
        assert service.is_configured() is True

    def test_is_configured_false_missing_token(self):
        """is_configured returns False when token missing."""
        service = self._make_service(GITHUB_TOKEN="")
        assert service.is_configured() is False

    def test_is_configured_false_missing_owner(self):
        """is_configured returns False when owner missing."""
        service = self._make_service(GITHUB_OWNER="")
        assert service.is_configured() is False

    @pytest.mark.asyncio
    async def test_publish_not_configured_raises(self):
        """publish_report raises GitHubConfigurationError when not configured."""
        from app.github.errors import GitHubConfigurationError

        ms = MagicMock()
        ms.GITHUB_TOKEN = ""
        ms.GITHUB_OWNER = ""
        ms.GITHUB_REPO = ""
        with patch("app.github.service.get_settings", return_value=ms):
            from app.github.service import GitHubService
            service = GitHubService()
            with pytest.raises(GitHubConfigurationError):
                await service.publish_report(1, MagicMock())

    @pytest.mark.asyncio
    async def test_publish_no_report_raises(self):
        """publish_report raises when no report file exists."""
        from app.github.errors import GitHubPublicationError

        run = MagicMock()
        run.report_path = None

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = run

        service = self._make_service()
        with pytest.raises(GitHubPublicationError):
            await service.publish_report(1, mock_db)

    @pytest.mark.asyncio
    async def test_publish_idempotent(self):
        """publish_report returns existing publication if already completed."""
        mock_entry = MagicMock()
        mock_entry.branch = "research/2026-01-01"
        mock_entry.file_path = "reports/report.md"
        mock_entry.commit_sha = "abc123"
        mock_entry.commit_url = "https://github.com/commit/abc123"

        run = MagicMock()
        run.report_path = "/some/report.md"
        run.report_status = "completed"

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_entry

        service = self._make_service()
        with patch("app.github.service.os.path.exists", return_value=True), \
             patch("builtins.open", create=True) as mock_open:
            mock_open.return_value.__enter__ = lambda s: s
            mock_open.return_value.__exit__ = MagicMock(return_value=False)
            mock_open.return_value.read.return_value = "x" * 100
            mock_open.return_value.__len__ = lambda self: 100
            result = await service.publish_report(1, mock_db)
            assert result["status"] == "completed"
            assert result["commit_sha"] == "abc123"

    @pytest.mark.asyncio
    async def test_get_publication_status_none(self):
        """get_publication_status returns None when not published."""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None

        service = self._make_service()
        result = await service.get_publication_status(1, mock_db)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_publication_status_found(self):
        """get_publication_status returns metadata when published."""
        mock_entry = MagicMock()
        mock_entry.status.value = "completed"
        mock_entry.branch = "research/2026-01-01"
        mock_entry.file_path = "reports/report.md"
        mock_entry.commit_sha = "abc123"
        mock_entry.commit_url = "https://github.com/commit/abc123"
        mock_entry.error_message = None
        mock_entry.created_at = datetime.now(timezone.utc)

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = mock_entry

        service = self._make_service()
        result = await service.get_publication_status(1, mock_db)
        assert result is not None
        assert result["status"] == "completed"
        assert result["branch"] == "research/2026-01-01"


# ============================================
# 7. AI Status API Endpoint Tests
# ============================================

class TestAIStatusEndpoint:
    def test_ai_status_returns_ok(self, client):
        """GET /api/ai/status returns status info."""
        r = client.get("/api/ai/status")
        assert r.status_code == 200
        d = r.json()
        assert "provider" in d
        assert "configured_key_slots" in d
        assert "available_key_slots" in d
        assert "default_model" in d
        assert d["provider"] == "openrouter"

    def test_ai_models_returns_ok(self, client):
        """GET /api/ai/models returns model mappings."""
        r = client.get("/api/ai/models")
        assert r.status_code == 200
        d = r.json()
        assert "models" in d
        assert isinstance(d["models"], dict)

    def test_ai_models_contains_agents(self, client):
        """GET /api/ai/models contains all 5 agent types."""
        r = client.get("/api/ai/models")
        d = r.json()
        expected_agents = [
            "MarketAnalyst", "CompetitorAnalyst", "IdeaGenerator",
            "TechnicalAnalyst", "ValidationPlanner",
        ]
        for agent in expected_agents:
            assert agent in d["models"]


# ============================================
# 8. Health Endpoint Tests (Phase 6 additions)
# ============================================

class TestHealthEndpoints:
    def test_health_ai(self, client):
        """GET /health/ai returns AI health status."""
        r = client.get("/health/ai")
        assert r.status_code == 200
        d = r.json()
        assert "status" in d
        assert "provider" in d
        assert "configured_keys" in d
        assert d["provider"] == "openrouter"

    def test_health_github(self, client):
        """GET /health/github returns GitHub health status."""
        r = client.get("/health/github")
        assert r.status_code == 200
        d = r.json()
        assert "status" in d
        assert "configured" in d
        assert isinstance(d["configured"], bool)

    def test_health_main(self, client):
        """GET /health returns ok."""
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"


# ============================================
# 9. Report API Route Tests
# ============================================

class TestReportRoutes:
    def test_get_report_not_found(self, client):
        """GET /api/research/99999/report returns 404."""
        r = client.get("/api/research/99999/report")
        assert r.status_code == 404

    def test_post_report_not_found(self, client):
        """POST /api/research/99999/report returns 404."""
        r = client.post("/api/research/99999/report")
        assert r.status_code == 404

    def test_get_report_no_content_yet(self, client, db):
        """GET report for run without report returns empty content."""
        run = _create_completed_research(db)
        r = client.get(f"/api/research/{run.id}/report")
        assert r.status_code == 200
        d = r.json()
        assert d["research_id"] == run.id
        assert d["content"] is None


# ============================================
# 10. GitHub API Route Tests
# ============================================

class TestGitHubRoutes:
    def test_get_github_status_not_published(self, client, db):
        """GET github status returns not_published when no entry."""
        run = _create_completed_research(db)
        r = client.get(f"/api/research/{run.id}/github")
        assert r.status_code == 200
        d = r.json()
        assert d["status"] == "not_published"

    def test_get_github_status_not_found(self, client):
        """GET github status returns 404 for missing research."""
        r = client.get("/api/research/99999/github")
        assert r.status_code == 404

    def test_post_github_not_configured(self, client, db):
        """POST github returns 503 when GitHub not configured."""
        run = _create_completed_research(db)
        r = client.post(f"/api/research/{run.id}/github")
        assert r.status_code == 503
        d = r.json()
        assert d["detail"]["code"] == "GITHUB_CONFIGURATION_ERROR"

    def test_post_github_not_found(self, client):
        """POST github returns 404 for missing research."""
        r = client.post("/api/research/99999/github")
        assert r.status_code == 404


# ============================================
# 11. Report Generation E2E Test
# ============================================

class TestReportGenerationE2E:
    def test_generate_report_e2e(self, client, db):
        """End-to-end report generation from API."""
        run = _create_completed_research(db)

        with patch("app.api.routes.report.ReportService") as MockService:
            mock_svc = MagicMock()
            mock_svc.generate_report.return_value = {
                "research_id": run.id,
                "report_status": "completed",
                "report_path": os.path.join("tmp", "test-report.md"),
                "report_generated_at": datetime.now(timezone.utc).isoformat(),
            }
            MockService.return_value = mock_svc

            r = client.post(f"/api/research/{run.id}/report")
            assert r.status_code == 200
            d = r.json()
            assert d["report_status"] == "completed"
            assert "test-report.md" in d["report_path"]

    def test_get_report_content_e2e(self, client, db):
        """End-to-end report content retrieval from API."""
        run = _create_completed_research(db)

        with patch("app.api.routes.report.ReportService") as MockService:
            mock_svc = MagicMock()
            mock_svc.get_report_content.return_value = {
                "research_id": run.id,
                "report_status": "completed",
                "content": "# Report Content\n\nTest report.",
                "report_path": os.path.join("tmp", "test-report.md"),
            }
            MockService.return_value = mock_svc

            r = client.get(f"/api/research/{run.id}/report")
            assert r.status_code == 200
            d = r.json()
            assert "Report Content" in d["content"]


# ============================================
# 12. GitHub Publication E2E Test
# ============================================

class TestGitHubPublicationE2E:
    def test_publish_github_e2e(self, client, db):
        """End-to-end GitHub publication from API."""
        run = _create_completed_research(db)

        with patch("app.api.routes.github.GitHubService") as MockService:
            mock_svc = MagicMock()
            mock_svc.publish_report = AsyncMock(return_value={
                "research_id": run.id,
                "status": "completed",
                "branch": "research/2026-01-01",
                "file_path": "reports/report.md",
                "commit_sha": "abc123",
                "commit_url": "https://github.com/commit/abc123",
            })
            MockService.return_value = mock_svc

            r = client.post(f"/api/research/{run.id}/github")
            assert r.status_code == 200
            d = r.json()
            assert d["status"] == "completed"
            assert d["commit_sha"] == "abc123"

    def test_get_github_status_e2e(self, client, db):
        """End-to-end GitHub status from API."""
        run = _create_completed_research(db)

        with patch("app.api.routes.github.GitHubService") as MockService:
            mock_svc = MagicMock()
            mock_svc.get_publication_status = AsyncMock(return_value={
                "research_id": run.id,
                "status": "completed",
                "branch": "research/2026-01-01",
                "file_path": "reports/report.md",
                "commit_sha": "abc123",
                "commit_url": "https://github.com/commit/abc123",
                "error": None,
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
            MockService.return_value = mock_svc

            r = client.get(f"/api/research/{run.id}/github")
            assert r.status_code == 200
            d = r.json()
            assert d["status"] == "completed"


# ============================================
# 13. AI Response Schema Tests
# ============================================

class TestAIResponseSchema:
    def test_ai_response_with_key_slot(self):
        """AIResponse includes key_slot field."""
        from app.ai.schemas import AIResponse, AIUsage

        resp = AIResponse(
            content="Hello",
            usage=AIUsage(input_tokens=10, output_tokens=20),
            key_slot="05",
        )
        assert resp.key_slot == "05"
        assert resp.content == "Hello"

    def test_ai_response_default_key_slot(self):
        """AIResponse key_slot defaults to None."""
        from app.ai.schemas import AIResponse

        resp = AIResponse(content="Hello")
        assert resp.key_slot is None

    def test_ai_usage_defaults(self):
        """AIUsage defaults to None for token counts."""
        from app.ai.schemas import AIUsage

        usage = AIUsage()
        assert usage.input_tokens is None
        assert usage.output_tokens is None


# ============================================
# 14. Error Class Hierarchy Tests
# ============================================

class TestErrorHierarchy:
    def test_report_errors(self):
        """Report errors are proper subclasses."""
        from app.reports.errors import ReportError, ReportGenerationError, ReportNotFoundError

        assert issubclass(ReportGenerationError, ReportError)
        assert issubclass(ReportNotFoundError, ReportError)

    def test_github_errors(self):
        """GitHub errors are proper subclasses."""
        from app.github.errors import (
            GitHubError, GitHubConfigurationError, GitHubAuthenticationError,
            GitHubRepositoryNotFoundError, GitHubPublicationError,
        )

        assert issubclass(GitHubConfigurationError, GitHubError)
        assert issubclass(GitHubAuthenticationError, GitHubError)
        assert issubclass(GitHubRepositoryNotFoundError, GitHubError)
        assert issubclass(GitHubPublicationError, GitHubError)

    def test_ai_errors(self):
        """AI errors include AllKeysExhausted."""
        from app.ai.errors import AIError, AIAllKeysExhausted

        assert issubclass(AIAllKeysExhausted, AIError)


# ============================================
# 15. Database Model Tests (Phase 6 columns)
# ============================================

class TestDatabaseModelsPhase6:
    def test_research_run_has_report_fields(self, db):
        """ResearchRun has Phase 6 report fields."""
        from app.database.models.research import ResearchRun, ResearchStatus, ReportStatus

        run = ResearchRun(
            topic="Test",
            status=ResearchStatus.COMPLETED,
            report_status=ReportStatus.COMPLETED,
            report_generated_at=datetime.now(timezone.utc),
            report_error=None,
        )
        db.add(run)
        db.commit()
        db.refresh(run)

        assert run.report_status == ReportStatus.COMPLETED
        assert run.report_generated_at is not None
        assert run.report_error is None

    def test_agent_run_has_key_slot(self, db):
        """AgentRun has provider_key_slot column."""
        from app.database.models.agent_run import AgentRun, AgentRunStatus
        from app.database.models.research import ResearchRun, ResearchStatus

        run = ResearchRun(topic="T", status=ResearchStatus.COMPLETED)
        db.add(run)
        db.flush()

        ar = AgentRun(
            research_run_id=run.id,
            agent_name="MarketAnalyst",
            status=AgentRunStatus.COMPLETED,
            model="test-model",
            provider_key_slot="03",
        )
        db.add(ar)
        db.commit()
        db.refresh(ar)

        assert ar.provider_key_slot == "03"

    def test_research_github_model(self, db):
        """ResearchGitHub model creates and persists."""
        from app.database.models.github import ResearchGitHub, GitHubPublishStatus
        from app.database.models.research import ResearchRun, ResearchStatus

        run = ResearchRun(topic="T", status=ResearchStatus.COMPLETED)
        db.add(run)
        db.flush()

        gh = ResearchGitHub(
            research_run_id=run.id,
            provider="github",
            owner="test-owner",
            repository="test-repo",
            branch="research/2026-01-01",
            file_path="reports/report.md",
            status=GitHubPublishStatus.COMPLETED,
            commit_sha="abc123def",
        )
        db.add(gh)
        db.commit()
        db.refresh(gh)

        assert gh.owner == "test-owner"
        assert gh.branch == "research/2026-01-01"
        assert gh.commit_sha == "abc123def"
        assert gh.status == GitHubPublishStatus.COMPLETED

    def test_research_github_cascade(self, db):
        """Deleting ResearchRun cascades to ResearchGitHub."""
        from app.database.models.github import ResearchGitHub, GitHubPublishStatus
        from app.database.models.research import ResearchRun, ResearchStatus

        run = ResearchRun(topic="T", status=ResearchStatus.COMPLETED)
        db.add(run)
        db.flush()

        gh = ResearchGitHub(
            research_run_id=run.id,
            provider="github",
            owner="test-owner",
            repository="test-repo",
            branch="research/2026-01-01",
            file_path="reports/report.md",
            status=GitHubPublishStatus.COMPLETED,
        )
        db.add(gh)
        db.commit()

        db.delete(run)
        db.commit()

        remaining = db.query(ResearchGitHub).all()
        assert len(remaining) == 0

    def test_report_status_enum_values(self):
        """ReportStatus enum has expected values."""
        from app.database.models.research import ReportStatus

        assert ReportStatus.PENDING.value == "pending"
        assert ReportStatus.GENERATING.value == "generating"
        assert ReportStatus.COMPLETED.value == "completed"
        assert ReportStatus.FAILED.value == "failed"

    def test_github_publish_status_enum_values(self):
        """GitHubPublishStatus enum has expected values."""
        from app.database.models.github import GitHubPublishStatus

        assert GitHubPublishStatus.PENDING.value == "pending"
        assert GitHubPublishStatus.PUBLISHING.value == "publishing"
        assert GitHubPublishStatus.COMPLETED.value == "completed"
        assert GitHubPublishStatus.FAILED.value == "failed"


# ============================================
# 16. Key Pool Integration with Provider
# ============================================

class TestKeyPoolProviderIntegration:
    def test_provider_uses_key_pool(self):
        """OpenRouterProvider uses key pool for key selection."""
        from app.ai.provider import OpenRouterProvider

        with patch("app.ai.key_pool.get_settings") as mock_kp_settings, \
             patch("app.ai.model_registry.get_settings") as mock_mr_settings, \
             patch("app.ai.client.OpenRouterClient") as MockClient:

            mock_kp_settings.return_value.get_api_keys.return_value = [
                ("01", "key-01"),
                ("02", "key-02"),
            ]
            mock_mr_settings.return_value = MagicMock()
            mock_mr_settings.return_value.OPENROUTER_MODEL = "test-model"
            MockClient.return_value = MagicMock()

            provider = OpenRouterProvider()
            assert provider._key_pool.configured_count == 2

    def test_provider_resolve_model_with_agent(self):
        """_resolve_model returns agent-specific model."""
        from app.ai.provider import OpenRouterProvider

        with patch("app.ai.key_pool.get_settings") as mock_kp_settings, \
             patch("app.ai.model_registry.get_settings") as mock_mr_settings, \
             patch("app.ai.client.OpenRouterClient") as MockClient:

            mock_kp_settings.return_value.get_api_keys.return_value = [("01", "k")]
            mock_mr_settings.return_value = MagicMock()
            mock_mr_settings.return_value.OPENROUTER_MODEL = "default-m"
            mock_mr_settings.return_value.MODEL_MARKET_ANALYST = "market-m"
            MockClient.return_value = MagicMock()

            provider = OpenRouterProvider()
            model = provider._resolve_model(None, "MarketAnalyst")
            assert model == "market-m"

    def test_provider_resolve_model_override(self):
        """_resolve_model returns explicit model when provided."""
        from app.ai.provider import OpenRouterProvider

        with patch("app.ai.key_pool.get_settings") as mock_kp_settings, \
             patch("app.ai.model_registry.get_settings") as mock_mr_settings, \
             patch("app.ai.client.OpenRouterClient") as MockClient:

            mock_kp_settings.return_value.get_api_keys.return_value = [("01", "k")]
            mock_mr_settings.return_value = MagicMock()
            mock_mr_settings.return_value.OPENROUTER_MODEL = "default-m"
            MockClient.return_value = MagicMock()

            provider = OpenRouterProvider()
            model = provider._resolve_model("explicit-model", "MarketAnalyst")
            assert model == "explicit-model"

    def test_provider_model_property(self):
        """provider.model returns default model or 'unknown'."""
        from app.ai.provider import OpenRouterProvider

        with patch("app.ai.key_pool.get_settings") as mock_kp_settings, \
             patch("app.ai.model_registry.get_settings") as mock_mr_settings, \
             patch("app.ai.client.OpenRouterClient") as MockClient:

            mock_kp_settings.return_value.get_api_keys.return_value = [("01", "k")]
            mock_mr_settings.return_value = MagicMock()
            mock_mr_settings.return_value.OPENROUTER_MODEL = "the-model"
            MockClient.return_value = MagicMock()

            provider = OpenRouterProvider()
            assert provider.model == "the-model"


# ============================================
# 17. Report Path Security Tests
# ============================================

class TestReportPathSecurity:
    def test_path_stays_within_reports_dir(self):
        """Report path cannot escape REPORTS_DIR via date string."""
        from app.reports.service import ReportService
        from app.reports.errors import ReportGenerationError

        reports_dir = os.path.join("safe", "reports")
        mock_settings = MagicMock()
        mock_settings.REPORTS_DIR = reports_dir
        with patch("app.reports.service.get_settings", return_value=mock_settings):
            service = ReportService()

            # Normal path should work and stay within reports_dir
            path = service._build_report_path(1, "2026-01-01")
            normalized = os.path.normpath(path)
            reports_normalized = os.path.normpath(reports_dir)
            assert normalized.startswith(reports_normalized)

            # Path traversal attempt — 3 levels: year/month/date_str
            traversal = os.path.join("..", "..", "..", "etc", "passwd")
            with pytest.raises(ReportGenerationError, match="path escape"):
                service._build_report_path(1, traversal)

    def test_get_status_never_leaks_keys(self):
        """get_status dict never contains actual API key values."""
        from app.ai.key_pool import OpenRouterKeyPool

        with patch("app.ai.key_pool.get_settings") as mock_settings:
            mock_settings.return_value.get_api_keys.return_value = [
                ("01", "sk-or-v1-abc123supersecret"),
                ("02", "sk-or-v1-def456topsecret"),
            ]
            pool = OpenRouterKeyPool()
            status = pool.get_status()
            status_str = json.dumps(status)
            assert "sk-or-v1" not in status_str
            assert "supersecret" not in status_str
            assert "topsecret" not in status_str


# ============================================
# 18. 11-Key Architecture Tests
# ============================================

class TestKeyArchitecture:
    def test_config_has_12_key_slots(self):
        """Settings has 12 key slot attributes (01-12)."""
        from app.core.config import Settings

        s = Settings(_env_file=None)
        for i in range(1, 13):
            slot = f"{i:02d}"
            attr = f"OPENROUTER_API_KEY_{slot}"
            assert hasattr(s, attr), f"Missing attribute {attr}"

    def test_get_api_keys_returns_tuple_format(self):
        """get_api_keys returns list of (slot, key) tuples."""
        s = _make_settings(
            OPENROUTER_API_KEY_01="k1",
            OPENROUTER_API_KEY_05="k5",
            OPENROUTER_API_KEY_12="k12",
        )
        keys = s.get_api_keys()
        assert len(keys) == 3
        assert keys[0] == ("01", "k1")
        assert keys[1] == ("05", "k5")
        assert keys[2] == ("12", "k12")

    def test_all_free_models_list_has_20(self):
        """ALL_FREE_MODELS list contains 20 models."""
        from app.ai.model_registry import ALL_FREE_MODELS

        assert len(ALL_FREE_MODELS) == 20

    def test_all_free_models_are_unique(self):
        """ALL_FREE_MODELS has no duplicates."""
        from app.ai.model_registry import ALL_FREE_MODELS

        assert len(ALL_FREE_MODELS) == len(set(ALL_FREE_MODELS))

    def test_model_registry_maps_all_5_agents(self):
        """Model registry internal map covers all 5 agents."""
        from app.ai.model_registry import _AGENT_MODEL_VARS

        expected = {"MarketAnalyst", "CompetitorAnalyst", "IdeaGenerator",
                    "TechnicalAnalyst", "ValidationPlanner"}
        assert set(_AGENT_MODEL_VARS.keys()) == expected
