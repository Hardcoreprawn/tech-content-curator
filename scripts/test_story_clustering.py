"""Test script for story clustering functionality.

This script tests the story clustering system with real examples from your
October 31st pipeline run that had duplicate stories.

Run: python scripts/test_story_clustering.py
"""

import sys
from datetime import UTC, datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from pydantic import HttpUrl
from rich.console import Console

from src.deduplication import (
    calculate_story_similarity,
    filter_duplicate_stories,
    find_story_clusters,
    report_story_clusters,
)
from src.models import CollectedItem, EnrichedItem, SourceType

console = Console()


def create_test_item(
    title: str,
    content: str,
    source: SourceType,
    topics: list[str],
    quality: float = 0.8,
) -> EnrichedItem:
    """Helper to create test enriched items."""
    collected = CollectedItem(
        id=f"test-{hash(title)}",
        title=title,
        content=content,
        source=source,
        url=HttpUrl(f"https://example.com/{hash(title)}"),
        author="test_user",
        collected_at=datetime.now(UTC),
    )

    return EnrichedItem(
        original=collected,
        research_summary=content,
        related_sources=[],
        topics=topics,
        quality_score=quality,
        enriched_at=datetime.now(UTC),
    )


def test_affinity_case():
    """Test case: Affinity Software from different sources."""
    console.print(
        "\n[bold cyan]Test Case 1: Affinity Software (from your Oct 31 run)[/bold cyan]\n"
    )

    item1 = create_test_item(
        title="Affinity Studio Goes Free: A Game Changer for Designers",
        content="Affinity announces free release of their design software suite. "
        "The move comes after Canva acquisition. Major shift from paid model.",
        source=SourceType.HACKERNEWS,
        topics=["design", "software", "freemium", "affinity"],
        quality=0.85,
    )

    item2 = create_test_item(
        title="Affinity Software's Freemium Shift: What Artists Need to Know",
        content="Affinity's business model change to freemium after Canva acquisition. "
        "Artists should understand implications of this shift.",
        source=SourceType.MASTODON,
        topics=["design", "software", "freemium", "canva", "affinity"],
        quality=0.80,
    )

    # Calculate similarity
    similarity = calculate_story_similarity(item1, item2)
    console.print(f"Story similarity: {similarity:.1%}")
    console.print(
        f"Should be detected as duplicates: {'✓ Yes' if similarity > 0.55 else '✗ No'}\n"
    )

    # Cluster them
    clusters = find_story_clusters([item1, item2])
    report_story_clusters(clusters, verbose=True)

    # Filter
    filtered = filter_duplicate_stories([item1, item2])
    console.print(
        f"\n[green]After filtering: {len(filtered)} items (started with 2)[/green]"
    )


def test_icc_case():
    """Test case: ICC Open Source from different sources."""
    console.print(
        "\n[bold cyan]Test Case 2: ICC Open Source (from your Oct 31 run)[/bold cyan]\n"
    )

    item1 = create_test_item(
        title="ICC Ditches Microsoft 365 for Open-Source: A Data Privacy Win",
        content="International Criminal Court transitions from Microsoft 365 to open-source. "
        "Focus on data privacy and sovereignty concerns.",
        source=SourceType.MASTODON,
        topics=[
            "open-source",
            "microsoft",
            "privacy",
            "icc",
            "cloud",
            "data-sovereignty",
        ],
        quality=0.82,
    )

    item2 = create_test_item(
        title="ICC's Bold Move: Embracing Open-Source Over Microsoft",
        content="ICC adopts open-source software instead of Microsoft 365. "
        "Part of broader European tech development and industry adoption trends.",
        source=SourceType.MASTODON,
        topics=["open-source", "microsoft", "enterprise", "icc", "europe", "cloud"],
        quality=0.78,
    )

    # Calculate similarity
    similarity = calculate_story_similarity(item1, item2)
    console.print(f"Story similarity: {similarity:.1%}")
    console.print(
        f"Should be detected as duplicates: {'✓ Yes' if similarity > 0.55 else '✗ No'}\n"
    )

    # Cluster them
    clusters = find_story_clusters([item1, item2])
    report_story_clusters(clusters, verbose=True)

    # Filter
    filtered = filter_duplicate_stories([item1, item2])
    console.print(
        f"\n[green]After filtering: {len(filtered)} items (started with 2)[/green]"
    )


