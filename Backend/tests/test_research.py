"""Tests for Phase 4 — Real web research, source collection, and pipeline."""

import json
from datetime import datetime, timezone
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
    return TestClient(_app)


# --- Search Result Schema Tests ---

class TestSearchResultSchema:
    def test_valid_result(self):
        from app.research.schemas import SearchResult
        r = SearchResult(
            title="Test Title",
            url="https://example.com/article",
            snippet="A snippet",
            source_domain="example.com",
            rank=1,
        )
        assert r.title == "Test Title"
        assert r.rank == 1

    def test_invalid_url_rejected(self):
        from app.research.schemas import SearchResult
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            SearchResult(title="T", url="not-a-url", rank=1)

    def test_ftp_url_rejected(self):
        from app.research.schemas import SearchResult
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            SearchResult(title="T", url="ftp://example.com", rank=1)

    def test_empty_title_rejected(self):
        from app.research.schemas import SearchResult
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            SearchResult(title="", url="https://example.com", rank=1)

    def test_optional_fields(self):
        from app.research.schemas import SearchResult
        r = SearchResult(title="T", url="https://example.com")
        assert r.published_at is None
        assert r.rank == 0


# --- WebDocument Schema Tests ---

class TestWebDocumentSchema:
    def test_default_status(self):
        from app.research.schemas import WebDocument
        d = WebDocument(url="https://example.com")
        assert d.status == "success"
        assert d.word_count == 0

    def test_failed_status(self):
        from app.research.schemas import WebDocument
        d = WebDocument(url="https://example.com", status="failed", error="timeout")
        assert d.status == "failed"
        assert d.error == "timeout"


# --- URL Normalization Tests ---

class TestUrlNormalization:
    def test_trailing_slash_removed(self):
        from app.research.normalizer import normalize_url
        url = normalize_url("https://example.com/page/")
        assert url == "https://example.com/page"

    def test_root_slash_preserved(self):
        from app.research.normalizer import normalize_url
        # Root path "/" is preserved (not stripped to empty path)
        url = normalize_url("https://example.com/")
        assert url == "https://example.com/"

    def test_tracking_params_removed(self):
        from app.research.normalizer import normalize_url
        url = normalize_url("https://example.com/page?utm_source=twitter&id=123")
        assert "utm_source" not in url
        assert "id=123" in url

    def test_fragment_removed(self):
        from app.research.normalizer import normalize_url
        url = normalize_url("https://example.com/page#section")
        assert "#" not in url

    def test_scheme_lowered(self):
        from app.research.normalizer import normalize_url
        url = normalize_url("HTTPS://example.com/page")
        assert url.startswith("https://")

    def test_host_lowered(self):
        from app.research.normalizer import normalize_url
        url = normalize_url("https://EXAMPLE.COM/page")
        assert "example.com" in url

    def test_deduplication(self):
        from app.research.normalizer import deduplicate_urls
        urls = [
            "https://example.com/page/",
            "https://example.com/page",
            "https://other.com/page",
        ]
        result = deduplicate_urls(urls)
        assert len(result) == 2

    def test_extract_domain(self):
        from app.research.normalizer import extract_domain
        assert extract_domain("https://example.com/path") == "example.com"
        assert extract_domain("https://sub.example.com") == "sub.example.com"


# --- Source Quality Tests ---

class TestSourceQuality:
    def test_official_gov(self):
        from app.research.quality import classify_source
        from app.research.schemas import SourceQuality
        assert classify_source("https://example.gov/report") == SourceQuality.OFFICIAL

    def test_official_github(self):
        from app.research.quality import classify_source
        from app.research.schemas import SourceQuality
        assert classify_source("https://github.com/user/repo") == SourceQuality.OFFICIAL

    def test_news(self):
        from app.research.quality import classify_source
        from app.research.schemas import SourceQuality
        assert classify_source("https://techcrunch.com/article") == SourceQuality.NEWS

    def test_documentation(self):
        from app.research.quality import classify_source
        from app.research.schemas import SourceQuality
        # docs.python.org is classified as documentation (checked before generic .org TLD)
        assert classify_source("https://docs.python.org/3/library/") == SourceQuality.DOCUMENTATION
        assert classify_source("https://developer.mozilla.org/docs/Web") == SourceQuality.DOCUMENTATION

    def test_community(self):
        from app.research.quality import classify_source
        from app.research.schemas import SourceQuality
        assert classify_source("https://reddit.com/r/programming") == SourceQuality.COMMUNITY

    def test_unknown(self):
        from app.research.quality import classify_source
        from app.research.schemas import SourceQuality
        assert classify_source("https://random-site.xyz/page") == SourceQuality.UNKNOWN


