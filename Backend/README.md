# AI Idea Researcher — Backend

A FastAPI backend for researching, validating, and refining AI-related ideas using OpenRouter LLM APIs and GitHub integration.

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

## Running Tests

```bash
pytest -v
```

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

## Future Architecture

| Phase | Description |
|-------|-------------|
| Phase 3 | OpenRouter LLM integration |
| Phase 4 | Research agents and orchestrator |
| Phase 5 | GitHub integration |
| Phase 6 | API authentication |
| Phase 7 | Frontend clients |

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
│   │       └── health.py
│   ├── schemas/
│   │   ├── __init__.py
│   │   └── health.py
│   └── database/
│       ├── __init__.py
│       ├── base.py
│       ├── database.py
│       └── models/
│           ├── __init__.py
│           ├── research.py
│           ├── source.py
│           ├── idea.py
│           └── agent_run.py
├── alembic/
│   ├── versions/
│   ├── env.py
│   └── script.py.mako
├── tests/
│   ├── __init__.py
│   └── test_health.py
├── alembic.ini
├── .env.example
├── .gitignore
├── requirements.txt
├── README.md
└── run.py
```
