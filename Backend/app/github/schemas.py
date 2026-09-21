"""Pydantic schemas for GitHub integration."""

from pydantic import BaseModel, Field


class GitHubPublishRequest(BaseModel):
    """Request to publish a report to GitHub."""

    force: bool = Field(
        default=False,
        description="Republish even if already published.",
    )


class GitHubPublishResponse(BaseModel):
    """Response for GitHub publication."""

    research_id: int
    status: str
    branch: str | None = None
    file_path: str | None = None
    commit_sha: str | None = None
    commit_url: str | None = None
    error: str | None = None


class GitHubConfigResponse(BaseModel):
    """Response for GitHub configuration status."""

    configured: bool
    owner: str
    repository: str
    default_branch: str
    branch_prefix: str
