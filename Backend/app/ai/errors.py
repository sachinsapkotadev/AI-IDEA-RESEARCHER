"""AI-specific error types."""


class AIError(Exception):
    """Base class for all AI-related errors."""


class AIConfigurationError(AIError):
    """Raised when AI provider is not properly configured."""


class AIProviderError(AIError):
    """Raised when the AI provider returns an error."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class AIRateLimitError(AIProviderError):
    """Raised when rate limited by the AI provider."""


class AITimeoutError(AIProviderError):
    """Raised when the AI provider request times out."""


class AIResponseParsingError(AIError):
    """Raised when the AI response cannot be parsed."""


class AIResponseValidationError(AIError):
    """Raised when the AI response fails Pydantic validation."""


class AIAllKeysExhausted(AIError):
    """Raised when all API keys are unavailable."""
