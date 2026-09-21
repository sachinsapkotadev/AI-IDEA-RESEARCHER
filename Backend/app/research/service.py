"""Research pipeline service — orchestrates the full research flow."""

import logging
import time
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.ai.errors import AIError
from app.ai.prompts import RESEARCH_PROMPT_TEMPLATE, SYSTEM_PROMPT
from app.ai.provider import OpenRouterProvider, _extract_json_from_response
from app.ai.schemas import ResearchResult
from app.core.config import get_settings
from app.database.models.agent_run import AgentRun, AgentRunStatus
from app.database.models.research import ResearchRun, ResearchStatus
from app.database.models.source import ResearchSource, SourceStatus, SourceType
from app.research.context_builder import build_research_context
from app.research.errors import NoUsableSourcesError, SearchProviderError
from app.research.extractor import extract_content
from app.research.normalizer import deduplicate_urls, extract_domain, normalize_url
from app.research.quality import classify_source
from app.research.schemas import ResearchContext, ResearchMetrics
from app.research.sources.base import SearchProvider
from app.research.sources.google_search import GoogleSearchProvider

logger = logging.getLogger(__name__)


class ResearchService:
    """Orchestrates the full research pipeline.

    Pipeline:
    1. Create ResearchRun
    2. Search topic
    3. Normalize results
    4. Deduplicate
    5. Fetch selected pages
    6. Extract readable content
    7. Save ResearchSource records
    8. Build research context
    9. Send context to Research Agent
    10. Validate AI result
    11. Save final research result
    12. Update ResearchRun status
    """

    def __init__(
        self,
        search_provider: SearchProvider | None = None,
        ai_provider: OpenRouterProvider | None = None,
    ) -> None:
        self._search = search_provider or GoogleSearchProvider()
        self._ai = ai_provider or OpenRouterProvider()
        self._settings = get_settings()

    async def run(self, research_run: ResearchRun, db: Session) -> ResearchResult:
        """Execute the full research pipeline.

        Args:
            research_run: The ResearchRun instance with a topic.
            db: Database session.

        Returns:
            Validated ResearchResult.

        Raises:
            AIError: On AI-related failures.
            SearchProviderError: On search failures.
            NoUsableSourcesError: When no usable sources found.
        """
        topic = research_run.topic
        start_time = time.time()

        resolved_model = self._ai._resolve_model(None, "ResearchPipeline")
        logger.info("Research pipeline started | topic=%s | model=%s", topic[:80], resolved_model)

        # Update status
        research_run.status = ResearchStatus.RUNNING
        research_run.started_at = datetime.now(timezone.utc)
        db.flush()

        # Create agent run record
        agent_run = AgentRun(
            research_run_id=research_run.id,
            agent_name="ResearchPipeline",
            model=resolved_model,
            status=AgentRunStatus.RUNNING,
            started_at=datetime.now(timezone.utc),
        )
        db.add(agent_run)
        db.flush()

        metrics = ResearchMetrics()

        try:
            # Step 1: Search
            logger.info("Step 1: Searching | topic=%s", topic[:60])
            max_results = self._settings.MAX_SEARCH_RESULTS
            search_results = await self._search.search(
                query=topic,
                max_results=max_results,
            )
            metrics.sources_found = len(search_results)
            logger.info("Search complete | results=%d", len(search_results))

            if not search_results:
                raise NoUsableSourcesError(
                    "No search results returned for this topic."
                )

            # Step 2: Normalize and deduplicate
            logger.info("Step 2: Normalizing URLs")
            urls = [r.url for r in search_results]
            unique_urls = deduplicate_urls(urls)

            # Filter search results to unique URLs
            seen_normalized: set[str] = set()
            unique_results = []
            for result in search_results:
                norm = normalize_url(result.url)
                if norm not in seen_normalized:
                    seen_normalized.add(norm)
                    unique_results.append(result)
            search_results = unique_results

            # Step 3: Fetch and extract content
            logger.info("Step 3: Fetching content | urls=%d", len(search_results))
            max_sources = self._settings.MAX_SOURCES_PER_RESEARCH
            documents = []
            for result in search_results[:max_sources]:
                doc = extract_content(result.url)
                documents.append(doc)
                if doc.status == "success":
                    metrics.documents_fetched += 1
                else:
                    metrics.documents_failed += 1

            logger.info(
                "Content extraction done | fetched=%d | failed=%d",
                metrics.documents_fetched,
                metrics.documents_failed,
            )

            # Step 4: Save sources to database
            logger.info("Step 4: Saving sources to database")
            for idx, result in enumerate(search_results[:max_sources]):
                doc = documents[idx] if idx < len(documents) else None
                quality = classify_source(result.url)

                source = ResearchSource(
                    research_run_id=research_run.id,
                    title=result.title,
                    url=result.url,
                    source_type=SourceType.WEB,
                    domain=result.source_domain or extract_domain(result.url),
                    snippet=result.snippet,
                    content=doc.text if doc and doc.status == "success" else None,
                    quality=quality.value,
                    published_at=result.published_at,
                    retrieved_at=doc.retrieved_at if doc else None,
                    status=SourceStatus(doc.status) if doc else SourceStatus.SKIPPED,
                    word_count=doc.word_count if doc else 0,
                    rank=result.rank,
                )
                db.add(source)
            db.flush()

            # Step 5: Build research context
            logger.info("Step 5: Building research context")
            context = build_research_context(
                topic=topic,
                search_results=search_results[:max_sources],
                documents=documents,
            )

            # Check if we have any usable sources
            if not context.documents:
                raise NoUsableSourcesError(
                    "No usable source content was extracted."
                )

            metrics.sources_used = context.documents_fetched
            metrics.characters_sent = context.characters_sent

            # Step 6: Send to AI
            logger.info(
                "Step 6: AI analysis | sources=%d | chars=%d",
                context.documents_fetched,
                context.characters_sent,
            )
            source_material = _format_source_material(context)
            source_refs = _format_source_references(context)

            prompt = RESEARCH_PROMPT_TEMPLATE.format(
                topic=topic,
                source_material=source_material,
                source_references=source_refs,
            )

            response = await self._ai.generate(
                prompt=prompt,
                system_prompt=SYSTEM_PROMPT,
                agent_name="ResearchPipeline",
            )

            # Parse and validate
            raw_json = _extract_json_from_response(response.content)
            result = ResearchResult.model_validate(raw_json)

            # Update agent run
            agent_run.status = AgentRunStatus.COMPLETED
            agent_run.completed_at = datetime.now(timezone.utc)
            agent_run.input_tokens = response.usage.input_tokens
            agent_run.output_tokens = response.usage.output_tokens
            agent_run.provider_key_slot = response.key_slot

            # Update research run
            research_run.status = ResearchStatus.COMPLETED
            research_run.completed_at = datetime.now(timezone.utc)
            research_run.report_path = result.model_dump_json()

            elapsed = time.time() - start_time
            metrics.duration_seconds = elapsed

            logger.info(
                "Research pipeline completed | topic=%s | model=%s | key_slot=%s | "
                "duration=%.1fs | sources=%d | docs=%d | chars=%d",
                topic[:60],
                resolved_model,
                response.key_slot,
                elapsed,
                metrics.sources_found,
                metrics.documents_fetched,
                metrics.characters_sent,
            )

            db.commit()
            db.refresh(research_run)

            return result

        except (NoUsableSourcesError, SearchProviderError) as exc:
            research_run.status = ResearchStatus.FAILED
            research_run.completed_at = datetime.now(timezone.utc)
            agent_run.status = AgentRunStatus.FAILED
            agent_run.completed_at = datetime.now(timezone.utc)
            agent_run.error_message = str(exc)
            db.commit()

            elapsed = time.time() - start_time
            logger.warning(
                "Research pipeline failed | topic=%s | error=%s | duration=%.1fs",
                topic[:60], type(exc).__name__, elapsed,
            )
            raise

        except AIError as exc:
            research_run.status = ResearchStatus.FAILED
            research_run.completed_at = datetime.now(timezone.utc)
            agent_run.status = AgentRunStatus.FAILED
            agent_run.completed_at = datetime.now(timezone.utc)
            agent_run.error_message = str(exc)
            db.commit()

            elapsed = time.time() - start_time
            logger.warning(
                "Research pipeline AI error | topic=%s | error=%s | duration=%.1fs",
                topic[:60], type(exc).__name__, elapsed,
            )
            raise

        except Exception as exc:
            research_run.status = ResearchStatus.FAILED
            research_run.completed_at = datetime.now(timezone.utc)
            agent_run.status = AgentRunStatus.FAILED
            agent_run.completed_at = datetime.now(timezone.utc)
            agent_run.error_message = f"Unexpected error: {type(exc).__name__}"
            db.commit()

            elapsed = time.time() - start_time
            logger.exception(
                "Research pipeline unexpected error | topic=%s | duration=%.1fs",
                topic[:60], elapsed,
            )
            raise


def _format_source_material(context: ResearchContext) -> str:
    """Format document content for the AI prompt."""
    parts: list[str] = []
    for idx, doc in enumerate(context.documents):
        source_id = f"S{idx + 1}"
        parts.append(
            f"[{source_id}] {doc.title or doc.domain}\n"
            f"URL: {doc.url}\n"
            f"{doc.text}\n"
        )
    return "\n---\n".join(parts)


def _format_source_references(context: ResearchContext) -> str:
    """Format source references for the AI prompt."""
    lines: list[str] = []
    for ref in context.source_references:
        lines.append(f"[{ref['id']}] {ref['title']} — {ref['url']} ({ref['quality']})")
    return "\n".join(lines)
