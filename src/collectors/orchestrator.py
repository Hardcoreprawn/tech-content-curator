"""Collection utilities and orchestration.

This module provides utility functions for managing collected items:
- Saving collected items to JSON files
- Deduplicating collected items
- Orchestrating collection from all sources
"""

import json
from datetime import UTC, datetime
from pathlib import Path

from rich.console import Console

from ..config import get_config, get_data_dir
from ..deduplication.dedup_feedback import DeduplicationFeedbackSystem
from ..deduplication.semantic_dedup import SemanticDeduplicator
from ..models import CollectedItem, PipelineConfig
from ..utils.url_tools import normalize_url
from .github import collect_from_github_trending
from .hackernews import collect_from_hackernews
from .mastodon import collect_from_mastodon_trending
from .reddit import collect_from_reddit

console = Console()


def save_collected_items(
    items: list[CollectedItem], timestamp: str | None = None
) -> Path:
    """Save collected items to JSON file.

    Why JSON files instead of a database:
    - Simple to debug (you can open the file and see what's in it)
    - No setup required
    - Easy to process with other tools
    - Good enough for this scale

    Args:
        items: List of collected items to save
        timestamp: Optional timestamp for filename, defaults to now

    Returns:
        Path to the saved file
    """
    if not timestamp:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    filename = f"collected_{timestamp}.json"
    filepath = get_data_dir() / filename

    # Convert Pydantic models to dict for JSON serialization
    data = {
        "collected_at": datetime.now(UTC).isoformat(),
        "total_items": len(items),
        "items": [item.model_dump() for item in items],
    }

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)

    console.print(f"[green]✓[/green] Saved {len(items)} items to {filename}")
    return filepath


def deduplicate_items(items: list[CollectedItem]) -> list[CollectedItem]:
    """Remove duplicate content using semantic deduplication with learning.

    Uses adaptive semantic analysis to detect duplicates across instances.
    Learns patterns from duplicates to improve future detection.
    Keeps the item with the highest engagement when duplicates are found.

    Args:
        items: List of collected items to deduplicate

    Returns:
        List of unique items
    """
    if not items:
        return items

    console.print(f"[yellow]Deduplicating {len(items)} items...[/yellow]")

    # First pass: Remove exact URL duplicates
    url_groups: dict[str, list[CollectedItem]] = {}
    for item in items:
        url = normalize_url(str(item.url))
        if url not in url_groups:
            url_groups[url] = []
        url_groups[url].append(item)

    # Keep highest engagement item from each URL group
    def get_engagement(item: CollectedItem) -> int:
        """Calculate engagement score for an item."""
        if not item.metadata:
            return 0
        return (
            item.metadata.get("favourites_count", 0)
            + item.metadata.get("score", 0)
            + item.metadata.get("reblogs_count", 0) * 2
            + item.metadata.get("replies_count", 0) * 3
            + item.metadata.get("comments", 0) * 3
        )

    url_deduped = []
    url_dups_removed = 0
    for _url, group in url_groups.items():
        best_item = max(group, key=get_engagement)
        url_deduped.append(best_item)
        if len(group) > 1:
            url_dups_removed += len(group) - 1

    if url_dups_removed > 0:
        console.print(f"[dim]Removed {url_dups_removed} exact URL duplicates[/dim]")

    # Second pass: Semantic deduplication
    console.print(
        f"[yellow]Running semantic deduplication on {len(url_deduped)} items...[/yellow]"
    )

    deduplicator = SemanticDeduplicator()
    feedback_system = DeduplicationFeedbackSystem()

    duplicate_groups = deduplicator.find_duplicates(url_deduped, threshold=0.6)  # type: ignore

    # Create set of items that are duplicates
    duplicate_items = set()
    unique_items = []

    for group in duplicate_groups:
        best_item = max(group, key=lambda x: get_engagement(x))  # type: ignore
        unique_items.append(best_item)

        for item in group:
            if item != best_item:
                duplicate_items.add(id(item))

        console.print(
            f"[dim]Removed {len(group) - 1} semantic duplicates of: {best_item.content[:50]}...[/dim]"
        )

    # Add non-duplicate items
    for item in url_deduped:
        if id(item) not in duplicate_items:
            if not any(id(unique_item) == id(item) for unique_item in unique_items):
                unique_items.append(item)

    semantic_dedupe_count = len(url_deduped) - len(unique_items)
    if semantic_dedupe_count > 0:
        console.print(
            f"[blue]Removed {semantic_dedupe_count} semantic duplicates using learned patterns[/blue]"
        )

        feedback_system.record_deduplication_session(
            url_deduped, unique_items, deduplicator
        )

        stats = deduplicator.get_pattern_stats()
        if stats.get("total_patterns", 0) > 0:
            console.print(
                f"[dim]Using {stats['total_patterns']} learned patterns with {stats.get('avg_confidence', 0):.2f} avg confidence[/dim]"
            )

    return unique_items


def collect_all_sources() -> list[CollectedItem]:
    """Collect content from all configured sources.

    This is the main entry point for content collection.
    It tries each source and combines results, with deduplication.

    Returns:
        List of deduplicated collected items
    """
    config = get_config()
    all_items = []

    console.print("[bold blue]Starting content collection...[/bold blue]")

    # Collect from Mastodon
    for instance in config.mastodon_instances:
        console.print(f"\n[blue]Trying Mastodon instance: {instance}[/blue]")
        try:
            instance_config = PipelineConfig(
                openai_api_key=config.openai_api_key,
                mastodon_instances=[instance],
                articles_per_run=config.articles_per_run,
                min_content_length=config.min_content_length,
                max_content_length=config.max_content_length,
            )
            mastodon_items = collect_from_mastodon_trending(instance_config)
            all_items.extend(mastodon_items)

            if len(all_items) >= 80:
                console.print(
                    f"[green]✓[/green] Collected enough items ({len(all_items)}), stopping Mastodon collection"
                )
                break
        except Exception as e:
            console.print(f"[yellow]⚠[/yellow] Failed to collect from {instance}: {e}")
            continue

    # Collect from Reddit
    console.print("\n[blue]Collecting from Reddit...[/blue]")
    try:
        reddit_items = collect_from_reddit(config, limit=20)
        all_items.extend(reddit_items)
    except Exception as e:
        console.print(f"[yellow]⚠[/yellow] Reddit collection failed: {e}")

    # Collect from HackerNews
    console.print("\n[blue]Collecting from HackerNews...[/blue]")
    try:
        hn_items = collect_from_hackernews(limit=30)
        all_items.extend(hn_items)
    except Exception as e:
        console.print(f"[yellow]⚠[/yellow] HackerNews collection failed: {e}")

    # Collect from GitHub Trending
    console.print("\n[blue]Collecting from GitHub Trending...[/blue]")
    try:
        github_items = collect_from_github_trending(limit=20)
        all_items.extend(github_items)
    except Exception as e:
        console.print(f"[yellow]⚠[/yellow] GitHub collection failed: {e}")

    # Deduplicate collected items
    console.print(f"\n[bold]Total items before deduplication: {len(all_items)}[/bold]")
    unique_items = deduplicate_items(all_items)
    console.print(f"[bold green]Final unique items: {len(unique_items)}[/bold green]")

    return unique_items