def test_unrelated_case():
    """Test case: Unrelated items should NOT be clustered."""
    console.print(
        "\n[bold cyan]Test Case 3: Unrelated Items (should NOT cluster)[/bold cyan]\n"
    )

    item1 = create_test_item(
        title="Rust 1.75 Released with New Features",
        content="Rust programming language version 1.75 includes new async improvements.",
        source=SourceType.REDDIT,
        topics=["rust", "programming", "release"],
        quality=0.85,
    )

    item2 = create_test_item(
        title="Python 3.13 Beta Now Available",
        content="Python 3.13 beta release with performance improvements.",
        source=SourceType.HACKERNEWS,
        topics=["python", "programming", "release"],
        quality=0.87,
    )

    # Calculate similarity
    similarity = calculate_story_similarity(item1, item2)
    console.print(f"Story similarity: {similarity:.1%}")
    console.print(
        f"Should NOT be detected as duplicates: {'✓ Correct' if similarity <= 0.55 else '✗ Wrong'}\n"
    )

    # Cluster them
    clusters = find_story_clusters([item1, item2])
    report_story_clusters(clusters, verbose=True)

    # Filter
    filtered = filter_duplicate_stories([item1, item2])
    console.print(
        f"\n[green]After filtering: {len(filtered)} items (started with 2)[/green]"
    )


def test_mixed_case():
    """Test case: Mix of related and unrelated items."""
    console.print(
        "\n[bold cyan]Test Case 4: Mixed Batch (realistic scenario)[/bold cyan]\n"
    )

    items = [
        # Duplicate story pair
        create_test_item(
            "Docker Security Flaw Discovered",
            "Critical security vulnerability found in Docker containers.",
            SourceType.HACKERNEWS,
            ["docker", "security", "vulnerability"],
            0.90,
        ),
        create_test_item(
            "Major Docker Vulnerability Affects Millions",
            "Docker security issue impacts container deployments worldwide.",
            SourceType.REDDIT,
            ["docker", "security", "containers"],
            0.85,
        ),
        # Unrelated item
        create_test_item(
            "TypeScript 5.3 Adds Import Attributes",
            "New TypeScript version includes import attributes support.",
            SourceType.HACKERNEWS,
            ["typescript", "javascript", "release"],
            0.88,
        ),
        # Another unrelated item
        create_test_item(
            "GitHub Copilot Workspace Announced",
            "GitHub announces new AI-powered development environment.",
            SourceType.GITHUB,
            ["github", "ai", "tools"],
            0.92,
        ),
    ]

    console.print(f"Input: {len(items)} items")

    # Find clusters
    clusters = find_story_clusters(items)
    report_story_clusters(clusters, verbose=True)

    # Filter
    filtered = filter_duplicate_stories(items)
    console.print(f"\n[green]After filtering: {len(filtered)} unique stories[/green]")
    console.print("Expected: 3 (Docker duplicate removed, others kept)")


if __name__ == "__main__":
    console.print("\n[bold]Story Clustering Test Suite[/bold]")
    console.print("=" * 60)

    test_affinity_case()
    console.print("\n" + "=" * 60)

    test_icc_case()
    console.print("\n" + "=" * 60)

    test_unrelated_case()
    console.print("\n" + "=" * 60)

    test_mixed_case()
    console.print("\n" + "=" * 60)

    console.print("\n[bold green]✓ All tests complete![/bold green]")
