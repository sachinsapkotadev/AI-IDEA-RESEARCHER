"""Build optimized research context for AI analysis."""

import logging

from app.core.config import get_settings
from app.research.schemas import (
    ResearchContext,
    SearchResult,
    WebDocument,
)
from app.research.normalizer import extract_domain
from app.research.quality import classify_source

logger = logging.getLogger(__name__)


def _estimate_chars(text: str) -> int:
    """Estimate character count for context budgeting."""
    return len(text)


def build_research_context(
    topic: str,
    search_results: list[SearchResult],
    documents: list[WebDocument],
) -> ResearchContext:
    """Build an optimized research context for the AI agent.

    Performs:
    1. Filters to successful documents only
    2. Prioritizes by source quality
    3. Truncates oversized sources
    4. Caps total context size
    5. Builds source reference list

    Returns:
        ResearchContext with optimized content for AI consumption.
    """
    settings = get_settings()
    max_total = getattr(settings, "MAX_TOTAL_RESEARCH_CONTEXT", 100_000)

    # Filter to successful documents
    successful_docs = [d for d in documents if d.status == "success" and d.text]

    # Build quality scores for prioritization
    doc_priorities: list[tuple[int, WebDocument]] = []
    quality_order = {
        "official": 0,
        "documentation": 1,
        "news": 2,
        "community": 3,
        "blog": 4,
        "unknown": 5,
    }

    for doc in successful_docs:
        quality = classify_source(doc.url)
        priority = quality_order.get(quality.value, 5)
        doc_priorities.append((priority, doc))

    # Sort by quality (lower = higher priority)
    doc_priorities.sort(key=lambda x: x[0])

    # Build source references and allocate context budget
    source_refs: list[dict] = []
    total_chars = 0
    docs_used: list[WebDocument] = []

    for idx, (priority, doc) in enumerate(doc_priorities):
        source_id = f"S{idx + 1}"
        quality = classify_source(doc.url)

        source_refs.append({
            "id": source_id,
            "title": doc.title or doc.domain,
            "url": doc.url,
            "quality": quality.value,
        })

        # Check budget
        doc_chars = _estimate_chars(doc.text)
        if total_chars + doc_chars > max_total:
            # Truncate to fit
            remaining = max_total - total_chars
            if remaining > 500:
                doc.text = doc.text[:remaining] + "\n[...truncated to fit context limit]"
                doc.word_count = len(doc.text.split())
                total_chars += remaining
                docs_used.append(doc)
            logger.info(
                "Context budget reached at source %s | total=%d/%d",
                source_id, total_chars, max_total,
            )
            break

        total_chars += doc_chars
        docs_used.append(doc)

    context = ResearchContext(
        topic=topic,
        search_results=search_results,
        documents=docs_used,
        source_count=len(search_results),
        documents_fetched=len(successful_docs),
        documents_failed=len(documents) - len(successful_docs),
        characters_sent=total_chars,
        source_references=source_refs,
    )

    logger.info(
        "Research context built | sources=%d | docs=%d | chars=%d",
        context.source_count,
        context.documents_fetched,
        context.characters_sent,
    )

    return context