# --- Content Extraction Tests ---

class TestContentExtraction:
    @patch("app.research.extractor.httpx.Client")
    def test_successful_extraction(self, mock_client_cls):
        from app.research.extractor import extract_content

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/html"}
        mock_response.content = b"<html><head><title>Test Page</title></head><body><p>Hello world</p></body></html>"
        mock_response.text = "<html><head><title>Test Page</title></head><body><p>Hello world</p></body></html>"
        mock_response.raise_for_status = MagicMock()

        mock_instance = MagicMock()
        mock_instance.get.return_value = mock_response
        mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_instance)
        mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)

        doc = extract_content("https://example.com/page")
        assert doc.status == "success"
        assert doc.title == "Test Page"
        assert "Hello world" in doc.text
        assert doc.word_count > 0

    def test_private_ip_blocked(self):
        from app.research.extractor import extract_content
        doc = extract_content("http://127.0.0.1/secret")
        assert doc.status == "skipped"
        assert "private" in doc.error.lower() or "blocked" in doc.error.lower()

    def test_metadata_endpoint_blocked(self):
        from app.research.extractor import extract_content
        doc = extract_content("http://169.254.169.254/metadata")
        assert doc.status == "skipped"

    def test_ftp_scheme_blocked(self):
        from app.research.extractor import extract_content
        doc = extract_content("ftp://example.com/file")
        assert doc.status == "skipped"

    def test_localhost_blocked(self):
        from app.research.extractor import extract_content
        doc = extract_content("http://localhost:8000/admin")
        assert doc.status == "skipped"

    @patch("app.research.extractor.httpx.Client")
    def test_timeout_handled(self, mock_client_cls):
        import httpx
        from app.research.extractor import extract_content

        mock_instance = MagicMock()
        mock_instance.get.side_effect = httpx.TimeoutException("timeout")
        mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_instance)
        mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)

        doc = extract_content("https://example.com/slow")
        assert doc.status == "failed"
        assert "timed out" in doc.error.lower() or "timeout" in doc.error.lower()

    @patch("app.research.extractor.httpx.Client")
    def test_http_error_handled(self, mock_client_cls):
        import httpx
        from app.research.extractor import extract_content

        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.headers = {"content-type": "text/html"}
        error = httpx.HTTPStatusError("Not Found", request=MagicMock(), response=mock_response)
        mock_response.raise_for_status.side_effect = error

        mock_instance = MagicMock()
        mock_instance.get.return_value = mock_response
        mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_instance)
        mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)

        doc = extract_content("https://example.com/missing")
        assert doc.status == "failed"

    @patch("app.research.extractor.httpx.Client")
    def test_unsupported_content_type(self, mock_client_cls):
        from app.research.extractor import extract_content

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/pdf"}
        mock_response.content = b"%PDF-1.4 fake content"
        mock_response.raise_for_status = MagicMock()

        mock_instance = MagicMock()
        mock_instance.get.return_value = mock_response
        mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_instance)
        mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)

        doc = extract_content("https://example.com/doc.pdf")
        assert doc.status == "skipped"

    @patch("app.research.extractor.httpx.Client")
    def test_large_response_handled(self, mock_client_cls):
        from app.research.extractor import extract_content

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/html"}
        # 6MB content exceeds 5MB limit
        mock_response.content = b"x" * (6 * 1024 * 1024)
        mock_response.raise_for_status = MagicMock()

        mock_instance = MagicMock()
        mock_instance.get.return_value = mock_response
        mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_instance)
        mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)

        doc = extract_content("https://example.com/huge")
        assert doc.status == "skipped"


