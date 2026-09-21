"""GitHub service — orchestrates report publication to GitHub."""

import logging
import os
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database.models.github import GitHubPublishStatus, ResearchGitHub
from app.database.models.research import ReportStatus, ResearchRun
from app.github.client import GitHubClient
from app.github.errors import (
    GitHubAuthenticationError,
    GitHubConfigurationError,
    GitHubError,
    GitHubPublicationError,
    GitHubRepositoryNotFoundError,
)
from app.reports.errors import ReportNotFoundError

logger = logging.getLogger(__name__)


class GitHubService:
    """Orchestrates report publication to GitHub.

    Workflow:
    1. Verify report exists and is non-empty
    2. Verify report belongs to the current ResearchRun
    3. Create or locate research branch
    4. Add/update only the report file
    5. Create commit
    6. Record GitHub metadata
    7. Return success only if GitHub actually confirms
    """

    def __init__(self, client: GitHubClient | None = None) -> None:
        self._client = client
        self._settings = get_settings()

    def _get_client(self) -> GitHubClient:
        """Lazy-initialize the GitHub client."""
        if self._client is None:
            self._client = GitHubClient()
        return self._client

    def is_configured(self) -> bool:
        """Check if GitHub integration is configured."""
        return bool(
            self._settings.GITHUB_TOKEN
            and self._settings.GITHUB_OWNER
            and self._settings.GITHUB_REPO
        )

    async def publish_report(
        self,
        research_id: int,
        db: Session,
        force: bool = False,
    ) -> dict:
        """Publish a research report to a GitHub branch.

        Args:
            research_id: ID of the ResearchRun.
            db: Database session.
            force: If True, republish even if already published.

        Returns:
            Dict with publication metadata.

        Raises:
            ReportNotFoundError: If research run not found.
            GitHubConfigurationError: If GitHub not configured.
            GitHubPublicationError: On publication failure.
        """
        if not self.is_configured():
            raise GitHubConfigurationError(
                "GitHub is not configured. Set GITHUB_TOKEN, GITHUB_OWNER, and GITHUB_REPO."
            )

        run = db.query(ResearchRun).filter(ResearchRun.id == research_id).first()
        if not run:
            raise ReportNotFoundError(f"ResearchRun {research_id} not found")

        # Verify report exists
        if not run.report_path or not os.path.exists(run.report_path):
            raise GitHubPublicationError(
                "No report file exists. Generate a report first via POST /api/research/{id}/report."
            )

        # Read report content
        with open(run.report_path, "r", encoding="utf-8") as f:
            report_content = f.read()

        if not report_content or len(report_content.strip()) < 50:
            raise GitHubPublicationError("Report file is empty or too short.")

        # Check idempotency — already published?
        existing = (
            db.query(ResearchGitHub)
            .filter(
                ResearchGitHub.research_run_id == research_id,
                ResearchGitHub.status == GitHubPublishStatus.COMPLETED,
            )
            .first()
        )
        if existing and not force:
            logger.info(
                "Report already published | research_id=%d | branch=%s | sha=%s",
                research_id, existing.branch, existing.commit_sha,
            )
            return {
                "research_id": research_id,
                "status": "completed",
                "branch": existing.branch,
                "file_path": existing.file_path,
                "commit_sha": existing.commit_sha,
                "commit_url": existing.commit_url,
            }

        client = self._get_client()

        try:
            # Create GitHub record
            gh_entry = ResearchGitHub(
                research_run_id=research_id,
                provider="github",
                owner=self._settings.GITHUB_OWNER,
                repository=self._settings.GITHUB_REPO,
                status=GitHubPublishStatus.PUBLISHING,
            )
            db.add(gh_entry)
            db.flush()

            # Determine branch name
            now = datetime.now(timezone.utc)
            branch_prefix = self._settings.GITHUB_RESEARCH_BRANCH_PREFIX.rstrip("/")
            branch_name = f"{branch_prefix}/{now.strftime('%Y-%m-%d')}"

            # Ensure branch exists
            try:
                await client.create_branch(branch_name)
            except Exception as exc:
                logger.warning("Branch creation note: %s", exc)

            gh_entry.branch = branch_name

            # File path in repo
            file_path = f"reports/{now.year}/{now.month:02d}/{now.strftime('%Y-%m-%d')}/research-{research_id}.md"
            gh_entry.file_path = file_path

            # Commit message
            commit_message = f"research: add report {now.strftime('%Y-%m-%d')} (research-{research_id})"

            # Create/update file
            result = await client.create_or_update_file(
                path=file_path,
                content=report_content,
                message=commit_message,
                branch=branch_name,
            )

            # Extract commit info
            commit_data = result.get("commit", {})
            gh_entry.commit_sha = commit_data.get("sha")
            gh_entry.commit_url = commit_data.get("html_url")
            gh_entry.status = GitHubPublishStatus.COMPLETED

            db.flush()
            db.commit()

            logger.info(
                "Report published to GitHub | research_id=%d | branch=%s | file=%s | sha=%s",
                research_id, branch_name, file_path, gh_entry.commit_sha,
            )

            return {
                "research_id": research_id,
                "status": "completed",
                "branch": branch_name,
                "file_path": file_path,
                "commit_sha": gh_entry.commit_sha,
                "commit_url": gh_entry.commit_url,
            }

        except (GitHubAuthenticationError, GitHubRepositoryNotFoundError) as exc:
            gh_entry.status = GitHubPublishStatus.FAILED
            gh_entry.error_message = str(exc)[:2000]
            db.flush()
            db.commit()
            raise

        except GitHubError as exc:
            gh_entry.status = GitHubPublishStatus.FAILED
            gh_entry.error_message = str(exc)[:2000]
            db.flush()
            db.commit()
            raise GitHubPublicationError(f"GitHub publication failed: {exc}") from exc

        except Exception as exc:
            if gh_entry:
                gh_entry.status = GitHubPublishStatus.FAILED
                gh_entry.error_message = f"Unexpected error: {type(exc).__name__}: {exc}"[:2000]
                db.flush()
                db.commit()
            logger.exception("GitHub publication failed | research_id=%d", research_id)
            raise GitHubPublicationError(f"GitHub publication failed: {exc}") from exc

    async def get_publication_status(
        self,
        research_id: int,
        db: Session,
    ) -> dict | None:
        """Get the GitHub publication status for a research run.

        Returns:
            Publication metadata dict or None if not published.
        """
        entry = (
            db.query(ResearchGitHub)
            .filter(ResearchGitHub.research_run_id == research_id)
            .order_by(ResearchGitHub.created_at.desc())
            .first()
        )
        if not entry:
            return None

        return {
            "research_id": research_id,
            "status": entry.status.value,
            "branch": entry.branch,
            "file_path": entry.file_path,
            "commit_sha": entry.commit_sha,
            "commit_url": entry.commit_url,
            "error": entry.error_message,
            "created_at": entry.created_at.isoformat() if entry.created_at else None,
        }
