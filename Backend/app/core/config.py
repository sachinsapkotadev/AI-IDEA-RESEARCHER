"""Application configuration using pydantic-settings."""

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    APP_NAME: str = "AI Idea Researcher API"
    APP_VERSION: str = "0.1.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = False

    # Optional integrations
    DATABASE_URL: str = ""
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    OPENROUTER_MODEL: str = ""
    GITHUB_TOKEN: str = ""
    GITHUB_REPOSITORY: str = ""

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


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()
