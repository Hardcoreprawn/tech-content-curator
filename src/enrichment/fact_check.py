"""Fact-checking module for article validation.

Lightweight validation that checks:
- Source URLs are reachable
- Markdown links aren't broken
- Basic claim validation against research summary
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import httpx
from rich.console import Console

from ..models import EnrichedItem, GeneratedArticle

console = Console()


@dataclass
class FactCheckResult:
    """Result of fact-checking an article."""

    confidence_score: float  # 0.0 to 1.0
    warnings: list[str]
    broken_links: list[str]
    unreachable_sources: list[str]
    passed: bool


def validate_url_reachable(url: str, timeout: float = 10.0) -> bool:
    """Check if a URL is reachable with a HEAD request.

    Args:
        url: URL to check
        timeout: Request timeout in seconds

    Returns:
        True if URL returns 2xx or 3xx status code
    """
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            response = client.head(url)
            return response.status_code < 400
    except Exception:
        # Try GET if HEAD fails (some servers don't support HEAD)
        try:
            with httpx.Client(timeout=timeout, follow_redirects=True) as client:
                response = client.get(url, timeout=5.0)
                return response.status_code < 400
        except Exception:
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
    console.print(f"[blue]Fact-checking:[/blue] {article.title[:50]}...")

    warnings: list[str] = []
    broken_links: list[str] = []
    unreachable_sources: list[str] = []

    # 1. Check all source URLs are reachable
    console.print("  Checking source URLs...")
    for source in article.sources:
        url = str(source.original.url)
        if not validate_url_reachable(url):
            unreachable_sources.append(url)
            warnings.append(f"Source URL unreachable: {url}")

    # 2. Extract and validate all markdown links in the article
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
    if "> **Attribution:**" not in article.content and "> Attribution:" not in article.content:
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
    passed = confidence >= 0.7 and not unreachable_sources

    result = FactCheckResult(
        confidence_score=confidence,
        warnings=warnings,
        broken_links=broken_links,
        unreachable_sources=unreachable_sources,
        passed=passed,
    )

    # Print summary
    if passed:
        console.print(f"  [green]✓[/green] Passed (confidence: {confidence:.2f})")
    else:
        console.print(f"  [yellow]⚠[/yellow] Failed (confidence: {confidence:.2f})")
    
    if warnings:
        console.print(f"  [yellow]{len(warnings)} warning(s)[/yellow]")
        for warning in warnings[:3]:  # Show first 3
            console.print(f"    • {warning}")
        if len(warnings) > 3:
            console.print(f"    • ... and {len(warnings) - 3} more")

    return result
