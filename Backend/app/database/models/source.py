"""ResearchSource model."""

import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class SourceType(str, enum.Enum):
    """Type of research source."""
    WEB = "web"
    ACADEMIC = "academic"
    NEWS = "news"
    GITHUB = "github"
    OTHER = "other"


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
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationship
    research_run: Mapped["ResearchRun"] = relationship("ResearchRun", back_populates="sources")

    def __repr__(self) -> str:
        return f"<ResearchSource id={self.id} title={self.title!r}>"