# --- Context Builder Tests ---

class TestContextBuilder:
    def test_builds_context(self):
        from app.research.context_builder import build_research_context
        from app.research.schemas import SearchResult, WebDocument

        results = [
            SearchResult(title="S1", url="https://example.com/a", rank=1),
            SearchResult(title="S2", url="https://example.com/b", rank=2),
        ]
        docs = [
            WebDocument(url="https://example.com/a", text="Content A", status="success", word_count=10),
            WebDocument(url="https://example.com/b", text="Content B", status="success", word_count=10),
        ]

        ctx = build_research_context("test topic", results, docs)
        assert ctx.source_count == 2
        assert ctx.documents_fetched == 2
        assert ctx.characters_sent > 0
        assert len(ctx.source_references) == 2

    def test_filters_failed_docs(self):
        from app.research.context_builder import build_research_context
        from app.research.schemas import SearchResult, WebDocument

        results = [SearchResult(title="S1", url="https://example.com/a", rank=1)]
        docs = [
            WebDocument(url="https://example.com/a", text="", status="failed", error="timeout"),
        ]

        ctx = build_research_context("topic", results, docs)
        assert ctx.documents_fetched == 0
        assert ctx.documents_failed == 1

    def test_truncation_on_budget(self):
        from app.research.context_builder import build_research_context
        from app.research.schemas import SearchResult, WebDocument

        results = [SearchResult(title="S1", url="https://example.com/a", rank=1)]
        docs = [
            WebDocument(url="https://example.com/a", text="x" * 200_000, status="success", word_count=20000),
        ]

        ctx = build_research_context("topic", results, docs)
        assert ctx.characters_sent <= 100_000


# --- Google Search Provider Tests ---

class TestGoogleSearchProvider:
    def test_missing_api_key(self):
        from app.research.errors import SearchConfigurationError
        with patch("app.research.sources.google_search.get_settings") as m:
            m.return_value = MagicMock(SEARCH_API_KEY="", SEARCH_ENGINE_ID="cx")
            from app.research.sources.google_search import GoogleSearchProvider
            with pytest.raises(SearchConfigurationError):
                GoogleSearchProvider()

    def test_missing_engine_id(self):
        from app.research.errors import SearchConfigurationError
        with patch("app.research.sources.google_search.get_settings") as m:
            m.return_value = MagicMock(SEARCH_API_KEY="key", SEARCH_ENGINE_ID="")
            from app.research.sources.google_search import GoogleSearchProvider
            with pytest.raises(SearchConfigurationError):
                GoogleSearchProvider()

    @pytest.mark.asyncio
    async def test_search_success(self):
        from app.research.sources.google_search import GoogleSearchProvider

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "items": [
                {"title": "Result 1", "link": "https://example.com/1", "snippet": "Snippet 1"},
                {"title": "Result 2", "link": "https://example.com/2", "snippet": "Snippet 2"},
            ]
        }

        with patch("app.research.sources.google_search.get_settings") as m:
            m.return_value = MagicMock(SEARCH_API_KEY="key", SEARCH_ENGINE_ID="cx")
            with patch("app.research.sources.google_search.httpx.AsyncClient") as h:
                mock_client = AsyncMock()
                mock_client.get = AsyncMock(return_value=mock_response)
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                h.return_value = mock_client

                provider = GoogleSearchProvider()
                results = await provider.search("test query", max_results=5)

                assert len(results) == 2
                assert results[0].title == "Result 1"
                assert results[0].rank == 1

    @pytest.mark.asyncio
    async def test_search_no_results(self):
        from app.research.sources.google_search import GoogleSearchProvider

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}

        with patch("app.research.sources.google_search.get_settings") as m:
            m.return_value = MagicMock(SEARCH_API_KEY="key", SEARCH_ENGINE_ID="cx")
            with patch("app.research.sources.google_search.httpx.AsyncClient") as h:
                mock_client = AsyncMock()
                mock_client.get = AsyncMock(return_value=mock_response)
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                h.return_value = mock_client

                provider = GoogleSearchProvider()
                results = await provider.search("no results query")
                assert results == []

    @pytest.mark.asyncio
    async def test_search_rate_limit(self):
        from app.research.errors import SearchProviderError
        from app.research.sources.google_search import GoogleSearchProvider

        mock_response = MagicMock()
        mock_response.status_code = 429

        with patch("app.research.sources.google_search.get_settings") as m:
            m.return_value = MagicMock(SEARCH_API_KEY="key", SEARCH_ENGINE_ID="cx")
            with patch("app.research.sources.google_search.httpx.AsyncClient") as h:
                mock_client = AsyncMock()
                mock_client.get = AsyncMock(return_value=mock_response)
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                h.return_value = mock_client

                provider = GoogleSearchProvider()
                with pytest.raises(SearchProviderError):
                    await provider.search("query")


