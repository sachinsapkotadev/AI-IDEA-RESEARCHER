"""Application configuration using pydantic-settings."""

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    APP_NAME: str = "AI Idea Researcher API"
    APP_VERSION: str = "0.2.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = False

    # Database
    DATABASE_URL: str = ""

    # OpenRouter — 12 key slots (_01 through _12)
    OPENROUTER_API_KEY_01: str = ""
    OPENROUTER_API_KEY_02: str = ""
    OPENROUTER_API_KEY_03: str = ""
    OPENROUTER_API_KEY_04: str = ""
    OPENROUTER_API_KEY_05: str = ""
    OPENROUTER_API_KEY_06: str = ""
    OPENROUTER_API_KEY_07: str = ""
    OPENROUTER_API_KEY_08: str = ""
    OPENROUTER_API_KEY_09: str = ""
    OPENROUTER_API_KEY_10: str = ""
    OPENROUTER_API_KEY_11: str = ""
    OPENROUTER_API_KEY_12: str = ""
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    OPENROUTER_PROXY_PORT: int = 3457
    OPENROUTER_PROXY_HOST: str = "127.0.0.1"
    OPENROUTER_MAX_RETRIES: int = 3

    # Default model (used when agent-specific not set)
    OPENROUTER_MODEL: str = "nvidia/nemotron-3.5-lightning:free"
    DEFAULT_MODEL: str = "nvidia/nemotron-3.5-lightning:free"

    # Per-agent model assignments (20 free models available)
    MODEL_MARKET_ANALYST: str = "inclusionai/ling-3.0-flash-vl:free"
    MODEL_COMPETITOR_ANALYST: str = "nex-agi/nex-n2.5-mini:free"
    MODEL_IDEA_GENERATOR: str = "qwen/qwen3.8-27b:free"
    MODEL_TECHNICAL_ANALYST: str = "nvidia/nemotron-3-ultra-550b-a55b:free"
    MODEL_VALIDATION_PLANNER: str = "cohere/north-mini-code:free"

    # NVIDIA
    NVIDIA_API_KEY: str = ""

    @property
    def openrouter_api_keys(self) -> list[str]:
        """Return all valid API keys for round-robin rotation."""
        keys = []
        for i in range(1, 13):
            key = getattr(self, f"OPENROUTER_API_KEY_{str(i).zfill(2)}", "")
            if key and "YOUR_KEY" not in key and "xxxxxxxx" not in key:
                keys.append(key)
        if not keys and self.OPENROUTER_API_KEY:
            keys.append(self.OPENROUTER_API_KEY)
        return keys

    def get_agent_model(self, agent_name: str) -> str:
        """Return the model for a specific agent, falling back to default."""
        model_map = {
            "MarketAnalyst": self.MODEL_MARKET_ANALYST,
            "CompetitorAnalyst": self.MODEL_COMPETITOR_ANALYST,
            "IdeaGenerator": self.MODEL_IDEA_GENERATOR,
            "TechnicalAnalyst": self.MODEL_TECHNICAL_ANALYST,
            "ValidationPlanner": self.MODEL_VALIDATION_PLANNER,
        }
        return model_map.get(agent_name, self.DEFAULT_MODEL)

    # Search Provider (Phase 4)
    SEARCH_PROVIDER: str = "google"
    SEARCH_API_KEY: str = ""
    SEARCH_ENGINE_ID: str = ""
    SEARCH_DEFAULT_NUM: int = 10

    # Source Limits (Phase 4)
    MAX_SEARCH_RESULTS: int = 10
    MAX_SOURCES_PER_RESEARCH: int = 10
    MAX_CONTENT_LENGTH_PER_SOURCE: int = 50_000
    MAX_TOTAL_RESEARCH_CONTEXT: int = 100_000
    MAX_CONCURRENT_RESEARCH: int = 5

    # Content Extraction (Phase 4)
    SEARCH_USER_AGENT: str = "AI-Idea-Researcher/1.0 (+https://ai-idea-researcher.local)"

    # Report Generation (Phase 6)
    REPORTS_DIR: str = "./reports"

    # GitHub Integration (Phase 6)
    GITHUB_TOKEN: str = ""
    GITHUB_OWNER: str = ""
    GITHUB_REPO: str = ""
    GITHUB_DEFAULT_BRANCH: str = "main"
    GITHUB_RESEARCH_BRANCH_PREFIX: str = "research/"

    # CORS
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:8080"

    # Logging
    LOG_LEVEL: str = "INFO"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }

    @property
    def cors_origin_list(self) -> list[str]:
        """Parse comma-separated CORS origins into a list."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def database_url(self) -> str:
        """Return the database URL, raising if empty when needed."""
        if not self.DATABASE_URL:
            raise ValueError("DATABASE_URL is not configured")
        return self.DATABASE_URL

    def get_api_keys(self) -> list[tuple[str, str]]:
        """Return list of (slot_name, key_value) for configured, non-empty keys.

        Slot names are like '01', '02', ..., '12'.
        Only returns slots with actual key values.
        """
        keys: list[tuple[str, str]] = []
        for i in range(1, 13):
            slot = f"{i:02d}"
            attr = f"OPENROUTER_API_KEY_{slot}"
            value = getattr(self, attr, "")
            if value and value.strip():
                keys.append((slot, value.strip()))
        return keys


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()
