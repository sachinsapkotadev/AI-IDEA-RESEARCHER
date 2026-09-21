"""Idea model."""

import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class IdeaStatus(str, enum.Enum):
    """Lifecycle status of an idea."""
    NEW = "new"
    REVIEWING = "reviewing"
    VALIDATED = "validated"
    REJECTED = "rejected"
    BUILT = "built"


class Idea(Base):
    """An idea generated from research."""
    __tablename__ = "ideas"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    research_run_id: Mapped[int] = mapped_column(
        ForeignKey("research_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    problem: Mapped[str | None] = mapped_column(Text, nullable=True)
    solution: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_users: Mapped[str | None] = mapped_column(Text, nullable=True)
    mvp: Mapped[str | None] = mapped_column(Text, nullable=True)
    monetization: Mapped[str | None] = mapped_column(Text, nullable=True)
    competition: Mapped[str | None] = mapped_column(Text, nullable=True)
    differentiation: Mapped[str | None] = mapped_column(Text, nullable=True)
    technical_complexity: Mapped[str | None] = mapped_column(Text, nullable=True)
    risks: Mapped[str | None] = mapped_column(Text, nullable=True)
    validation_plan: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[IdeaStatus] = mapped_column(
        Enum(IdeaStatus, name="idea_status"),
        default=IdeaStatus.NEW,
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationship
    research_run: Mapped["ResearchRun"] = relationship("ResearchRun", back_populates="ideas")

    def __repr__(self) -> str:
        return f"<Idea id={self.id} title={self.title!r} status={self.status.value}>"