# --- Research Service Tests ---

class TestResearchService:
    @pytest.fixture
    def db(self):
        engine = _make_test_engine()
        S = sessionmaker(bind=engine)
        session = S()
        yield session
        session.close()
        engine.dispose()

    @pytest.mark.asyncio
    async def test_full_pipeline_success(self, db):
        from app.research.service import ResearchService
        from app.research.schemas import SearchResult, WebDocument
        from app.database.models.research import ResearchRun, ResearchStatus

        run = ResearchRun(topic="Test research topic")
        db.add(run)
        db.flush()

        mock_search = MagicMock()
        mock_search.search = AsyncMock(return_value=[
            SearchResult(title="Source 1", url="https://example.com/1", snippet="S1", source_domain="example.com", rank=1),
        ])

        mock_ai = MagicMock()
        mock_ai.model = "test-model"
        mock_ai.generate = AsyncMock(return_value=MagicMock(
            content=json.dumps({
                "topic": "Test research topic",
                "summary": "Test summary.",
                "findings": ["Finding 1"],
                "problems": ["Problem 1"],
                "opportunities": ["Opportunity 1"],
                "source_references": ["S1"],
                "uncertainties": ["Uncertainty 1"],
            }),
            usage=MagicMock(input_tokens=100, output_tokens=200),
        ))

        with patch("app.research.service.extract_content") as mock_extract:
            mock_extract.return_value = WebDocument(
                url="https://example.com/1",
                title="Source 1",
                text="This is test content about the topic.",
                status="success",
                word_count=8,
            )
            with patch("app.research.service.GoogleSearchProvider", return_value=mock_search):
                with patch("app.research.service.OpenRouterProvider", return_value=mock_ai):
                    service = ResearchService(
                        search_provider=mock_search,
                        ai_provider=mock_ai,
                    )
                    result = await service.run(run, db)

        assert result.topic == "Test research topic"
        assert run.status == ResearchStatus.COMPLETED
        assert run.completed_at is not None

    @pytest.mark.asyncio
    async def test_no_search_results(self, db):
        from app.research.service import ResearchService
        from app.research.errors import NoUsableSourcesError
        from app.database.models.research import ResearchRun, ResearchStatus

        run = ResearchRun(topic="No results topic")
        db.add(run)
        db.flush()

        mock_search = MagicMock()
        mock_search.search = AsyncMock(return_value=[])

        mock_ai = MagicMock()
        mock_ai.model = "test-model"

        service = ResearchService(search_provider=mock_search, ai_provider=mock_ai)

        with pytest.raises(NoUsableSourcesError):
            await service.run(run, db)

        assert run.status == ResearchStatus.FAILED
        db.commit()

    @pytest.mark.asyncio
    async def test_partial_source_failure(self, db):
        from app.research.service import ResearchService
        from app.research.schemas import SearchResult, WebDocument
        from app.database.models.research import ResearchRun, ResearchStatus

        run = ResearchRun(topic="Partial failure topic")
        db.add(run)
        db.flush()

        mock_search = MagicMock()
        mock_search.search = AsyncMock(return_value=[
            SearchResult(title="Good", url="https://example.com/good", snippet="", rank=1),
            SearchResult(title="Bad", url="https://example.com/bad", snippet="", rank=2),
        ])

        mock_ai = MagicMock()
        mock_ai.model = "test-model"
        mock_ai.generate = AsyncMock(return_value=MagicMock(
            content=json.dumps({
                "topic": "Partial failure topic",
                "summary": "Summary",
                "findings": [],
                "source_references": ["S1"],
            }),
            usage=MagicMock(input_tokens=50, output_tokens=100),
        ))

        def mock_extract(url):
            if "good" in url:
                return WebDocument(url=url, title="Good", text="Good content", status="success", word_count=2)
            return WebDocument(url=url, title="Bad", status="failed", error="timeout")

        with patch("app.research.service.extract_content", side_effect=mock_extract):
            service = ResearchService(search_provider=mock_search, ai_provider=mock_ai)
            result = await service.run(run, db)

        assert result.topic == "Partial failure topic"
        assert run.status == ResearchStatus.COMPLETED


