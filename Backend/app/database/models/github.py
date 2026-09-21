"""ResearchGitHub model — tracks GitHub publication of research reports."""

import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class GitHubPublishStatus(str, enum.Enum):
    """Status of GitHub publication."""
    PENDING = "pending"
    PUBLISHING = "publishing"
    COMPLETED = "completed"
    FAILED = "failed"


class ResearchGitHub(Base):
    """Tracks GitHub publication of a research report."""
    __tablename__ = "research_github"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    research_run_id: Mapped[int] = mapped_column(
        ForeignKey("research_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(50), default="github", nullable=False)
    owner: Mapped[str] = mapped_column(String(200), nullable=False)
    repository: Mapped[str] = mapped_column(String(200), nullable=False)
    branch: Mapped[str] = mapped_column(String(200), nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    commit_sha: Mapped[str | None] = mapped_column(String(40), nullable=True)
    commit_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[GitHubPublishStatus] = mapped_column(
        Enum(GitHubPublishStatus, name="github_publish_status"),
        default=GitHubPublishStatus.PENDING,
        nullable=False,
        index=True,
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationship
    research_run: Mapped["ResearchRun"] = relationship("ResearchRun", back_populates="github_entries")

    def __repr__(self) -> str:
        return f"<ResearchGitHub id={self.id} branch={self.branch!r} status={self.status.value}>"
