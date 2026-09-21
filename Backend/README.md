# AI Idea Researcher — Backend

A FastAPI backend for researching, validating, and refining AI-related ideas using real web search, content extraction, and OpenRouter LLM APIs.

## Requirements

- **Python 3.11+**
- **PostgreSQL 14+** (or a hosted instance)
- pip

## Installation

```bash
# Clone the repository
git clone <repo-url>
cd Backend

# Create virtual environment
python -m venv .venv

# Activate (Windows)
.venv\Scripts\activate

# Activate (macOS/Linux)
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## PostgreSQL Setup

1. Install PostgreSQL or use a hosted service (e.g., Render, Supabase).

2. Create the database:

```sql
CREATE DATABASE ai_idea_researcher;
```

3. Copy the environment file and set your `DATABASE_URL`:

```bash
copy .env.example .env       # Windows
cp .env.example .env          # macOS/Linux
```

Edit `.env` and set `DATABASE_URL`:

```
DATABASE_URL=postgresql+psycopg://username:password@localhost:5432/ai_idea_researcher
```

> **Important:** Never commit `.env` to version control.

## Search Provider Configuration

Phase 4 introduces real web search via Google Custom Search JSON API.

1. Get a Google API key: https://console.cloud.google.com/apis/credentials
2. Create a Custom Search Engine: https://cse.google.com/cse/all
3. Set your engine ID: https://programmablesearchengine.google.com/controlpanel/all

Add to `.env`:

```
SEARCH_PROVIDER=google
SEARCH_API_KEY=your-google-api-key
SEARCH_ENGINE_ID=your-search-engine-id
```

Other configurable options:

```
SEARCH_DEFAULT_NUM=10          # Default results per search
MAX_SEARCH_RESULTS=10          # Max search results to process
MAX_SOURCES_PER_RESEARCH=10    # Max sources to fetch content from
MAX_CONTENT_LENGTH_PER_SOURCE=50000  # Max characters per source
MAX_TOTAL_RESEARCH_CONTEXT=100000    # Max total characters for AI context
MAX_CONCURRENT_RESEARCH=5      # Max concurrent research runs
```

## Running Migrations

```bash
# Apply all migrations
alembic upgrade head

# Check current migration
alembic current

# View migration history
alembic history
```

## Running Locally

```bash
python run.py
```

or:

```bash
uvicorn app.main:app --reload
```

The API starts at **http://localhost:8000** with auto-reload in development mode.

## API Documentation

Once running, visit:

| Page | URL |
|------|-----|
| Swagger UI | http://localhost:8000/docs |
| ReDoc | http://localhost:8000/redoc |
| OpenAPI JSON | http://localhost:8000/openapi.json |

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | API information |
| GET | `/health` | Service health check |
| GET | `/health/database` | Database connectivity check |
| POST | `/api/research` | Start a new research run |
| GET | `/api/research` | List research runs (paginated) |
| GET | `/api/research/{id}` | Get a research run by ID |
| GET | `/api/research/{id}/sources` | Get sources for a research run |

### POST /api/research

```json
// Request
{
  "topic": "SaaS opportunities for small businesses"
}

// Response (201)
{
  "id": 1,
  "topic": "SaaS opportunities for small businesses",
  "status": "completed",
  "sources_found": 10,
  "sources_used": 5,
  "result": {
    "topic": "SaaS opportunities for small businesses",
    "summary": "...",
    "findings": ["..."],
    "problems": ["..."],
    "opportunities": ["..."],
    "source_references": ["S1", "S2"],
    "uncertainties": ["..."]
  },
  "started_at": "2026-09-21T15:30:00Z",
  "completed_at": "2026-09-21T15:30:15Z",
  "created_at": "2026-09-21T15:30:00Z"
}
```

### GET /api/research/{id}/sources

```json
// Response (200)
{
  "research_id": 1,
  "topic": "SaaS opportunities for small businesses",
  "sources": [
    {
      "id": 1,
      "title": "Article Title",
      "url": "https://example.com/article",
      "source_type": "web",
      "domain": "example.com",
      "quality": "news",
      "status": "success",
      "word_count": 1500,
      "rank": 1
    }
  ]
}
```

## Running Tests

```bash
pytest -v
```

Tests mock all external APIs (Google Search, OpenRouter, webpage fetching).
No real API keys are required to run tests.

## Architecture

### Research Pipeline

```
User Topic
    ↓
