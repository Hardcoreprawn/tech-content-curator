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
    indicator_count = sum(
        1 for indicator in meta_indicators if indicator in content_lower
    )

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


def fetch_article_content(url: str, max_size: int = 5000) -> str | None:
    """Fetch and extract main content from article URL.

    Uses basic HTTP fetching to retrieve article content.
    Extracts the main text and cleans it for use in enrichment.

    Args:
        url: Article URL to fetch
        max_size: Maximum characters to return

    Returns:
        Main article content or None if fetch fails
    """
    try:
        import time

        import requests
        from bs4 import BeautifulSoup

        # Add delay to be respectful
        time.sleep(0.5)

        # Fetch with timeout
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; TechContentCurator/1.0; +https://github.com/Hardcoreprawn/tech-content-curator)"
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        # Parse HTML
        soup = BeautifulSoup(response.content, "html.parser")

        # Remove script and style elements
        for script in soup(["script", "style", "nav", "footer", "aside"]):
            script.decompose()

        # Try to find main content
        # Look for common article containers
        main_content = None
        for selector in [
            "article",
            'div[class*="content"]',
            'div[class*="post"]',
            'div[class*="article"]',
            "main",
        ]:
            main_content = soup.select_one(selector)
            if main_content:
                break

        # Fallback to body if no article container found
        if not main_content:
            main_content = soup.body

        if not main_content:
            logger.warning(f"Could not find content in {url}")
            return None

        # Extract text
        text = main_content.get_text(separator="\n", strip=True)

        # Clean up excessive whitespace
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        text = "\n".join(lines)

        # Truncate if needed
        if len(text) > max_size:
            text = text[:max_size] + "\n\n[Content truncated...]"

        logger.info(f"Fetched {len(text)} chars from {url}")
        return text

    except requests.Timeout:
        logger.warning(f"Timeout fetching {url}")
        return None
    except requests.RequestException as e:
        logger.warning(f"Failed to fetch {url}: {e}")
        return None
    except Exception as e:
        logger.exception(f"Unexpected error fetching {url}: {e}")
        return None


def extract_additional_references(article_content: str) -> list[str]:
    """Extract URLs from fetched article content for additional research.

    Looks for URLs in the article text that might provide additional
    context or related research.

    Args:
        article_content: The fetched article text

    Returns:
        List of URLs found in the article content
    """
    if not article_content:
        return []

    # Match URLs in text
    url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
    urls = re.findall(url_pattern, article_content)

    # Filter for likely research/reference URLs
    reference_domains = [
        "doi.org",
        "arxiv.org",
        "github.com",
        "gitlab.com",
        "scholar.google",
        "pubmed",
        "ieee.org",
        "acm.org",
        ".edu",
        "research",
        "paper",
        "proceedings",
    ]

    filtered_urls = []
    seen_domains = set()

    for url in urls:
        url_lower = url.lower()

        # Check if it's a reference URL
        if any(domain in url_lower for domain in reference_domains):
            # Avoid duplicates from same domain
            domain = url.split("/")[2] if "/" in url else url
            if domain not in seen_domains:
                filtered_urls.append(url)
                seen_domains.add(domain)

    logger.debug(f"Extracted {len(filtered_urls)} reference URLs from article")
    return filtered_urls


def enrich_with_primary_source(
    item: CollectedItem, max_references: int = 3
) -> dict[str, any]:
    """Enrich item by fetching primary source content and extracting references.

    This is the main entry point for secondary URI retrieval.

    Args:
        item: The collected item to enrich
        max_references: Maximum number of additional references to extract

    Returns:
        Dictionary with primary_source_content and additional_references
    """
    result = {"primary_source_content": None, "additional_references": []}

    # Extract URLs from the post
    urls = extract_urls_from_content(item.content)

    if not urls:
        logger.debug("No URLs found in item content")
        return result

    # Check if this is meta-content
    if not is_meta_content(item, urls):
        logger.debug("Not meta-content, skipping primary source fetch")
        return result

    logger.info(f"Meta-content detected, fetching primary source from {urls[0]}")

    # Fetch the first (primary) URL
    primary_content = fetch_article_content(urls[0])

    if primary_content:
        result["primary_source_content"] = primary_content

        # Extract additional references from the primary source
        references = extract_additional_references(primary_content)
        result["additional_references"] = references[:max_references]

        logger.info(
            f"Enriched with {len(primary_content)} chars and {len(result['additional_references'])} references"
        )

    return result
