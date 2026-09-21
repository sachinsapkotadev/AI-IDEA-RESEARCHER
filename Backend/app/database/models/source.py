"""ResearchSource model."""

import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class SourceType(str, enum.Enum):
    """Type of research source."""
    WEB = "web"
    ACADEMIC = "academic"
    NEWS = "news"
    GITHUB = "github"
    OTHER = "other"


class SourceStatus(str, enum.Enum):
    """Status of source content retrieval."""
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class ResearchSource(Base):
    """A source used during a research run."""
    __tablename__ = "research_sources"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    research_run_id: Mapped[int] = mapped_column(
        ForeignKey("research_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_type: Mapped[SourceType] = mapped_column(
        Enum(SourceType, name="source_type"), default=SourceType.WEB, nullable=False
    )
    domain: Mapped[str | None] = mapped_column(String(200), nullable=True)
    snippet: Mapped[str | None] = mapped_column(Text, nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    quality: Mapped[str | None] = mapped_column(String(50), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retrieved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[SourceStatus] = mapped_column(
        Enum(SourceStatus, name="source_status"),
        default=SourceStatus.SUCCESS,
        nullable=False,
    )
    word_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationship
    research_run: Mapped["ResearchRun"] = relationship("ResearchRun", back_populates="sources")

    def __repr__(self) -> str:
        return f"<ResearchSource id={self.id} title={self.title!r}>"
