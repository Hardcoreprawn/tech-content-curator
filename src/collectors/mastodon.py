"""Mastodon content collector.

Collects trending and public timeline posts from Mastodon instances.
Mastodon is TIER_1 source - high quality, community-filtered content.
"""

from datetime import UTC, datetime
from urllib.parse import urljoin

import httpx
from rich.console import Console

from ..models import CollectedItem, PipelineConfig, SourceType
from .base import (
    clean_html_content,
    extract_title_from_content,
    is_entitled_whining,
    is_political_content,
    is_relevant_content,
)

console = Console()


def collect_from_mastodon_trending(
    config: PipelineConfig, limit: int = 30
) -> list[CollectedItem]:
    """Collect trending posts from Mastodon for better content quality.

    Trending content is more likely to be:
    - High quality and engaging
    - Already filtered by community engagement
    - More relevant and interesting

    Args:
        config: Pipeline configuration
        limit: Maximum number of posts to collect

    Returns:
        List of collected items from Mastodon trending
    """
    instance = config.mastodon_instances[0]  # Use first instance from list
    console.print(
        f"[blue]Collecting trending content from Mastodon ({instance})...[/blue]"
    )

    # Try trending statuses first (better quality content)
    trending_url = urljoin(instance, "/api/v1/trends/statuses")

    try:
        with httpx.Client(timeout=30.0) as client:
            # Get trending posts
            trending_response = client.get(
                trending_url, params={"limit": min(limit, 20)}
            )

            if trending_response.status_code == 200:
                trending_posts = trending_response.json()
                console.print(
                    f"[green]✓[/green] Found {len(trending_posts)} trending posts"
                )

                if trending_posts:
                    return _process_mastodon_posts(
                        trending_posts, config, "trending", instance
                    )

            # Fallback to public timeline if trending fails
            console.print(
                "[yellow]Trending not available, falling back to public timeline[/yellow]"
            )

    except Exception as e:
        console.print(
            f"[yellow]Trending collection failed: {e}, using public timeline[/yellow]"
        )

    # Fallback to public timeline
    return collect_from_mastodon_public(config, limit)


def collect_from_mastodon(
    config: PipelineConfig, limit: int = 20
) -> list[CollectedItem]:
    """Backward-compatible shim for older callers.

    Uses trending first with a fallback to public timeline.
    """
    try:
        return collect_from_mastodon_trending(config, limit)
    except Exception:
        return collect_from_mastodon_public(config, limit)


def collect_from_mastodon_public(
    config: PipelineConfig, limit: int = 20
) -> list[CollectedItem]:
    """Collect from public timeline as fallback.

    Args:
        config: Pipeline configuration
        limit: Maximum number of posts to collect

    Returns:
        List of collected items from Mastodon public timeline
    """
    instance = config.mastodon_instances[0]  # Use first instance from list
    console.print(f"[blue]Collecting from public timeline ({instance})...[/blue]")

    # Mastodon API endpoint for public timeline
    url = urljoin(instance, "/api/v1/timelines/public")

    # Parameters: only get posts (not boosts), limit results
    params = {
        "only_media": "false",
        "local": "false",  # Include federated content
        "limit": min(limit, 40),  # Mastodon's max is 40
    }

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.get(url, params=params)
            response.raise_for_status()

        posts = response.json()
        console.print(
            f"[green]✓[/green] Retrieved {len(posts)} posts from public timeline"
        )

        return _process_mastodon_posts(posts, config, "public", instance)

    except httpx.HTTPError as e:
        console.print(f"[red]✗[/red] Failed to collect from Mastodon: {e}")
        raise


