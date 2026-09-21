"""Tests for Phase 3 — AI engine and research endpoints."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.database.base import Base


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
    from app.database.database import get_db
    from app.main import app as _app

    engine = _make_test_engine()
    TestSession = sessionmaker(bind=engine)

    def _override():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    _app.dependency_overrides[get_db] = _override
    yield
    _app.dependency_overrides.clear()
    engine.dispose()


@pytest.fixture
def client():
    from app.main import app as _app
    with TestClient(_app) as c:
        yield c


def _make_ai_response(content: dict, model: str = "test-model") -> dict:
    return {
        "choices": [{"message": {"content": json.dumps(content)}}],
        "model": model,
        "usage": {"prompt_tokens": 100, "completion_tokens": 200},
    }


VALID_RESULT = {
    "topic": "SaaS for small businesses",
    "summary": "This is a research summary.",
    "findings": ["Finding 1", "Finding 2"],
    "problems": ["Problem 1"],
    "opportunities": ["Opportunity 1"],
    "sources": [{"title": "Source 1", "url": "https://example.com", "source_type": "web"}],
    "uncertainties": ["Uncertainty 1"],
}


# --- Schema Tests ---

class TestSchemas:
    def test_valid_result(self):
        from app.ai.schemas import ResearchResult
        r = ResearchResult(**VALID_RESULT)
        assert r.topic == "SaaS for small businesses"
        assert len(r.findings) == 2

    def test_empty_topic_rejected(self):
        from app.ai.schemas import ResearchResult
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            ResearchResult(topic="", summary="test")

    def test_optional_fields_default(self):
        from app.ai.schemas import ResearchResult
        r = ResearchResult(topic="t", summary="s")
        assert r.findings == []
        assert r.sources == []

    def test_valid_source(self):
        from app.ai.schemas import SourceInfo
        s = SourceInfo(title="T", url="https://x.com", source_type="web")
        assert s.title == "T"

    def test_source_empty_title_rejected(self):
        from app.ai.schemas import SourceInfo
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            SourceInfo(title="", source_type="web")


# --- JSON Parsing Tests ---

class TestJsonParsing:
    def test_raw_json(self):
        from app.ai.provider import _extract_json_from_response
        d = {"k": "v"}
        assert _extract_json_from_response(json.dumps(d)) == d

    def test_markdown_fences(self):
        from app.ai.provider import _extract_json_from_response
        d = {"k": "v"}
        assert _extract_json_from_response(f"```json\n{json.dumps(d)}\n```") == d

    def test_fences_no_lang(self):
        from app.ai.provider import _extract_json_from_response
        d = {"k": "v"}
        assert _extract_json_from_response(f"```\n{json.dumps(d)}\n```") == d

    def test_surrounding_text(self):
        from app.ai.provider import _extract_json_from_response
        d = {"k": "v"}
        assert _extract_json_from_response(f"Here:\n{json.dumps(d)}\nDone.") == d

    def test_invalid_raises(self):
        from app.ai.provider import _extract_json_from_response
        from app.ai.errors import AIResponseParsingError
        with pytest.raises(AIResponseParsingError):
            _extract_json_from_response("not json at all")

    def test_empty_raises(self):
        from app.ai.provider import _extract_json_from_response
        from app.ai.errors import AIResponseParsingError
        with pytest.raises(AIResponseParsingError):
            _extract_json_from_response("")


# --- Error Tests ---

class TestErrors:
    def test_hierarchy(self):
        from app.ai.errors import (
            AIConfigurationError, AIProviderError, AIResponseParsingError,
            AIResponseValidationError, AIRateLimitError, AITimeoutError,
        )
        assert issubclass(AIConfigurationError, Exception)
        assert issubclass(AIRateLimitError, AIProviderError)
        assert issubclass(AITimeoutError, AIProviderError)

    def test_status_code(self):
        from app.ai.errors import AIProviderError
        assert AIProviderError("t", status_code=500).status_code == 500


# --- Config Tests ---

class TestConfig:
    def test_missing_key(self):
        from app.ai.errors import AIConfigurationError
        with patch("app.ai.client.get_settings") as m:
            m.return_value = MagicMock(OPENROUTER_API_KEY="", OPENROUTER_MODEL="m", OPENROUTER_BASE_URL="u")
            from app.ai.client import OpenRouterClient
            with pytest.raises(AIConfigurationError):
                OpenRouterClient()

    def test_missing_model(self):
        from app.ai.errors import AIConfigurationError
        with patch("app.ai.client.get_settings") as m:
            m.return_value = MagicMock(OPENROUTER_API_KEY="k", OPENROUTER_MODEL="", OPENROUTER_BASE_URL="u")
            from app.ai.client import OpenRouterClient
            with pytest.raises(AIConfigurationError):
                OpenRouterClient()


# --- Client Tests ---

class TestClient:
    @pytest.fixture
    def ms(self):
        with patch("app.ai.client.get_settings") as m:
            m.return_value = MagicMock(OPENROUTER_API_KEY="k", OPENROUTER_MODEL="m", OPENROUTER_BASE_URL="u")
            yield m

    @pytest.mark.asyncio
    async def test_success(self, ms):
        from app.ai.client import OpenRouterClient
        r = MagicMock(); r.status_code = 200; r.json.return_value = {"choices": [{"message": {"content": "hi"}}], "model": "m"}
        with patch("app.ai.client.httpx.AsyncClient") as h:
            h.return_value.__aenter__ = AsyncMock(return_value=h)
            h.return_value.__aexit__ = AsyncMock(return_value=False)
            h.post = AsyncMock(return_value=r)
            assert "choices" in await OpenRouterClient().chat_completion([{"role": "user", "content": "t"}])

    @pytest.mark.asyncio
    async def test_rate_limit(self, ms):
        from app.ai.client import OpenRouterClient
        from app.ai.errors import AIRateLimitError
        r = MagicMock(); r.status_code = 429
        with patch("app.ai.client.httpx.AsyncClient") as h:
            h.return_value.__aenter__ = AsyncMock(return_value=h)
            h.return_value.__aexit__ = AsyncMock(return_value=False)
            h.post = AsyncMock(return_value=r)
            with pytest.raises(AIRateLimitError):
                await OpenRouterClient().chat_completion([{"role": "user", "content": "t"}])

    @pytest.mark.asyncio
    async def test_auth_error(self, ms):
        from app.ai.client import OpenRouterClient
        from app.ai.errors import AIProviderError
        r = MagicMock(); r.status_code = 401
        with patch("app.ai.client.httpx.AsyncClient") as h:
            h.return_value.__aenter__ = AsyncMock(return_value=h)
            h.return_value.__aexit__ = AsyncMock(return_value=False)
            h.post = AsyncMock(return_value=r)
            with pytest.raises(AIProviderError) as e:
                await OpenRouterClient().chat_completion([{"role": "user", "content": "t"}])
            assert e.value.status_code == 401

    @pytest.mark.asyncio
    async def test_server_error(self, ms):
        from app.ai.client import OpenRouterClient
        from app.ai.errors import AIProviderError
        r = MagicMock(); r.status_code = 500
        with patch("app.ai.client.httpx.AsyncClient") as h:
            h.return_value.__aenter__ = AsyncMock(return_value=h)
            h.return_value.__aexit__ = AsyncMock(return_value=False)
            h.post = AsyncMock(return_value=r)
            with pytest.raises(AIProviderError):
                await OpenRouterClient().chat_completion([{"role": "user", "content": "t"}])

    @pytest.mark.asyncio
    async def test_timeout(self, ms):
        import httpx
        from app.ai.client import OpenRouterClient
        from app.ai.errors import AITimeoutError
        with patch("app.ai.client.httpx.AsyncClient") as h:
            h.return_value.__aenter__ = AsyncMock(return_value=h)
            h.return_value.__aexit__ = AsyncMock(return_value=False)
            h.post = AsyncMock(side_effect=httpx.TimeoutException("t"))
            with pytest.raises(AITimeoutError):
                await OpenRouterClient().chat_completion([{"role": "user", "content": "t"}])


# --- Provider Tests ---

class TestProvider:
    @pytest.mark.asyncio
    async def test_valid(self):
        from app.ai.provider import OpenRouterProvider
        with patch("app.ai.client.get_settings") as m:
            m.return_value = MagicMock(OPENROUTER_API_KEY="k", OPENROUTER_MODEL="m", OPENROUTER_BASE_URL="u")
            with patch("app.ai.client.httpx.AsyncClient") as h:
                r = MagicMock(); r.status_code = 200; r.json.return_value = _make_ai_response(VALID_RESULT)
                h.return_value.__aenter__ = AsyncMock(return_value=h)
                h.return_value.__aexit__ = AsyncMock(return_value=False)
                h.post = AsyncMock(return_value=r)
                p = OpenRouterProvider()
                result = await p.generate(prompt="t")
                assert result.usage.input_tokens == 100

    @pytest.mark.asyncio
    async def test_malformed_json(self):
        """AI returns unparseable content → provider should raise AIResponseParsingError."""
        from app.ai.provider import OpenRouterProvider
        from app.ai.errors import AIResponseParsingError
        with patch("app.ai.client.get_settings") as m:
            m.return_value = MagicMock(OPENROUTER_API_KEY="k", OPENROUTER_MODEL="m", OPENROUTER_BASE_URL="u")
            with patch("app.ai.client.httpx.AsyncClient") as h:
                r = MagicMock(); r.status_code = 200
                r.json.return_value = {
                    "choices": [{"message": {"content": "no json here just plain text"}}],
                    "model": "m",
                }
                h.return_value.__aenter__ = AsyncMock(return_value=h)
                h.return_value.__aexit__ = AsyncMock(return_value=False)
                h.post = AsyncMock(return_value=r)
                with pytest.raises(AIResponseParsingError):
                    await OpenRouterProvider().generate(prompt="t")


# --- Agent Tests ---

class TestAgent:
    @pytest.fixture
    def db(self):
        engine = _make_test_engine()
        S = sessionmaker(bind=engine)
        session = S()
        yield session
        session.close()
        engine.dispose()

    @pytest.mark.asyncio
    async def test_success(self, db):
        from app.ai.research_agent import ResearchAgent
        from app.ai.schemas import AIResponse, AIUsage
        from app.database.models.research import ResearchRun, ResearchStatus

        run = ResearchRun(topic="T")
        db.add(run); db.flush()

        mock = MagicMock(); mock.model = "m"
        mock.generate = AsyncMock(return_value=AIResponse(
            content=json.dumps(VALID_RESULT), model="m",
            usage=AIUsage(input_tokens=50, output_tokens=100),
        ))

        result = await ResearchAgent(provider=mock).run(run, db)
        assert result.topic == "SaaS for small businesses"
        assert run.status == ResearchStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_failure(self, db):
        from app.ai.research_agent import ResearchAgent
        from app.ai.errors import AIProviderError
        from app.database.models.research import ResearchRun, ResearchStatus

        run = ResearchRun(topic="T")
        db.add(run); db.flush()

        mock = MagicMock(); mock.model = "m"
        mock.generate = AsyncMock(side_effect=AIProviderError("err"))

        with pytest.raises(AIProviderError):
            await ResearchAgent(provider=mock).run(run, db)
        assert run.status == ResearchStatus.FAILED

    @pytest.mark.asyncio
    async def test_tokens(self, db):
        from app.ai.research_agent import ResearchAgent
        from app.ai.schemas import AIResponse, AIUsage
        from app.database.models.research import ResearchRun
        from app.database.models.agent_run import AgentRun, AgentRunStatus

        run = ResearchRun(topic="T")
        db.add(run); db.flush()

        mock = MagicMock(); mock.model = "m"
        mock.generate = AsyncMock(return_value=AIResponse(
            content=json.dumps(VALID_RESULT), model="m",
            usage=AIUsage(input_tokens=75, output_tokens=150),
        ))

        await ResearchAgent(provider=mock).run(run, db)
        ar = db.query(AgentRun).filter_by(research_run_id=run.id).one()
        assert ar.input_tokens == 75
        assert ar.output_tokens == 150
        assert ar.status == AgentRunStatus.COMPLETED


# --- Endpoint Tests ---

class TestEndpoints:
    def _mock_agent(self, result=None, error=None):
        m = MagicMock()
        if error:
            m.run = AsyncMock(side_effect=error)
        else:
            from app.ai.schemas import ResearchResult
            m.run = AsyncMock(return_value=ResearchResult(**(result or VALID_RESULT)))
        return m

    def test_create_success(self, client):
        with patch("app.api.routes.research.ResearchAgent") as M:
            M.return_value = self._mock_agent()
            r = client.post("/api/research", json={"topic": "SaaS opportunities for small businesses"})
            assert r.status_code == 201
            d = r.json()
            assert d["status"] == "completed"
            assert d["result"]["topic"] == "SaaS for small businesses"

    def test_empty_topic(self, client):
        assert client.post("/api/research", json={"topic": ""}).status_code == 422

    def test_short_topic(self, client):
        assert client.post("/api/research", json={"topic": "ab"}).status_code == 422

    def test_missing_topic(self, client):
        assert client.post("/api/research", json={}).status_code == 422

    def test_long_topic(self, client):
        assert client.post("/api/research", json={"topic": "x" * 501}).status_code == 422

    def test_ai_error(self, client):
        from app.ai.errors import AIProviderError
        with patch("app.api.routes.research.ResearchAgent") as M:
            M.return_value = self._mock_agent(error=AIProviderError("down"))
            r = client.post("/api/research", json={"topic": "Test error topic"})
            assert r.status_code == 503
            assert r.json()["detail"]["code"] == "AI_PROVIDER_ERROR"

    def test_config_error(self, client):
        from app.ai.errors import AIConfigurationError
        with patch("app.api.routes.research.ResearchAgent") as M:
            M.return_value = self._mock_agent(error=AIConfigurationError("no key"))
            r = client.post("/api/research", json={"topic": "Test config topic"})
            assert r.status_code == 503
            assert r.json()["detail"]["code"] == "AI_CONFIGURATION_ERROR"

    def test_list_empty(self, client):
        r = client.get("/api/research")
        assert r.status_code == 200
        assert r.json()["items"] == []

    def test_list_with_data(self, client):
        with patch("app.api.routes.research.ResearchAgent") as M:
            M.return_value = self._mock_agent()
            client.post("/api/research", json={"topic": "List topic one"})
            client.post("/api/research", json={"topic": "List topic two"})
        r = client.get("/api/research")
        assert r.json()["total"] == 2

    def test_pagination(self, client):
        with patch("app.api.routes.research.ResearchAgent") as M:
            M.return_value = self._mock_agent()
            for i in range(5):
                client.post("/api/research", json={"topic": f"Page topic {i}"})
        r = client.get("/api/research?page=1&page_size=2")
        d = r.json()
        assert d["total"] == 5
        assert len(d["items"]) == 2

    def test_get_not_found(self, client):
        assert client.get("/api/research/99999").status_code == 404

    def test_get_found(self, client):
        with patch("app.api.routes.research.ResearchAgent") as M:
            M.return_value = self._mock_agent()
            rid = client.post("/api/research", json={"topic": "Get topic"}).json()["id"]
        r = client.get(f"/api/research/{rid}")
        assert r.status_code == 200
        assert r.json()["topic"] == "Get topic"


# --- Health (unchanged) ---

def test_root(client):
    r = client.get("/")
    assert r.status_code == 200
    assert r.json()["status"] == "running"


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}
