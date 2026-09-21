"""Health check routes."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.database import check_database_connection, get_db
from app.schemas.health import DatabaseHealthResponse, HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Return service health status."""
    return HealthResponse(status="ok")


@router.get("/health/database", response_model=DatabaseHealthResponse)
async def database_health(db: Session = Depends(get_db)) -> DatabaseHealthResponse:
    """Check database connectivity."""
    db_ok = check_database_connection()
    if not db_ok:
        return DatabaseHealthResponse(status="error", database="disconnected")
    return DatabaseHealthResponse(status="ok", database="connected")


@router.get("/health/ai")
async def ai_health() -> dict:
    """Check AI provider health.

    Never exposes API keys or secrets.
    """
    try:
        from app.ai.key_pool import OpenRouterKeyPool
        pool = OpenRouterKeyPool()
        status = pool.get_status()
        return {
            "status": "ok" if status["configured_key_slots"] > 0 else "not_configured",
            "provider": status["provider"],
            "configured_keys": status["configured_key_slots"],
        }
    except Exception:
        return {
            "status": "not_configured",
            "provider": "openrouter",
            "configured_keys": 0,
        }


@router.get("/health/github")
async def github_health() -> dict:
    """Check GitHub integration health.

    Never exposes tokens or secrets.
    """
    from app.github.service import GitHubService
    service = GitHubService()
    configured = service.is_configured()
    return {
        "status": "ok" if configured else "not_configured",
        "configured": configured,
    }