POST /api/research
    ↓
ResearchService
    ↓
GoogleSearchProvider → Google Custom Search API
    ↓
Search Results (validated, normalized)
    ↓
URL Normalization + Deduplication
    ↓
Content Extraction (httpx + BeautifulSoup)
    ↓
Source Quality Classification
    ↓
PostgreSQL ResearchSource records
    ↓
Context Building (prioritization, truncation)
    ↓
Research Agent (OpenRouter LLM)
    ↓
Validated Research Result
    ↓
PostgreSQL ResearchRun
```

### Source Quality Categories

| Category | Description |
|----------|-------------|
| official | Government (.gov), education (.edu), major platforms |
| documentation | Official docs sites (MDN, AWS, Python, etc.) |
| news | Major news outlets (Reuters, TechCrunch, etc.) |
| community | Reddit, HN, StackOverflow, dev.to |
| blog | Personal blogs, Medium posts |
| unknown | Unclassified sources |

### Security Protections

- SSRF protection: blocks localhost, private IPs, cloud metadata endpoints
- Content-type validation: only HTML/text content is processed
- Response size limits: max 5MB per page
- Redirect limits: max 5 redirects
- URL validation: only http/https schemes allowed
- No JavaScript execution from downloaded content
- No script/file execution from downloaded content

### Token Optimization

Before sending content to the AI:

1. Navigation/script/style noise removed
2. Duplicate content filtered
3. Oversized sources truncated
4. Total context capped (default: 100k characters)
5. Source quality prioritization

## Current Status

**Phase 1 — Project Foundation** ✅ Complete

- FastAPI application scaffold
- Configuration management
- Health check endpoints
- CORS middleware
- Global exception handling
- Test suite

**Phase 2 — Database Foundation** ✅ Complete

- PostgreSQL via SQLAlchemy 2.x
- Alembic migrations
- Database models (ResearchRun, ResearchSource, Idea, AgentRun)
- Database session management
- Database health endpoint

**Phase 3 — OpenRouter AI Engine** ✅ Complete

- OpenRouter HTTP client
- AI provider abstraction
- Research Agent with structured output
- JSON response parsing
- Error handling and retry logic

**Phase 4 — Real Web Research** ✅ Complete

- Google Custom Search integration
- URL normalization and deduplication
- Web content extraction (httpx + BeautifulSoup)
- Source quality classification
- Research pipeline orchestration
- Context building with token optimization
- Source citations in AI output
- SSRF protection
- Comprehensive test suite (56 tests)

## Future Architecture

| Phase | Description |
|-------|-------------|
| Phase 5 | Multi-agent system (Market Analyst, Competitor Analyst, etc.) |
| Phase 6 | GitHub integration |
| Phase 7 | API authentication |
| Phase 8 | Frontend clients |

## Project Structure

```
Backend/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── core/
│   │   ├── __init__.py
│   │   └── config.py
│   ├── api/
│   │   ├── __init__.py
│   │   └── routes/
│   │       ├── __init__.py
│   │       ├── health.py
│   │       └── research.py
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── health.py
│   │   └── research.py
│   ├── database/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── database.py
│   │   └── models/
│   │       ├── __init__.py
│   │       ├── research.py
│   │       ├── source.py
│   │       ├── idea.py
│   │       └── agent_run.py
│   ├── ai/
│   │   ├── __init__.py
│   │   ├── client.py
│   │   ├── provider.py
│   │   ├── prompts.py
│   │   ├── schemas.py
│   │   ├── errors.py
│   │   └── research_agent.py
│   └── research/              # Phase 4
│       ├── __init__.py
│       ├── schemas.py
│       ├── service.py
│       ├── normalizer.py
│       ├── extractor.py
│       ├── quality.py
│       ├── context_builder.py
│       ├── errors.py
│       └── sources/
│           ├── __init__.py
│           ├── base.py
│           └── google_search.py
├── alembic/
│   ├── versions/
│   │   ├── 06bd93681223_initial_tables.py
│   │   └── 07ce2d9a3145_extend_research_sources.py
│   ├── env.py
│   └── script.py.mako
├── tests/
│   ├── __init__.py
│   ├── test_health.py
│   └── test_research.py
├── alembic.ini
├── .env.example
├── .gitignore
├── requirements.txt
├── README.md
└── run.py
```
