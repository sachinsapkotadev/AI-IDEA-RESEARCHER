"""GitHub API client using httpx."""

import base64
import logging
from typing import Any

import httpx

from app.core.config import get_settings
from app.github.errors import (
    GitHubAuthenticationError,
    GitHubConfigurationError,
    GitHubRateLimitError,
    GitHubRepositoryNotFoundError,
)

logger = logging.getLogger(__name__)

GITHUB_API_BASE = "https://api.github.com"
DEFAULT_TIMEOUT = 30.0


class GitHubClient:
    """Low-level GitHub API client.

    Uses httpx to interact with the GitHub REST API.
    Does not use PyGithub or similar libraries.
    """

    def __init__(self) -> None:
        self._settings = get_settings()
        self._validate_config()

    def _validate_config(self) -> None:
        """Ensure required configuration is present."""
        if not self._settings.GITHUB_TOKEN:
            raise GitHubConfigurationError(
                "GITHUB_TOKEN is not configured. "
                "Set it in your .env file or environment."
            )
        if not self._settings.GITHUB_OWNER:
            raise GitHubConfigurationError(
                "GITHUB_OWNER is not configured."
            )
        if not self._settings.GITHUB_REPO:
            raise GitHubConfigurationError(
                "GITHUB_REPO is not configured."
            )

    @property
    def _headers(self) -> dict[str, str]:
        """Return headers for GitHub API requests."""
        return {
            "Authorization": f"Bearer {self._settings.GITHUB_TOKEN}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    @property
    def _repo_url(self) -> str:
        """Return the base URL for the target repository."""
        return f"{GITHUB_API_BASE}/repos/{self._settings.GITHUB_OWNER}/{self._settings.GITHUB_REPO}"

    async def get_repository(self) -> dict[str, Any]:
        """Get repository information.

        Returns:
            Repository metadata dict.

        Raises:
            GitHubAuthenticationError: On auth failure.
            GitHubRepositoryNotFoundError: On 404.
        """
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
            response = await client.get(self._repo_url, headers=self._headers)

            if response.status_code == 401:
                raise GitHubAuthenticationError("GitHub authentication failed. Check GITHUB_TOKEN.")
            if response.status_code == 404:
                raise GitHubRepositoryNotFoundError(
                    f"Repository {self._settings.GITHUB_OWNER}/{self._settings.GITHUB_REPO} not found."
                )
            if response.status_code == 403:
                raise GitHubAuthenticationError("GitHub access denied. Check token permissions.")
            if response.status_code == 429:
                raise GitHubRateLimitError("GitHub API rate limit exceeded.")

            response.raise_for_status()
            return response.json()

    async def get_default_branch(self) -> str:
        """Get the default branch of the repository.

        Returns:
            Default branch name.
        """
        repo = await self.get_repository()
        return repo.get("default_branch", self._settings.GITHUB_DEFAULT_BRANCH)

    async def create_branch(
        self,
        branch_name: str,
        from_branch: str | None = None,
    ) -> dict[str, Any]:
        """Create a new branch from another branch.

        Args:
            branch_name: Name of the new branch.
            from_branch: Source branch (defaults to repo default).

        Returns:
            Git ref dict.

        Raises:
            GitHubBranchConflictError: If branch already exists.
        """
        if from_branch is None:
            from_branch = await self.get_default_branch()

        # Get the SHA of the source branch
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
            ref_url = f"{self._repo_url}/git/ref/heads/{from_branch}"
            response = await client.get(ref_url, headers=self._headers)

            if response.status_code == 404:
                # Branch doesn't exist, try creating from default
                ref_url = f"{self._repo_url}/git/ref/heads/{self._settings.GITHUB_DEFAULT_BRANCH}"
                response = await client.get(ref_url, headers=self._headers)
                response.raise_for_status()

            if response.status_code == 429:
                raise GitHubRateLimitError("GitHub API rate limit exceeded.")

            data = response.json()
            sha = data["object"]["sha"]

        # Create the new branch
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
            create_url = f"{self._repo_url}/git/refs"
            payload = {
                "ref": f"refs/heads/{branch_name}",
                "sha": sha,
            }
            response = await client.post(create_url, json=payload, headers=self._headers)

            if response.status_code == 422:
                # Branch might already exist — return existing
                logger.info("Branch %s already exists, using it", branch_name)
                return {"ref": f"refs/heads/{branch_name}", "object": {"sha": sha}}

            if response.status_code == 429:
                raise GitHubRateLimitError("GitHub API rate limit exceeded.")

            response.raise_for_status()
            return response.json()

    async def get_file(self, path: str, ref: str) -> dict[str, Any] | None:
        """Get a file from the repository.

        Args:
            path: File path in the repository.
            ref: Branch or commit SHA.

        Returns:
            File content dict or None if not found.
        """
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
            url = f"{self._repo_url}/contents/{path}"
            response = await client.get(url, headers=self._headers, params={"ref": ref})

            if response.status_code == 404:
                return None
            if response.status_code == 429:
                raise GitHubRateLimitError("GitHub API rate limit exceeded.")

            response.raise_for_status()
            return response.json()

    async def create_or_update_file(
        self,
        path: str,
        content: str,
        message: str,
        branch: str,
    ) -> dict[str, Any]:
        """Create or update a file in the repository.

        Uses the GitHub contents API with SHA for updates.

        Args:
            path: File path in the repository.
            content: File content (will be base64-encoded).
            message: Commit message.
            branch: Branch to commit to.

        Returns:
            Git commit dict.
        """
        # Check if file already exists
        existing = await self.get_file(path, branch)
        sha = existing.get("sha") if existing else None

        encoded_content = base64.b64encode(content.encode("utf-8")).decode("utf-8")

        payload: dict[str, Any] = {
            "message": message,
            "content": encoded_content,
            "branch": branch,
        }
        if sha:
            payload["sha"] = sha

        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
            url = f"{self._repo_url}/contents/{path}"
            response = await client.put(url, json=payload, headers=self._headers)

            if response.status_code == 429:
                raise GitHubRateLimitError("GitHub API rate limit exceeded.")

            response.raise_for_status()
            return response.json()
