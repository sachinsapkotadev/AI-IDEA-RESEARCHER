"""Source quality classification."""

from urllib.parse import urlparse

from app.research.schemas import SourceQuality

# Domain patterns for quality classification
_OFFICIAL_TLDS = {".gov", ".edu", ".org"}
_OFFICIAL_DOMAINS = {
    "github.com", "gitlab.com", "bitbucket.org",
    "stackoverflow.com", "stackexchange.com",
}

_NEWS_DOMAINS = {
    "reuters.com", "apnews.com", "bbc.com", "bbc.co.uk",
    "nytimes.com", "washingtonpost.com", "theguardian.com",
    "bloomberg.com", "cnbc.com", "wsj.com", "ft.com",
    "techcrunch.com", "theverge.com", "arstechnica.com",
    "wired.com", "venturebeat.com", "thenextweb.com",
    "zdnet.com", "cnet.com", "engadget.com",
}

_DOCS_DOMAINS = {
    "docs.python.org", "developer.mozilla.org", "docs.microsoft.com",
    "learn.microsoft.com", "cloud.google.com", "aws.amazon.com",
    "docs.aws.amazon.com", "developer.apple.com", "reactjs.org",
    "nextjs.org", "vuejs.org", "angular.io", "svelte.dev",
    "fastapi.tiangolo.com", "flask.palletsprojects.com",
    "docs.sqlalchemy.org", "www.postgresql.org/docs/",
}

_COMMUNITY_DOMAINS = {
    "reddit.com", "news.ycombinator.com", "discourse.org",
    "stackoverflow.com", "stackexchange.com", "quora.com",
    "medium.com", "dev.to", "hashnode.com",
}


def classify_source(url: str) -> SourceQuality:
    """Classify a source URL into a quality category.

    This is a basic heuristic classification, NOT a credibility score.
    It categorizes the type of source for context purposes.
    """
    try:
        parsed = urlparse(url)
        hostname = (parsed.hostname or "").lower()
        path = (parsed.path or "").lower()
    except Exception:
        return SourceQuality.UNKNOWN

    if not hostname:
        return SourceQuality.UNKNOWN

    # Check official domains
    if any(hostname.endswith(tld) for tld in _OFFICIAL_TLDS):
        return SourceQuality.OFFICIAL
    if hostname in _OFFICIAL_DOMAINS:
        return SourceQuality.OFFICIAL

    # Check news domains
    if hostname in _NEWS_DOMAINS or any(
        hostname.endswith(f".{d}") for d in _NEWS_DOMAINS
    ):
        return SourceQuality.NEWS

    # Check documentation domains
    if hostname in _DOCS_DOMAINS or any(
        hostname.endswith(f".{d}") for d in _DOCS_DOMAINS
    ):
        return SourceQuality.DOCUMENTATION
    if "docs." in hostname or "/docs/" in path or "/documentation/" in path:
        return SourceQuality.DOCUMENTATION

    # Check community domains
    if hostname in _COMMUNITY_DOMAINS:
        return SourceQuality.COMMUNITY

    # Blog indicators
    if any(indicator in hostname for indicator in (
        "blog", "medium.com", "dev.to", "hashnode",
    )):
        return SourceQuality.BLOG
    if "/blog/" in path or "/post/" in path or "/article/" in path:
        return SourceQuality.BLOG

    return SourceQuality.UNKNOWN
