"""ResearchRun model."""

import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class ResearchStatus(str, enum.Enum):
    """Status of a research run."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ReportStatus(str, enum.Enum):
    """Status of report generation."""
    PENDING = "pending"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"


class ResearchRun(Base):
    """A single research run covering a topic."""
    __tablename__ = "research_runs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    topic: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    status: Mapped[ResearchStatus] = mapped_column(
        Enum(ResearchStatus, name="research_status"),
        default=ResearchStatus.PENDING,
        nullable=False,
        index=True,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    report_path: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Report tracking (Phase 6)
    report_status: Mapped[ReportStatus | None] = mapped_column(
        Enum(ReportStatus, name="report_status"),
        default=ReportStatus.PENDING,
        nullable=True,
    )
    report_generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    report_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    sources: Mapped[list["ResearchSource"]] = relationship(
        "ResearchSource", back_populates="research_run", cascade="all, delete-orphan"
    )
    ideas: Mapped[list["Idea"]] = relationship(
        "Idea", back_populates="research_run", cascade="all, delete-orphan"
    )
    agent_runs: Mapped[list["AgentRun"]] = relationship(
        "AgentRun", back_populates="research_run", cascade="all, delete-orphan"
    )
    github_entries: Mapped[list["ResearchGitHub"]] = relationship(
        "ResearchGitHub", back_populates="research_run", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<ResearchRun id={self.id} topic={self.topic!r} status={self.status.value}>"