# --- API Endpoint Tests ---

class TestResearchEndpoints:
    def _mock_service(self, result=None, error=None):
        m = MagicMock()
        if error:
            m.run = AsyncMock(side_effect=error)
        else:
            from app.ai.schemas import ResearchResult
            from app.database.models.research import ResearchStatus
            from datetime import datetime, timezone

            async def _fake_run(run_obj, db):
                run_obj.status = ResearchStatus.COMPLETED
                run_obj.completed_at = datetime.now(timezone.utc)
                return ResearchResult(
                    topic=run_obj.topic,
                    summary="Summary",
                    findings=["F1"],
                    source_references=["S1"],
                )
            m.run = AsyncMock(side_effect=_fake_run)
        return m

    def test_create_research(self, client):
        with patch("app.api.routes.research.ResearchService") as M:
            M.return_value = self._mock_service()
            r = client.post("/api/research", json={"topic": "Test research topic"})
            assert r.status_code == 201
            d = r.json()
            assert d["status"] == "completed"
            assert d["sources_found"] >= 0

    def test_empty_topic(self, client):
        assert client.post("/api/research", json={"topic": ""}).status_code == 422

    def test_short_topic(self, client):
        assert client.post("/api/research", json={"topic": "ab"}).status_code == 422

    def test_long_topic(self, client):
        assert client.post("/api/research", json={"topic": "x" * 501}).status_code == 422

    def test_search_config_error(self, client):
        from app.research.errors import SearchConfigurationError
        with patch("app.api.routes.research.ResearchService") as M:
            M.return_value = self._mock_service(error=SearchConfigurationError("no key"))
            r = client.post("/api/research", json={"topic": "Test config error"})
            assert r.status_code == 503
            assert r.json()["detail"]["code"] == "SEARCH_CONFIGURATION_ERROR"

    def test_no_usable_sources(self, client):
        from app.research.errors import NoUsableSourcesError
        with patch("app.api.routes.research.ResearchService") as M:
            M.return_value = self._mock_service(error=NoUsableSourcesError("no sources"))
            r = client.post("/api/research", json={"topic": "Test no sources"})
            assert r.status_code == 422
            assert r.json()["detail"]["code"] == "NO_USABLE_SOURCES"

    def test_list_research(self, client):
        r = client.get("/api/research")
        assert r.status_code == 200
        assert r.json()["items"] == []

    def test_get_research_not_found(self, client):
        assert client.get("/api/research/99999").status_code == 404

    def test_get_research_sources_not_found(self, client):
        assert client.get("/api/research/99999/sources").status_code == 404

    def test_get_research_sources(self, client):
        with patch("app.api.routes.research.ResearchService") as M:
            M.return_value = self._mock_service()
            r = client.post("/api/research", json={"topic": "Source endpoint test"})
            rid = r.json()["id"]
        r = client.get(f"/api/research/{rid}/sources")
        assert r.status_code == 200
        d = r.json()
        assert d["research_id"] == rid
        assert isinstance(d["sources"], list)


# --- Health endpoint sanity ---

def test_root(client):
    r = client.get("/")
    assert r.status_code == 200
    assert r.json()["status"] == "running"


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}