def _process_mastodon_posts(
    posts: list, config: PipelineConfig, source_type: str, instance: str
) -> list[CollectedItem]:
    """Process raw Mastodon posts into CollectedItem objects with filtering.

    Args:
        posts: Raw posts from Mastodon API
        config: Pipeline configuration
        source_type: "trending" or "public" for logging
        instance: The Mastodon instance URL

    Returns:
        List of filtered and processed CollectedItem objects
    """
    console.print(f"[blue]Processing {len(posts)} raw posts...[/blue]")

    # Tracking counters
    items = []
    filtered_counts = {
        "malformed": 0,
        "too_short": 0,
        "too_long": 0,
        "no_content": 0,
        "political": 0,
        "entitled": 0,
        "non_english": 0,
        "off_topic": 0,
        "processed": 0,
    }

    for post in posts:
        try:
            # Extract text content, handling HTML
            content = clean_html_content(post.get("content", ""))

            # Skip posts that are too long
            if len(content) > config.max_content_length:
                filtered_counts["too_long"] += 1
                continue

            # For very short posts, only keep if they have strong indicators
            if len(content) < 50:
                filtered_counts["too_short"] += 1
                continue
            elif len(content) < config.min_content_length:
                # Check if short post has redeeming qualities
                has_tech_keywords = any(
                    keyword in content.lower()
                    for keyword in [
                        "python",
                        "javascript",
                        "rust",
                        "go",
                        "docker",
                        "kubernetes",
                        "aws",
                        "azure",
                        "api",
                        "github",
                        "open source",
                        "algorithm",
                        "ml",
                        "ai",
                        "devops",
                        "cloud",
                    ]
                )
                has_engagement = (
                    post.get("favourites_count", 0) + post.get("reblogs_count", 0)
                ) > 5
                has_links = "http" in content

                if not (has_tech_keywords or has_engagement or has_links):
                    filtered_counts["too_short"] += 1
                    continue

            # Skip posts without meaningful content
            if not content.strip() or content.strip().startswith("@"):
                filtered_counts["no_content"] += 1
                continue

            # Filter out political content
            if is_political_content(content):
                filtered_counts["political"] += 1
                console.print(f"[dim]Filtered political: {content[:50]}...[/dim]")
                continue

            # Filter out entitled whining
            if is_entitled_whining(content):
                filtered_counts["entitled"] += 1
                console.print(f"[dim]Filtered entitled: {content[:50]}...[/dim]")
                continue

            # Check language
            language = post.get("language", "en")
            if language != "en" and len(content) > 50:
                filtered_counts["non_english"] += 1
                console.print(
                    f"[dim]Filtered non-English ({language}): {content[:50]}...[/dim]"
                )
                continue

            # Check topic relevance
            title = extract_title_from_content(content)
            if not is_relevant_content(content, title, config):
                filtered_counts["off_topic"] += 1
                console.print(f"[dim]Filtered off-topic: {content[:50]}...[/dim]")
                continue

            item = CollectedItem(
                id=f"mastodon_{post['id']}",
                title=title,
                content=content,
                source=SourceType.MASTODON,
                url=post["url"],
                author=post["account"]["username"],
                collected_at=datetime.now(UTC),
                metadata={
                    "favourites_count": post.get("favourites_count", 0),
                    "reblogs_count": post.get("reblogs_count", 0),
                    "replies_count": post.get("replies_count", 0),
                    "created_at": post.get("created_at"),
                    "language": language,
                    "instance": instance,
                    "source_type": source_type,
                    "source_name": "mastodon_trending",
                },
            )
            items.append(item)
            filtered_counts["processed"] += 1

        except (KeyError, ValueError) as e:
            filtered_counts["malformed"] += 1
            console.print(f"[yellow]⚠[/yellow] Malformed post: {e}")
            continue

    # Print detailed filtering summary
    total_raw = len(posts)
    total_filtered = sum(
        filtered_counts[key] for key in filtered_counts if key != "processed"
    )

    console.print("\n[bold]Collection Summary:[/bold]")
    console.print(f"  Raw posts retrieved: {total_raw}")
    console.print(f"  Successfully processed: {filtered_counts['processed']}")
    console.print(f"  Total filtered out: {total_filtered}")

    if total_filtered > 0:
        console.print("[dim]  Filter breakdown:[/dim]")
        for reason, count in filtered_counts.items():
            if reason != "processed" and count > 0:
                console.print(
                    f"[dim]    {reason.replace('_', ' ').title()}: {count}[/dim]"
                )

    console.print(
        f"[green]✓[/green] Final result: {len(items)} items from Mastodon {source_type}"
    )
    return items
