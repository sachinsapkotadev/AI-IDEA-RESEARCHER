"""Web content extraction utilities."""

import logging
import re
from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from app.core.config import get_settings
from app.research.schemas import WebDocument

logger = logging.getLogger(__name__)

# Content limits
DEFAULT_TIMEOUT = 15.0
MAX_RESPONSE_SIZE = 5 * 1024 * 1024  # 5 MB
MAX_REDIRECTS = 5
MAX_TEXT_LENGTH = 50_000  # 50k characters per source

# Tags that usually contain non-content
_NOISE_TAGS = {
    "script", "style", "noscript", "iframe", "form", "nav", "footer",
    "header", "aside", "svg", "img", "video", "audio", "canvas",
}

# Common navigation-like phrases to filter out
_NAV_PATTERNS = re.compile(
    r"^(menu|navigation|skip to|cookie|privacy policy|terms of service|"
    r"sign up|log in|subscribe|newsletter|advertisement|sponsored|"
    r"share this|follow us|related articles|comments)\s*$",
    re.IGNORECASE,
)


def _is_allowed_content_type(content_type: str) -> bool:
    """Check if the content type is something we can parse."""
    if not content_type:
        return True  # Assume allowed if missing
    allowed = ("text/html", "text/plain", "application/xhtml")
    return any(t in content_type.lower() for t in allowed)


def _is_safe_ip(hostname: str) -> bool:
    """Reject private/local/loopback IPs to prevent SSRF."""
    if not hostname:
        return False

    blocked = {
        "localhost", "127.0.0.1", "0.0.0.0", "::1",
        "metadata.google.internal", "169.254.169.254",
    }
    if hostname.lower() in blocked:
        return False

    # Block private IP ranges
    private_patterns = [
        re.compile(r"^10\."),
        re.compile(r"^172\.(1[6-9]|2[0-9]|3[01])\."),
        re.compile(r"^192\.168\."),
        re.compile(r"^169\.254\."),
    ]
    for pattern in private_patterns:
        if pattern.match(hostname):
            return False

    return True


def extract_content(url: str) -> WebDocument:
    """Fetch a URL and extract readable text content.

    Features:
    - HTTP GET with timeout
    - User-Agent header
    - Content-type validation
    - Maximum response size
    - Redirect limit
    - HTML parsing and noise removal
    - SSRF protection

    Returns:
        WebDocument with extracted text or error status.
    """
    settings = get_settings()
    domain = urlparse(url).hostname or ""

    doc = WebDocument(url=url, domain=domain)

    # Safety checks
    if not _is_safe_ip(domain):
        doc.status = "skipped"
        doc.error = "Blocked: private/local IP address"
        logger.info("Content extraction skipped (private IP): %s", url[:100])
        return doc

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        doc.status = "skipped"
        doc.error = f"Blocked: unsupported scheme '{parsed.scheme}'"
        return doc

    try:
        user_agent = getattr(settings, "SEARCH_USER_AGENT", None) or (
            "AI-Idea-Researcher/1.0 (+https://ai-idea-researcher.local)"
        )

        with httpx.Client(
            timeout=DEFAULT_TIMEOUT,
            max_redirects=MAX_REDIRECTS,
            follow_redirects=True,
        ) as client:
            response = client.get(
                url,
                headers={"User-Agent": user_agent},
            )

            # Check content type
            content_type = response.headers.get("content-type", "")
            if not _is_allowed_content_type(content_type):
                doc.status = "skipped"
                doc.error = f"Unsupported content type: {content_type}"
                return doc

            # Check size
            if len(response.content) > MAX_RESPONSE_SIZE:
                doc.status = "skipped"
                doc.error = "Response too large"
                return doc

            response.raise_for_status()

            doc.content_type = content_type

        # Parse HTML
        html = response.text
        soup = BeautifulSoup(html, "html.parser")

        # Extract title
        title_tag = soup.find("title")
        doc.title = title_tag.get_text(strip=True) if title_tag else ""

        # Remove noise elements
        for tag in soup.find_all(_NOISE_TAGS):
            tag.decompose()

        # Extract text
        text = soup.get_text(separator="\n", strip=True)

        # Clean up whitespace
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        # Remove navigation-like lines
        lines = [line for line in lines if not _NAV_PATTERNS.match(line)]
        text = "\n".join(lines)

        # Truncate if too long
        if len(text) > MAX_TEXT_LENGTH:
            text = text[:MAX_TEXT_LENGTH] + "\n[...truncated]"

        doc.text = text
        doc.word_count = len(text.split())
        doc.retrieved_at = datetime.now(timezone.utc)
        doc.status = "success"

        logger.info(
            "Content extracted: %s | words=%d | chars=%d",
            domain, doc.word_count, len(text),
        )

    except httpx.TimeoutException:
        doc.status = "failed"
        doc.error = "Request timed out"
        logger.warning("Content extraction timeout: %s", url[:100])
    except httpx.TooManyRedirects:
        doc.status = "failed"
        doc.error = "Too many redirects"
        logger.warning("Content extraction redirect limit: %s", url[:100])
    except httpx.HTTPStatusError as exc:
        doc.status = "failed"
        doc.error = f"HTTP {exc.response.status_code}"
        logger.warning("Content extraction HTTP error %d: %s", exc.response.status_code, url[:100])
    except Exception as exc:
        doc.status = "failed"
        doc.error = f"Extraction error: {type(exc).__name__}"
        logger.warning("Content extraction error: %s | %s", type(exc).__name__, url[:100])

    return doc
