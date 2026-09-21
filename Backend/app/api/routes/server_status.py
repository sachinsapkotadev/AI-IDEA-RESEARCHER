"""Server status routes — real-time backend health dashboard."""

import os
import time
from datetime import datetime, timezone

from fastapi import APIRouter

router = APIRouter()

_start_time = time.time()


@router.get("/api/server-status")
async def server_status() -> dict:
    """Comprehensive server status for the dashboard GUI."""
    uptime_seconds = time.time() - _start_time

    # Database check
    db_status = "unknown"
    db_error = None
    try:
        from app.database.database import check_database_connection
        db_ok = check_database_connection()
        db_status = "connected" if db_ok else "disconnected"
    except Exception as e:
        db_status = "error"
        db_error = str(e)

    # AI provider check
    ai_status = "unknown"
    ai_keys = 0
    ai_models: dict[str, str] = {}
    try:
        from app.ai.key_pool import OpenRouterKeyPool
        pool = OpenRouterKeyPool()
        pool_status = pool.get_status()
        ai_status = "configured" if pool_status.get("configured_key_slots", 0) > 0 else "not_configured"
        ai_keys = pool_status.get("configured_key_slots", 0)
    except Exception:
        ai_status = "not_configured"

    # Model assignments
    try:
        from app.core.config import get_settings
        settings = get_settings()
        ai_models = {
            "MarketAnalyst": settings.MODEL_MARKET_ANALYST,
            "CompetitorAnalyst": settings.MODEL_COMPETITOR_ANALYST,
            "IdeaGenerator": settings.MODEL_IDEA_GENERATOR,
            "TechnicalAnalyst": settings.MODEL_TECHNICAL_ANALYST,
            "ValidationPlanner": settings.MODEL_VALIDATION_PLANNER,
        }
    except Exception:
        pass

    # GitHub check
    github_status = "not_configured"
    try:
        from app.github.service import GitHubService
        svc = GitHubService()
        github_status = "configured" if svc.is_configured() else "not_configured"
    except Exception:
        pass

    # System info
    try:
        import psutil
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        system_info = {
            "cpu_percent": psutil.cpu_percent(interval=0.1),
            "memory_total_mb": round(mem.total / 1024 / 1024),
            "memory_used_mb": round(mem.used / 1024 / 1024),
            "memory_pct": mem.percent,
            "disk_total_gb": round(disk.total / 1024 / 1024 / 1024, 1),
            "disk_used_gb": round(disk.used / 1024 / 1024 / 1024, 1),
            "disk_pct": round(disk.percent, 1),
        }
    except ImportError:
        system_info = None

    # Deep research jobs
    try:
        from app.deep_research.engine import list_jobs
        active_jobs = [j for j in list_jobs() if j["status"] == "running"]
        deep_research = {
            "active_count": len(active_jobs),
            "jobs": list_jobs()[:5],
        }
    except Exception:
        deep_research = {"active_count": 0, "jobs": []}

    # Environment
    env = os.environ.get("ENVIRONMENT", "development")

    return {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "uptime_seconds": round(uptime_seconds, 1),
        "uptime_human": _format_uptime(uptime_seconds),
        "environment": env,
        "services": {
            "database": {
                "status": db_status,
                "error": db_error,
            },
            "ai": {
                "status": ai_status,
                "configured_keys": ai_keys,
                "models": ai_models,
            },
            "github": {
                "status": github_status,
            },
        },
        "system": system_info,
        "deep_research": deep_research,
    }


def _format_uptime(seconds: float) -> str:
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    if hours > 0:
        return f"{hours}h {minutes}m {secs}s"
    elif minutes > 0:
        return f"{minutes}m {secs}s"
    return f"{secs}s"
