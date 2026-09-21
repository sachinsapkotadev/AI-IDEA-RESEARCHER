# AI Idea Researcher

An AI-powered platform that researches, validates, and refines business ideas using real web search, multi-agent analysis, and LLM-powered insights.

**Repository:** [github.com/sachinsapkotadev/AI-IDEA-RESEARCHER](https://github.com/sachinsapkotadev/AI-IDEA-RESEARCHER) (Private)

---

## What It Does

AI Idea Researcher takes a business topic or idea and:

1. **Searches the web** for real, up-to-date information using Google Custom Search
2. **Extracts and processes** content from authoritative sources
3. **Runs a 5-agent AI pipeline** that analyzes market conditions, competitors, generates ideas, assesses technical feasibility, and creates validation plans
4. **Presents everything** through a modern web dashboard with research tracking, agent insights, and idea management

---

## Project Structure

```
AI-IDEA-RESEARCHER/
├── Backend/          # Python FastAPI backend (AI engine + API)
├── Website/          # Astro.js frontend (dashboard + marketing)
├── Android/          # Mobile app (coming soon)
└── README.md         # This file
```

---

## Backend — AI Engine & API

A **FastAPI** backend that powers the entire research and analysis pipeline.

### Tech Stack
- **Python 3.11+** with FastAPI
- **PostgreSQL** via SQLAlchemy 2.x + Alembic migrations
- **OpenRouter** LLM APIs (supports key rotation across 12 keys)
- **Google Custom Search API** for web research
- **httpx + BeautifulSoup** for content extraction

### Core Modules

| Module | Purpose |
|--------|---------|
| `app/ai/` | OpenRouter client, AI provider abstraction, research agent |
| `app/agents/` | 5-agent analysis pipeline (Market, Competitor, Idea, Technical, Validation) |
| `app/research/` | Web search, content extraction, quality classification, context building |
| `app/api/routes/` | REST API endpoints for research, analysis, and ideas |
| `app/database/` | SQLAlchemy models, database session management |
| `app/core/config.py` | Environment-based configuration via pydantic-settings |

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | API info |
| GET | `/health` | Service health check |
| GET | `/health/database` | Database connectivity |
| POST | `/api/research` | Start a new research run |
| GET | `/api/research` | List research runs (paginated) |
| GET | `/api/research/{id}` | Get research run by ID |
| GET | `/api/research/{id}/sources` | Get sources for a run |
| POST | `/api/research/{id}/analyze` | Run multi-agent analysis |
| GET | `/api/research/{id}/analysis-status` | Pipeline status |
| GET | `/api/research/{id}/agents` | Agent execution history |
| GET | `/api/research/{id}/ideas` | Ideas from research |
| GET | `/api/ideas` | List all ideas (paginated, filterable) |
| GET | `/api/ideas/{id}` | Get single idea |

### Research Pipeline Flow

```
User Topic → POST /api/research
    ↓
ResearchService
    ↓
Google Search API → Search Results (validated, normalized)
    ↓
URL Deduplication → Content Extraction (httpx + BeautifulSoup)
    ↓
Source Quality Classification → PostgreSQL storage
    ↓
Context Building (token optimization)
    ↓
Research Agent (OpenRouter LLM) → Validated Research Result
```

### Multi-Agent Analysis Pipeline

```
ResearchRun (completed) → POST /api/research/{id}/analyze
    ↓
AgentOrchestrator (sequential execution)
    ↓
┌─────────────────────────────────────────┐
│ 1. MarketAnalyst    → problems, trends  │
│ 2. CompetitorAnalyst → gaps, landscape  │
│ 3. IdeaGenerator    → 3-5 SaaS ideas   │
│ 4. TechnicalAnalyst → feasibility, risks│
│ 5. ValidationPlanner → success criteria │
└─────────────────────────────────────────┘
    ↓
PostgreSQL (Idea model + AgentRun tracking)
```

### Source Quality Categories

| Category | Description |
|----------|-------------|
| official | Government (.gov), education (.edu), major platforms |
| documentation | Official docs (MDN, AWS, Python, etc.) |
| news | Major outlets (Reuters, TechCrunch, etc.) |
| community | Reddit, HN, StackOverflow, dev.to |
| blog | Personal blogs, Medium posts |
| unknown | Unclassified sources |

### Security

- SSRF protection (blocks localhost, private IPs, cloud metadata)
- Content-type validation (HTML/text only)
- Response size limits (5MB max)
- Redirect limits (max 5)
- URL scheme validation (http/https only)
- No script/file execution from downloaded content

### Running Backend Locally

```bash
cd Backend

# Create virtual environment
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS/Linux

# Install dependencies
pip install -r requirements.txt

# Set up environment
copy .env.example .env
# Edit .env with your DATABASE_URL, OPENROUTER_API_KEY, SEARCH_API_KEY, etc.

# Run migrations
alembic upgrade head

# Start server
python run.py
# or: uvicorn app.main:app --reload
```

API docs at **http://localhost:8000/docs**

### Running Tests

```bash
cd Backend
pytest -v
```

Tests mock all external APIs — no real keys needed.

---

## Website — Frontend

An **Astro.js** website with Tailwind CSS v4, serving as both a marketing site and a full dashboard.

### Tech Stack
- **Astro 7** (SSG/SSR)
- **Tailwind CSS v4** via Vite plugin
- **TypeScript**
- **Node.js 22+**

### Pages

**Marketing:**
| Page | Route | Description |
|------|-------|-------------|
| Home | `/` | Landing page with hero, features, testimonials, FAQ |
| Features | `/features` | Detailed feature breakdown |
| Pricing | `/pricing` | Pricing plans (Free, Pro, Enterprise) |
| About | `/about` | Company info and team |
| Blog | `/blog` | Blog posts with dynamic slugs |
| Contact | `/contact` | Contact form |

**Dashboard:**
| Page | Route | Description |
|------|-------|-------------|
| Overview | `/dashboard` | Stats, recent activity, quick actions |
| Research | `/dashboard/research` | Research runs list |
| Research Detail | `/dashboard/research/[id]` | Individual research run + sources |
| Ideas | `/dashboard/ideas` | Generated ideas with filtering |
| Agents | `/dashboard/agents` | AI agent status and history |
| Models | `/dashboard/models` | AI model selection |
| Reports | `/dashboard/reports` | Generated reports |
| GitHub | `/dashboard/github` | GitHub integration |
| Automation | `/dashboard/automation` | Automation workflows |
| Settings | `/dashboard/settings` | User settings + theme toggle |

### Components

| Component | Purpose |
|-----------|---------|
| `Badge.astro` | Status/label badges |
| `Breadcrumbs.astro` | Navigation breadcrumbs |
| `Button.astro` | Reusable button variants |
| `Card.astro` | Content cards |
| `EmptyState.astro` | Empty state placeholders |
| `ErrorState.astro` | Error display |
| `FAQ.accordion` | FAQ accordion |
| `FeatureCard.astro` | Feature showcase cards |
| `Input.astro` / `Textarea.astro` | Form inputs |
| `LoadingState.astro` | Loading indicators |
| `PricingCard.astro` | Pricing tier cards |
| `SectionHeader.astro` | Section headings |
| `SkeletonCard.astro` / `SkeletonTable.astro` | Loading skeletons |
| `StatCard.astro` | Statistics display |
| `StatusBadge.astro` | Status indicators |
| `Testimonial.astro` | User testimonials |
| `ThemeToggle.astro` | Dark/light mode toggle |

### API Layer

- `src/lib/api/client.ts` — HTTP client for backend API
- `src/lib/api/demo.ts` — Demo/mock data for development
- `src/lib/api/types.ts` — TypeScript type definitions
- `src/lib/auth/index.ts` — Authentication utilities

### Running Website Locally

```bash
cd Website

# Install dependencies
npm install

# Start dev server
npm run dev
# or: astro dev --background

# Build for production
npm run build

# Preview production build
npm run preview
```

Website runs at **http://localhost:4321**

---

## Android — Coming Soon

Mobile app for on-the-go idea research and management.

---

## Configuration

### Backend Environment Variables

```env
# Database
DATABASE_URL=postgresql+psycopg://user:pass@localhost:5432/ai_idea_researcher

# OpenRouter AI (supports key rotation)
OPENROUTER_API_KEY=your-primary-key
OPENROUTER_API_KEY_01=your-key-01
OPENROUTER_API_KEY_02=your-key-02
# ... up to OPENROUTER_API_KEY_12
OPENROUTER_MODEL=your-model-name

# Google Search
SEARCH_PROVIDER=google
SEARCH_API_KEY=your-google-api-key
SEARCH_ENGINE_ID=your-search-engine-id

# GitHub Integration
GITHUB_TOKEN=your-github-token
GITHUB_REPOSITORY=owner/repo

# Source Limits
SEARCH_DEFAULT_NUM=10
MAX_SEARCH_RESULTS=10
MAX_SOURCES_PER_RESEARCH=10
MAX_CONTENT_LENGTH_PER_SOURCE=50000
MAX_TOTAL_RESEARCH_CONTEXT=100000
MAX_CONCURRENT_RESEARCH=5

# CORS
CORS_ORIGINS=http://localhost:4321,http://localhost:3000

# Logging
LOG_LEVEL=INFO
```

---

## Development Status

| Phase | Status | Description |
|-------|--------|-------------|
| Phase 1 | ✅ Complete | Project foundation (FastAPI scaffold, config, health checks) |
| Phase 2 | ✅ Complete | Database foundation (PostgreSQL, SQLAlchemy, Alembic, models) |
| Phase 3 | ✅ Complete | OpenRouter AI engine (client, provider, research agent) |
| Phase 4 | ✅ Complete | Real web research (Google Search, content extraction, quality scoring) |
| Phase 5 | ✅ Complete | Multi-agent analysis pipeline (5 agents, orchestrator, idea generation) |
| Phase 6 | 🚧 Planned | GitHub integration |
| Phase 7 | 🚧 Planned | API authentication |
| Phase 8 | 🚧 Planned | Frontend clients (full dashboard integration) |

---

## Tests

```bash
# Backend tests (112+ tests)
cd Backend
pytest -v

# All external APIs mocked — no real keys needed
```

---

## License

Private repository — All rights reserved.

---

**Built by [Sachin Dev](https://github.com/sachinsapkotadev)**
