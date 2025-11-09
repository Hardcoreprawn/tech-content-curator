"""Primary source fetching for meta-content enrichment.

Extracts URLs from social media posts and detects when posts
are discussing other articles (meta-content). This enables
better context when generating articles about articles.

Future: Will include article content fetching using VS Code's
fetch_webpage capability.
"""

from __future__ import annotations

import re

from ..models import CollectedItem
from ..utils.logging import get_logger

logger = get_logger(__name__)


def extract_urls_from_content(content: str) -> list[str]:
    """Extract article URLs from post content.

    Filters to keep only URLs that are likely to be articles
    (blogs, news sites, etc.) rather than social media links.

    Args:
        content: The post content to extract URLs from

    Returns:
        List of URLs found that appear to be articles, empty if none
    """
    # Match http/https URLs, stop at whitespace or common terminators
    url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
    urls = re.findall(url_pattern, content)

    if not urls:
        return []

    # Filter for domains that typically host articles
    # Exclude pure social media platforms (twitter, mastodon, reddit posts)
    article_domains = [
        "medium.com",
        "dev.to",
        "blog",
        "article",
        "news",
        ".org",
        ".edu",
        "arxiv",
        "github.io",
        "substack.com",
        "wordpress.com",
        "blogspot.com",
        "press",
        "post",
        "journal",
        "paper",
        "research",
    ]

    social_only_domains = [
        "twitter.com",
        "x.com",
        "reddit.com/r/",  # Exclude direct reddit posts
        "facebook.com",
        "instagram.com",
        "tiktok.com",
    ]

    filtered_urls = []
    for url in urls:
        url_lower = url.lower()

        # Exclude pure social media links
        if any(domain in url_lower for domain in social_only_domains):
            continue

        # Include if it matches article patterns
        if any(domain in url_lower for domain in article_domains):
            filtered_urls.append(url)
            continue

        # Also include .com/.net/.io that aren't in social exclusion list
        if any(tld in url_lower for tld in [".com/", ".net/", ".io/"]):
            filtered_urls.append(url)

    return filtered_urls


def is_meta_content(item: CollectedItem, urls: list[str]) -> bool:
    """Detect if post is discussing another article (meta-content).

    Meta-content is when a social media post is primarily about
    sharing/discussing an existing article, rather than being
    standalone content.

    Args:
        item: The collected item to analyze
        urls: Extracted URLs from the content

    Returns:
        True if post appears to be about another article
    """
    if not urls:
        return False

    content_lower = item.content.lower()

    # Indicators that this is commentary on an article
    meta_indicators = [
        "wrote",
        "article",
        "published",
        "post",
        "piece",
        "obituary",
        "essay",
        "blog",
        "thread",
        "analysis",
        "story",
        "report",
        "paper",
        "study",
        "research",
        "announcement",
        "press release",
        "interview",
        "review",
        "column",
    ]

    # Check if any indicators present
    indicator_count = sum(1 for indicator in meta_indicators if indicator in content_lower)

    # If we have URLs AND meta-indicators, likely meta-content
    # Require at least 2 indicators to avoid false positives
    if indicator_count >= 2:
        logger.debug(
            f"Meta-content detected: {indicator_count} indicators, {len(urls)} URLs"
        )
        return True

    # Special case: Single strong indicator with URL
    strong_indicators = [
        "wrote about",
        "published article",
        "obituary for",
        "essay on",
        "new piece",
        "just published",
        "analysis of",
        "review of",
        "thread on",
        "paper on",
        "study shows",
    ]

    if any(indicator in content_lower for indicator in strong_indicators):
        logger.debug("Meta-content detected: strong indicator present")
        return True

    return False


# Future Phase 2: Article fetching
# def fetch_article_content(url: str, max_size: int = 5000) -> str | None:
#     """Fetch and extract main content from article URL.
#
#     Will use VS Code's fetch_webpage capability to get article content,
#     then extract the main text using readability algorithms.
#
#     Args:
#         url: Article URL to fetch
#         max_size: Maximum characters to return
#
#     Returns:
#         Main article content or None if fetch fails
#     """
#     # TODO: Implement in Phase 2
#     pass
