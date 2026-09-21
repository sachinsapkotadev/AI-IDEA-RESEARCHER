# Phase 3 Design Spec — OpenRouter + AI Engine Foundation

## Overview

Add OpenRouter LLM integration, AI provider abstraction, structured AI responses, first Research Agent, AI usage tracking, and safe error handling to the existing FastAPI + PostgreSQL backend.

## Architecture

```
POST /api/research
    ↓
ResearchAgent.run(topic)
    ↓
AIProvider.generate(prompt)  [abstract interface]
    ↓
OpenRouterProvider           [httpx async HTTP]
    ↓
OpenRouter /chat/completions [OpenAI-compatible API]
```

## New Files

| File | Purpose |
|------|---------|
| `app/ai/__init__.py` | Package |
| `app/ai/client.py` | OpenRouter HTTP client (httpx async) |
| `app/ai/schemas.py` | AI request/response Pydantic models |
| `app/ai/errors.py` | AI-specific exceptions |
| `app/ai/provider.py` | Abstract AIProvider + OpenRouterProvider |
| `app/ai/prompts.py` | Research prompt constants |
| `app/ai/research_agent.py` | ResearchAgent orchestrator |
| `app/api/routes/research.py` | POST/GET research endpoints |
| `app/schemas/research.py` | API request/response schemas |
| `tests/test_research.py` | Full test suite |

## Modified Files

| File | Change |
|------|--------|
| `app/core/config.py` | Add `OPENROUTER_BASE_URL`, `OPENROUTER_MODEL` |
| `app/main.py` | Register research router |
| `.env.example` | Add OpenRouter env vars |
| `README.md` | Phase 3 documentation |

## Database Change

Add `result_data` JSONB column to `research_runs` via Alembic migration. Stores serialized `ResearchResult` as JSON. No data loss — column is nullable.

## Provider Abstraction

```python
class AIProvider(ABC):
    async def generate(self, prompt: str, system_prompt: str | None = None) -> AIResponse: ...

class OpenRouterProvider(AIProvider):
    # Uses httpx async client
    # Calls POST /chat/completions
    # Returns AIResponse with content + usage
```

## Research Agent Flow

1. Receive topic
2. Construct research prompt (from prompts.py)
3. Call AIProvider.generate()
4. Parse JSON from response (strip markdown fences if present)
5. Validate with Pydantic (ResearchResult schema)
6. Return validated result

## Error Handling

Custom exceptions → mapped to clean API error responses. Never expose API keys, raw provider responses, or stack traces.

## Testing

All tests mock the AI provider. No real API calls. Tests cover: valid response, malformed JSON, invalid schema, timeout, provider error, missing config, agent success/failure, API endpoints, token usage persistence.
