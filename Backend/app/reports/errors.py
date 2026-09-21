"""Report generation error types."""


class ReportError(Exception):
    """Base class for report-related errors."""


class ReportGenerationError(ReportError):
    """Raised when report generation fails."""


class ReportNotFoundError(ReportError):
    """Raised when a requested report does not exist."""


class ReportAlreadyExistsError(ReportError):
    """Raised when trying to generate a report that already exists."""
