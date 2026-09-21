"""Report service — orchestrates report generation and file storage."""

import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database.models.research import ReportStatus, ResearchRun
from app.reports.errors import ReportGenerationError, ReportNotFoundError
from app.reports.generator import ReportGenerator

logger = logging.getLogger(__name__)


class ReportService:
    """Orchestrates report generation and file storage.

    Responsibilities:
    - Check if report already exists (idempotency)
    - Generate Markdown report from research data
    - Store report in predictable directory structure
    - Update ResearchRun with report metadata
    """

    def __init__(self, generator: ReportGenerator | None = None) -> None:
        self._generator = generator or ReportGenerator()
        self._settings = get_settings()

    def generate_report(
        self,
        research_id: int,
        db: Session,
        force: bool = False,
    ) -> dict:
        """Generate a Markdown report for a completed research run.

        Args:
            research_id: ID of the ResearchRun.
            db: Database session.
            force: If True, regenerate even if report exists.

        Returns:
            Dict with report metadata.

        Raises:
            ReportNotFoundError: If research run not found.
            ReportGenerationError: If generation fails.
        """
        run = db.query(ResearchRun).filter(ResearchRun.id == research_id).first()
        if not run:
            raise ReportNotFoundError(f"ResearchRun {research_id} not found")

        # Check idempotency
        if (
            not force
            and run.report_status == ReportStatus.COMPLETED
            and run.report_path
            and os.path.exists(run.report_path)
        ):
            logger.info(
                "Report already exists | research_id=%d | path=%s",
                research_id, run.report_path,
            )
            return {
                "research_id": research_id,
                "report_status": "completed",
                "report_path": run.report_path,
                "report_generated_at": (
                    run.report_generated_at.isoformat() if run.report_generated_at else None
                ),
            }

        # Mark as generating
        run.report_status = ReportStatus.GENERATING
        db.flush()

        try:
            # Generate content
            content = self._generator.generate(run, db)
            markdown = self._generator.render_markdown(content)

            if not markdown or len(markdown.strip()) < 50:
                raise ReportGenerationError("Generated report is too short or empty.")

            # Build file path
            report_path = self._build_report_path(research_id, content.metadata.date)

            # Write file
            os.makedirs(os.path.dirname(report_path), exist_ok=True)
            with open(report_path, "w", encoding="utf-8") as f:
                f.write(markdown)

            # Verify file was written
            if not os.path.exists(report_path) or os.path.getsize(report_path) == 0:
                raise ReportGenerationError(f"Failed to write report to {report_path}")

            # Update research run
            now = datetime.now(timezone.utc)
            run.report_path = report_path
            run.report_status = ReportStatus.COMPLETED
            run.report_generated_at = now
            run.report_error = None
            db.flush()
            db.commit()

            logger.info(
                "Report generated | research_id=%d | path=%s | size=%d",
                research_id, report_path, os.path.getsize(report_path),
            )

            return {
                "research_id": research_id,
                "report_status": "completed",
                "report_path": report_path,
                "report_generated_at": now.isoformat(),
            }

        except Exception as exc:
            run.report_status = ReportStatus.FAILED
            run.report_error = str(exc)[:2000]
            db.flush()
            db.commit()

            logger.exception(
                "Report generation failed | research_id=%d",
                research_id,
            )
            raise ReportGenerationError(f"Report generation failed: {exc}") from exc

    def get_report_content(
        self,
        research_id: int,
        db: Session,
    ) -> dict:
        """Get the content of an existing report.

        Args:
            research_id: ID of the ResearchRun.
            db: Database session.

        Returns:
            Dict with report content and metadata.
        """
        run = db.query(ResearchRun).filter(ResearchRun.id == research_id).first()
        if not run:
            raise ReportNotFoundError(f"ResearchRun {research_id} not found")

        if not run.report_path or not os.path.exists(run.report_path):
            return {
                "research_id": research_id,
                "report_status": run.report_status.value if run.report_status else "pending",
                "content": None,
                "report_path": run.report_path,
            }

        with open(run.report_path, "r", encoding="utf-8") as f:
            content = f.read()

        return {
            "research_id": research_id,
            "report_status": run.report_status.value if run.report_status else "pending",
            "content": content,
            "report_path": run.report_path,
        }

    def _build_report_path(self, research_id: int, date_str: str) -> str:
        """Build a predictable report file path.

        Pattern: {REPORTS_DIR}/YYYY/MM/YYYY-MM-DD/research-{id}.md
        """
        reports_dir = self._settings.REPORTS_DIR
        now = datetime.now(timezone.utc)
        path = os.path.join(
            reports_dir,
            str(now.year),
            f"{now.month:02d}",
            date_str,
            f"research-{research_id}.md",
        )
        # Normalize and verify path stays within reports_dir
        normalized = os.path.normpath(path)
        reports_normalized = os.path.normpath(reports_dir)
        if not normalized.startswith(reports_normalized):
            raise ReportGenerationError("Report path escape detected.")
        return normalized
