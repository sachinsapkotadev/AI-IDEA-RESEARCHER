"""AI status and health routes."""

import logging

from fastapi import APIRouter

from app.ai.key_pool import OpenRouterKeyPool
from app.ai.model_registry import ModelRegistry
from app.github.service import GitHubService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ai"])


@router.get("/api/ai/status")
async def get_ai_status() -> dict:
    """Return safe AI provider status information.

    Never exposes API keys, tokens, or secrets.
    """
    try:
        pool = OpenRouterKeyPool()
        pool_status = pool.get_status()
    except Exception:
        pool_status = {
            "provider": "openrouter",
            "configured_key_slots": 0,
            "available_key_slots": 0,
            "status": "not_configured",
        }

    try:
        registry = ModelRegistry()
        default_model = registry.get_model("default") if registry.is_configured() else ""
    except ValueError:
        default_model = ""

    return {
        "provider": pool_status["provider"],
        "configured_key_slots": pool_status["configured_key_slots"],
        "available_key_slots": pool_status["available_key_slots"],
        "default_model": default_model,
        "status": pool_status["status"],
    }


@router.get("/api/ai/models")
async def get_ai_models() -> dict:
    """Return configured model mappings per agent.

    Never exposes API keys.
    """
    try:
        registry = ModelRegistry()
        models = registry.get_all_configured_models()
    except Exception:
        models = {}

    return {"models": models}
