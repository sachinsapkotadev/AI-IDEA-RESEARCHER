"""URL normalization and deduplication utilities."""

import re
from urllib.parse import parse_qs, urlparse, urlunparse

# Tracking parameters commonly added to URLs that don't affect content
_TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "fbclid", "gclid", "mc_cid", "mc_eid",
    "ref", "source", "via", "share",
}


def normalize_url(url: str) -> str:
    """Normalize a URL to reduce duplicate representations.

    Handles:
    - Trailing slash removal on paths
    - Case normalization of scheme and host
    - Removal of common tracking parameters
    - Fragment removal

    Does NOT:
    - Follow redirects
    - Rewrite URLs aggressively
    - Change actual destinations
    """
    try:
        parsed = urlparse(url)
    except Exception:
        return url

    # Normalize scheme and host
    scheme = parsed.scheme.lower()
    hostname = parsed.hostname.lower() if parsed.hostname else ""

    # Rebuild netloc with optional port
    netloc = hostname
    if parsed.port and parsed.port not in (80, 443):
        netloc = f"{hostname}:{parsed.port}"

    # Normalize path
    path = parsed.path
    # Remove trailing slash (except root)
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")

    # Filter tracking parameters
    query_params = parse_qs(parsed.query, keep_blank_values=False)
    filtered_params = {
        k: v for k, v in query_params.items()
        if k.lower() not in _TRACKING_PARAMS
    }

    # Rebuild query string
    query_parts = []
    for k, v in sorted(filtered_params.items()):
        for val in v:
            query_parts.append(f"{k}={val}")
    query = "&".join(query_parts)

    # Reconstruct URL without fragment
    normalized = urlunparse((scheme, netloc, path, parsed.params, query, ""))
    return normalized


def deduplicate_urls(urls: list[str]) -> list[str]:
    """Remove duplicate URLs after normalization.

    Preserves the order of first occurrence.
    """
    seen: set[str] = set()
    result: list[str] = []
    for url in urls:
        normalized = normalize_url(url)
        if normalized not in seen:
            seen.add(normalized)
            result.append(url)  # Keep original URL
    return result


def extract_domain(url: str) -> str:
    """Extract the domain from a URL."""
    try:
        parsed = urlparse(url)
        return parsed.hostname or ""
    except Exception:
        return ""
