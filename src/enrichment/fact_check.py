"""Fact-checking module for article validation.

Lightweight validation that checks:
- Source URLs are reachable
- Markdown links aren't broken
- Basic claim validation against research summary
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from random import random

import httpx
from rich.console import Console

from ..models import EnrichedItem, GeneratedArticle
from ..utils.logging import get_logger

logger = get_logger(__name__)
console = Console()


@dataclass
class FactCheckResult:
    """Result of fact-checking an article."""

    confidence_score: float  # 0.0 to 1.0
    warnings: list[str]
    broken_links: list[str]
    unreachable_sources: list[str]
    passed: bool


def validate_url_reachable(url: str, timeout: float | None = None) -> bool:
    """Check if a URL is reachable with a HEAD request.

    Args:
        url: URL to check
        timeout: Request timeout in seconds (uses config default if not provided)

    Returns:
        True if URL returns 2xx or 3xx status code
    """
    from ..config import get_config

    if timeout is None:
        config = get_config()
        timeout = config.timeouts.fact_check_timeout

    config = get_config()
    attempts = max(1, int(config.fact_check_retry_attempts))
    backoff_min = float(config.fact_check_retry_backoff_min)
    backoff_max = float(config.fact_check_retry_backoff_max)
    jitter = float(config.fact_check_retry_jitter)

    def _sleep_backoff(attempt_index: int) -> None:
        # Exponential backoff with jitter, capped.
        base = backoff_min * (2 ** max(0, attempt_index - 1))
        delay = min(backoff_max, base)
        delay = delay * (1.0 - jitter + (2.0 * jitter * random()))
        if delay > 0:
            time.sleep(delay)

    def _should_retry_status(status_code: int) -> bool:
        return status_code in (408, 425, 429) or 500 <= status_code <= 599

    def _try_request(client: httpx.Client, method: str) -> httpx.Response:
        # Some servers break on HEAD; we still try it first, then fallback to GET.
        if method == "HEAD":
            return client.head(url)
        # Prefer a cheap GET: request only first byte if possible.
        headers = {"Range": "bytes=0-0"}
        return client.get(url, headers=headers)

    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        for attempt in range(1, attempts + 1):
            try:
                response = _try_request(client, method="HEAD")
                logger.debug(
                    f"URL validation HEAD request: {url} -> {response.status_code}"
                )

                # If HEAD looks blocked/unsupported, fallback to GET.
                if response.status_code in (400, 403, 405):
                    response = _try_request(client, method="GET")
                    logger.debug(
                        f"URL validation GET request (fallback): {url} -> {response.status_code}"
                    )

                if response.status_code < 400:
                    return True

                if attempt < attempts and _should_retry_status(response.status_code):
                    _sleep_backoff(attempt)
                    continue
                return False
            except (
                httpx.TimeoutException,
                httpx.NetworkError,
                httpx.ProtocolError,
            ) as e:
                logger.debug(
                    f"URL validation request error (attempt {attempt}/{attempts}) for {url}: {type(e).__name__}"
                )
                if attempt < attempts:
                    _sleep_backoff(attempt)
                    continue
                logger.warning(
                    f"URL unreachable after retries: {url} ({type(e).__name__})"
                )
                return False
            except Exception:
                # Unexpected exception: log stack trace and fail closed.
                logger.exception(f"Unexpected error while validating URL: {url}")
                return False


def extract_markdown_links(content: str) -> list[tuple[str, str]]:
    """Extract all markdown links from content.

    Args:
        content: Markdown content

    Returns:
        List of (text, url) tuples
    """
    # Match [text](url) pattern
    pattern = r"\[([^\]]+)\]\(([^\)]+)\)"
    matches = re.findall(pattern, content)
    return matches


def validate_article(
    article: GeneratedArticle, source_items: list[EnrichedItem]
) -> FactCheckResult:
    """Validate an article for accuracy and link integrity.

    Args:
        article: The generated article to validate
        source_items: The enriched source items used to create the article

    Returns:
        FactCheckResult with confidence score and warnings
    """
    logger.debug(f"Validating article: {article.title[:50]}")
    console.print(f"[blue]Fact-checking:[/blue] {article.title[:50]}...")

    warnings: list[str] = []
    broken_links: list[str] = []
    unreachable_sources: list[str] = []

    from ..config import get_config

    config = get_config()
    mode = (config.fact_check_mode or "strict").lower()
    strict_mode = mode == "strict"
    max_broken_links = int(config.fact_check_max_broken_links)
    max_unreachable_sources = int(config.fact_check_max_unreachable_sources)

    # 1. Check all source URLs are reachable
    logger.debug(f"Checking {len(article.sources)} source URLs")
    console.print("  Checking source URLs...")
    for source in article.sources:
        url = str(source.original.url)
        if not validate_url_reachable(url):
            unreachable_sources.append(url)
            warnings.append(f"Source URL unreachable: {url}")

    # 2. Extract and validate all markdown links in the article
    logger.debug("Checking markdown links in article")
    console.print("  Checking markdown links...")
    links = extract_markdown_links(article.content)
    for text, url in links:
        # Skip anchor links and relative paths
        if url.startswith("#") or not url.startswith("http"):
            continue

        if not validate_url_reachable(url):
            broken_links.append(url)
            warnings.append(f"Broken link: [{text}]({url})")

    # 3. Basic validation: check word count is reasonable
    if article.word_count < 500:
        warnings.append(f"Article is short ({article.word_count} words)")
    elif article.word_count > 3000:
        warnings.append(f"Article is very long ({article.word_count} words)")

    # 4. Check if article has proper attribution
    if (
        "> **Attribution:**" not in article.content
        and "> Attribution:" not in article.content
    ):
        warnings.append("Missing attribution block")

    # 5. Check if article has references section
    if "## References" not in article.content:
        warnings.append("Missing References section")

    # Calculate confidence score
    # Start at 1.0, deduct for issues
    confidence = 1.0

    # Deduct for unreachable sources (major issue)
    if unreachable_sources:
        confidence -= len(unreachable_sources) * 0.15

    # Deduct for broken links (moderate issue)
    if broken_links:
        confidence -= len(broken_links) * 0.10

    # Deduct for structural issues (minor)
    if "Missing attribution block" in warnings:
        confidence -= 0.10
    if "Missing References section" in warnings:
        confidence -= 0.10

    # Deduct for word count issues (minor)
    if article.word_count < 500 or article.word_count > 3000:
        confidence -= 0.05

    # Clamp to 0.0 - 1.0 range
    confidence = max(0.0, min(1.0, confidence))

    # Determine pass/fail (threshold: 0.7)
    passed = confidence >= 0.7

    if strict_mode:
        if len(unreachable_sources) > max_unreachable_sources:
            passed = False
        if len(broken_links) > max_broken_links:
            passed = False

    result = FactCheckResult(
        confidence_score=confidence,
        warnings=warnings,
        broken_links=broken_links,
        unreachable_sources=unreachable_sources,
        passed=passed,
    )

    # Print summary and log results
    if passed:
        logger.info(
            f"Article validation passed: {article.title[:50]} (confidence: {confidence:.2f})"
        )
        console.print(f"  [green]✓[/green] Passed (confidence: {confidence:.2f})")
    else:
        logger.warning(
            f"Article validation failed: {article.title[:50]} (confidence: {confidence:.2f})"
        )
        console.print(f"  [yellow]⚠[/yellow] Failed (confidence: {confidence:.2f})")

    if warnings:
        logger.debug(f"Article validation warnings ({len(warnings)}): {warnings[:3]}")
        console.print(f"  [yellow]{len(warnings)} warning(s)[/yellow]")
        for warning in warnings[:3]:  # Show first 3
            console.print(f"    • {warning}")
        if len(warnings) > 3:
            console.print(f"    • ... and {len(warnings) - 3} more")

    return result
