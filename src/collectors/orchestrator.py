"""Collection utilities and orchestration.

This module provides utility functions for managing collected items:
- Saving collected items to JSON files
- Deduplicating collected items
- Orchestrating collection from all sources

With PYTHON_GIL=0, uses parallel collection for improved performance.
"""

import asyncio
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from rich.console import Console

from ..config import get_config, get_data_dir
from ..deduplication.dedup_feedback import DeduplicationFeedbackSystem
from ..deduplication.semantic_dedup import SemanticDeduplicator
from ..models import CollectedItem, PipelineConfig
from ..utils.file_io import atomic_write_json
from ..utils.logging import get_logger
from ..utils.url_tools import normalize_url
from .github import collect_from_github_trending
from .hackernews import collect_from_hackernews
from .mastodon import collect_from_mastodon_trending
from .reddit import collect_from_reddit

logger = get_logger(__name__)
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

    # Use atomic write to prevent corruption
    atomic_write_json(filepath, data, ensure_ascii=False, default=str)

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

    # find_duplicates expects list[ContentProtocol], but we're using list[CollectedItem]
    # which implements the protocol. Mypy doesn't properly infer protocol implementation
    # for invariant generics. Consider using Sequence in SemanticDeduplicator for better compatibility.
    duplicate_groups = cast(
        list[list[CollectedItem]],
        deduplicator.find_duplicates(url_deduped, threshold=0.6),  # type: ignore[arg-type]
    )

    # Create set of items that are duplicates
    duplicate_items: set[int] = set()
    unique_items: list[CollectedItem] = []

    for group in duplicate_groups:
        # max() with key function to find item with highest engagement
        best_item = max(group, key=lambda x: get_engagement(x))
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


async def collect_all_sources_async() -> list[CollectedItem]:
    """Collect content from all sources in parallel using free-threading.

    This function uses ThreadPoolExecutor for true parallel I/O when running
    with PYTHON_GIL=0. Each collector runs independently with no shared state,
    then results are merged sequentially at the end.

    Returns:
        List of deduplicated collected items
    """
    config = get_config()

    console.print("[bold blue]⚡ Starting parallel content collection...[/bold blue]")

    # Define wrapper functions for each source (isolated, no shared state)
    def collect_mastodon_wrapper():
        """Collect from all Mastodon instances."""
        items = []
        for instance in config.mastodon_instances:
            try:
                instance_config = PipelineConfig(
                    openai_api_key=config.openai_api_key,
                    mastodon_instances=[instance],
                    articles_per_run=config.articles_per_run,
                    min_content_length=config.min_content_length,
                    max_content_length=config.max_content_length,
                )
                mastodon_items = collect_from_mastodon_trending(instance_config)
                items.extend(mastodon_items)
                logger.info(f"Collected {len(mastodon_items)} items from {instance}")

                if len(items) >= 80:
                    logger.info("Reached 80 items from Mastodon, stopping")
                    break
            except Exception as e:
                logger.error(f"Mastodon {instance} failed: {e}")
                continue
        return items

    def collect_reddit_wrapper():
        """Collect from Reddit."""
        try:
            items = collect_from_reddit(config, limit=20)
            logger.info(f"Collected {len(items)} items from Reddit")
            return items
        except Exception as e:
            logger.error(f"Reddit collection failed: {e}")
            return []

    def collect_hn_wrapper():
        """Collect from HackerNews."""
        try:
            items = collect_from_hackernews(limit=30)
            logger.info(f"Collected {len(items)} items from HackerNews")
            return items
        except Exception as e:
            logger.error(f"HackerNews collection failed: {e}")
            return []

    def collect_github_wrapper():
        """Collect from GitHub Trending."""
        try:
            items = collect_from_github_trending(limit=20)
            logger.info(f"Collected {len(items)} items from GitHub")
            return items
        except Exception as e:
            logger.error(f"GitHub collection failed: {e}")
            return []

    # Parallel phase: each thread isolated, no sharing
    collection_start = time.perf_counter()
    console.print(
        "[bold blue]⚡ Launching parallel collection from 4 sources...[/bold blue]"
    )

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    source_names = ["Mastodon", "Reddit", "HackerNews", "GitHub"]
    source_start_times = {name: time.perf_counter() for name in source_names}

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [
            loop.run_in_executor(executor, collect_mastodon_wrapper),
            loop.run_in_executor(executor, collect_reddit_wrapper),
            loop.run_in_executor(executor, collect_hn_wrapper),
            loop.run_in_executor(executor, collect_github_wrapper),
        ]
        results = await asyncio.gather(*futures, return_exceptions=True)

    # Sequential merge: no locks needed
    all_items = []
    for i, result in enumerate(results):
        source_elapsed = time.perf_counter() - source_start_times[source_names[i]]
        if isinstance(result, Exception):
            logger.error(
                f"{source_names[i]} collection failed: {result}",
                exc_info=result,
                extra={
                    "source": source_names[i],
                    "phase": "collection",
                    "elapsed_seconds": source_elapsed,
                },
            )
            console.print(
                f"[yellow]⚠[/yellow] {source_names[i]} collection failed: {result}"
            )
            continue
        if isinstance(result, list):
            all_items.extend(result)
            logger.info(
                f"{source_names[i]} collected {len(result)} items in {source_elapsed:.2f}s",
                extra={
                    "source": source_names[i],
                    "count": len(result),
                    "elapsed_seconds": source_elapsed,
                },
            )

    collection_elapsed = time.perf_counter() - collection_start
    console.print(f"\n[bold]Total items before deduplication: {len(all_items)}[/bold]")
    console.print(f"[dim]Collection time: {collection_elapsed:.2f}s[/dim]")

    # Deduplication reads immutable patterns - no locks needed
    dedup_start = time.perf_counter()
    unique_items = deduplicate_items(all_items)
    dedup_elapsed = time.perf_counter() - dedup_start

    logger.info(
        f"Parallel collection completed: {len(all_items)} items in {collection_elapsed:.2f}s, "
        f"deduplication {dedup_elapsed:.2f}s, final {len(unique_items)} unique items",
        extra={
            "collection_time": collection_elapsed,
            "dedup_time": dedup_elapsed,
            "total_items": len(all_items),
            "unique_items": len(unique_items),
        },
    )
    console.print(f"[bold green]Final unique items: {len(unique_items)}[/bold green]")
    console.print(f"[dim]Total time: {collection_elapsed + dedup_elapsed:.2f}s[/dim]")

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
