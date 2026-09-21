"""GitHub integration error types."""


class GitHubError(Exception):
    """Base class for GitHub-related errors."""


class GitHubConfigurationError(GitHubError):
    """Raised when GitHub is not properly configured."""


class GitHubAuthenticationError(GitHubError):
    """Raised when GitHub authentication fails."""


class GitHubRepositoryNotFoundError(GitHubError):
    """Raised when the target repository is not found."""


class GitHubRateLimitError(GitHubError):
    """Raised when GitHub API rate limit is exceeded."""


class GitHubBranchConflictError(GitHubError):
    """Raised when branch creation conflicts."""


class GitHubPublicationError(GitHubError):
    """Raised when publication fails for any reason."""
