"""Utility functions for building compact source contexts for agents."""

from app.database.models.source import ResearchSource


def build_source_context(
    sources: list[ResearchSource],
    max_chars: int = 30_000,
) -> str:
    """Build a compact source context string for agent prompts.

    Args:
        sources: List of ResearchSource records.
        max_chars: Maximum total characters.

    Returns:
        Formatted source context string.
    """
    parts: list[str] = []
    total_chars = 0

    for idx, source in enumerate(sources):
        source_id = f"S{idx + 1}"
        # Use snippet if no content, truncate content to save tokens
        content = source.content or source.snippet or ""
        if len(content) > 3000:
            content = content[:3000] + "\n[...truncated]"

        block = (
            f"[{source_id}] {source.title}\n"
            f"URL: {source.url}\n"
            f"Domain: {source.domain or 'unknown'}\n"
            f"Content: {content}\n"
        )

        if total_chars + len(block) > max_chars:
            break

        parts.append(block)
        total_chars += len(block)

    return "\n---\n".join(parts)


def build_source_references(sources: list[ResearchSource]) -> str:
    """Build compact source reference list for agent prompts.

    Args:
        sources: List of ResearchSource records.

    Returns:
        Formatted reference string.
    """
    lines: list[str] = []
    for idx, source in enumerate(sources):
        source_id = f"S{idx + 1}"
        lines.append(
            f"[{source_id}] {source.title} — {source.url} ({source.quality or 'unknown'})"
        )
    return "\n".join(lines)


def truncate_text(text: str | None, max_length: int = 5000) -> str:
    """Truncate text to max length, adding marker if needed."""
    if not text:
        return ""
    if len(text) <= max_length:
        return text
    return text[:max_length] + "\n[...truncated]"
