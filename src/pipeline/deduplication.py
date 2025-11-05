"""Source deduplication and cooldown management.

This module handles checking for duplicate sources and enforcing
cooldown periods to ensure content diversity:

- Check if article already exists for a source URL
- Collect existing source URLs from published articles
- Enforce cooldown periods (don't reuse same source too soon)
- Load article metadata for deduplication checks

Supports both legacy single-source and current multi-source formats.
"""

from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import frontmatter

from ..utils.logging import get_logger
from ..utils.url_tools import normalize_url

logger = get_logger(__name__)


def check_article_exists_for_source(source_url: str, content_dir: Path) -> Path | None:
    """Check if an article for this source URL already exists.

    Args:
        source_url: Original source URL to check
        content_dir: Directory containing articles

    Returns:
        Path to existing article if found, None otherwise
    """
    logger.debug(f"Checking if article exists for source: {source_url}")
    # Normalize incoming URL once
    normalized_input = normalize_url(source_url)

    # Check all existing markdown files for this source URL
    for filepath in content_dir.glob("*.md"):
        try:
            post = frontmatter.load(str(filepath))
            meta = post.metadata or {}
            # New format: list of sources
            sources = meta.get("sources")
            if isinstance(sources, list):
                for s in sources:
                    url = s.get("url") if isinstance(s, dict) else None
                    if url and normalize_url(str(url)) == normalized_input:
                        return filepath
            # Legacy format: single source dict
            source_meta = meta.get("source")
            if isinstance(source_meta, dict):
                url = source_meta.get("url")
                if url and normalize_url(str(url)) == normalized_input:
                    logger.info(f"Found existing article for source: {filepath.name}")
                    return filepath
        except (OSError, ValueError, Exception) as e:
            logger.debug(f"Failed to load article metadata from {filepath}: {e}")
            continue
    logger.debug("No existing article found for source")
    return None


def collect_existing_source_urls(content_dir: Path) -> set[str]:
    """Collect normalized source URLs present in existing articles' frontmatter.

    Supports both legacy 'source' dict and current 'sources' list formats.

    Args:
        content_dir: Directory containing articles

    Returns:
        Set of normalized source URLs
    """
    logger.debug("Collecting existing source URLs from articles")
    urls: set[str] = set()
    for filepath in content_dir.glob("*.md"):
        try:
            post = frontmatter.load(str(filepath))
            meta = post.metadata or {}
            # New format: list of sources
            sources = meta.get("sources")
            if isinstance(sources, list):
                for s in sources:
                    url = s.get("url") if isinstance(s, dict) else None
                    if url:
                        urls.add(normalize_url(str(url)))
            # Legacy format: single source dict
            legacy = meta.get("source")
            if isinstance(legacy, dict):
                url = legacy.get("url")
                if url:
                    urls.add(normalize_url(str(url)))
        except (OSError, ValueError, Exception) as e:
            logger.debug(f"Failed to load article metadata from {filepath}: {e}")
            continue
    logger.info(f"Collected {len(urls)} existing source URLs")
    return urls


def is_source_in_cooldown(
    source_url: str, content_dir: Path, cooldown_days: int = 7
) -> bool:
    """Check if a source URL was used recently (within cooldown period).

    This prevents generating multiple articles from the same source (e.g., GitHub repo)
    too frequently, ensuring content diversity.

    Args:
        source_url: Source URL to check
        content_dir: Directory containing articles
        cooldown_days: Number of days to wait before reusing a source

    Returns:
        True if source is in cooldown period (was used recently)
    """
    normalized_url = normalize_url(source_url)
    cutoff_date = datetime.now(UTC) - timedelta(days=cooldown_days)

    for filepath in content_dir.glob("*.md"):
        try:
            post = frontmatter.load(str(filepath))
            meta = post.metadata or {}

            # Check article date
            article_date_str = meta.get("date")
            if not article_date_str:
                continue

            # Handle datetime.date, datetime.datetime, or string
            if isinstance(article_date_str, datetime):
                article_date = (
                    article_date_str.replace(tzinfo=UTC)
                    if article_date_str.tzinfo is None
                    else article_date_str
                )
            elif isinstance(article_date_str, date):
                # Convert date to datetime at start of day
                article_date = datetime.combine(
                    article_date_str, datetime.min.time()
                ).replace(tzinfo=UTC)
            elif isinstance(article_date_str, str):
                # Parse date (format: YYYY-MM-DD or full ISO format)
                article_date = datetime.fromisoformat(article_date_str)
                if article_date.tzinfo is None:
                    article_date = article_date.replace(tzinfo=UTC)
            else:
                continue

            # If article is older than cooldown, skip it
            if article_date < cutoff_date:
                continue

            # Check if this article used our source URL
            sources = meta.get("sources", [])
            if isinstance(sources, list):
                for s in sources:
                    url = s.get("url") if isinstance(s, dict) else None
                    if url and normalize_url(str(url)) == normalized_url:
                        logger.debug(
                            f"Source {source_url} in cooldown (article from {article_date})"
                        )
                        return True  # Found recent article with this source

        except (OSError, ValueError, Exception) as e:
            logger.debug(f"Failed to load article metadata from {filepath}: {e}")
            continue

    logger.debug(f"Source {source_url} not in cooldown")
    return False  # Source not used recently


def load_article_metadata_for_dedup(content_dir: Path) -> list[dict]:
    """Load existing article metadata for deduplication checks.

    Extracts title, summary, tags, and content from published articles
    to enable semantic similarity comparisons.

    Args:
        content_dir: Directory containing articles

    Returns:
        List of article metadata dictionaries
    """
    logger.debug("Loading article metadata for deduplication")
    articles = []

    for filepath in content_dir.glob("*.md"):
        try:
            post = frontmatter.load(str(filepath))
            meta = post.metadata or {}

            articles.append(
                {
                    "title": meta.get("title", ""),
                    "summary": meta.get("summary", ""),
                    "tags": meta.get("tags", []),
                    "content": post.content[:500],  # First 500 chars
                    "filepath": filepath,
                }
            )
        except (OSError, ValueError, Exception) as e:
            logger.debug(f"Failed to load article metadata from {filepath}: {e}")
            continue

    logger.info(f"Loaded metadata for {len(articles)} articles for deduplication")
    return articles
