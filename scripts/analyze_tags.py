#!/usr/bin/env python3
"""Analyze existing article tags and show normalization impact.

This script:
1. Scans all existing articles
2. Shows current tag statistics
3. Demonstrates what normalized tags would look like
4. Optionally updates articles with normalized tags
"""

import sys
from pathlib import Path

import frontmatter
from rich.console import Console
from rich.table import Table

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.content.tag_normalizer import normalize_tags

console = Console()


def analyze_tags(content_dir: Path = Path("content/posts")) -> dict:
    """Analyze tags across all articles.

    Returns:
        Dict with statistics and normalized versions
    """
    stats = {
        "total_articles": 0,
        "total_tags": 0,
        "unique_tags": set(),
        "tags_per_article": [],
        "normalized_stats": {
            "total_tags": 0,
            "unique_tags": set(),
            "tags_per_article": [],
            "discarded": 0,
        },
        "examples": [],
    }

    for article_path in content_dir.glob("*.md"):
        try:
            post = frontmatter.load(str(article_path))
            tags = post.get("tags", [])
            if not isinstance(tags, list):
                tags = []

            if not tags:
                continue

            stats["total_articles"] += 1
            stats["total_tags"] += len(tags)
            stats["unique_tags"].update(tags)
            stats["tags_per_article"].append(len(tags))

            # Normalize
            normalized = normalize_tags(tags, max_tags=5)
            discarded = len(tags) - len(normalized)

            stats["normalized_stats"]["total_tags"] += len(normalized)
            stats["normalized_stats"]["unique_tags"].update(normalized)
            stats["normalized_stats"]["tags_per_article"].append(len(normalized))
            stats["normalized_stats"]["discarded"] += discarded

            # Save example for display
            if len(stats["examples"]) < 5:
                stats["examples"].append(
                    {
                        "title": post.get("title", "Unknown"),
                        "original": tags,
                        "normalized": normalized,
                        "discarded": discarded,
                    }
                )

        except Exception as e:
            console.print(f"[yellow]Warning: Could not process {article_path}: {e}")

    return stats


def print_statistics(stats: dict):
    """Print tag statistics."""
    console.print("\n[bold cyan]═══ Current Tag Statistics ═══[/bold cyan]")
    console.print(f"Total articles: {stats['total_articles']}")
    console.print(f"Total tags: {stats['total_tags']}")
    console.print(f"Unique tags: {len(stats['unique_tags'])}")
    avg_tags = sum(stats["tags_per_article"]) / len(stats["tags_per_article"])
    console.print(f"Average tags per article: {avg_tags:.1f}")

    console.print("\n[bold green]═══ After Normalization ═══[/bold green]")
    console.print(f"Total tags: {stats['normalized_stats']['total_tags']}")
    console.print(f"Unique tags: {len(stats['normalized_stats']['unique_tags'])}")
    avg_normalized = sum(stats["normalized_stats"]["tags_per_article"]) / len(
        stats["normalized_stats"]["tags_per_article"]
    )
    console.print(f"Average tags per article: {avg_normalized:.1f}")
    console.print(
        f"Tags discarded (unrecognized): {stats['normalized_stats']['discarded']}"
    )

    # Calculate improvements
    tag_reduction = (
        1 - len(stats["normalized_stats"]["unique_tags"]) / len(stats["unique_tags"])
    ) * 100
    console.print("\n[bold magenta]Improvement:[/bold magenta]")
    console.print(f"Unique tags reduced by: {tag_reduction:.1f}%")
    console.print(
        f"From {len(stats['unique_tags'])} → {len(stats['normalized_stats']['unique_tags'])}"
    )


def print_examples(stats: dict):
    """Print example normalizations."""
    console.print("\n[bold cyan]═══ Example Normalizations ═══[/bold cyan]")

    for i, example in enumerate(stats["examples"], 1):
        console.print(f"\n[bold]{i}. {example['title'][:60]}...[/bold]")
        console.print(f"   Original ({len(example['original'])} tags):")
        console.print(f"     {', '.join(example['original'][:8])}...")
        console.print(f"   Normalized ({len(example['normalized'])} tags):")
        console.print(f"     {', '.join(example['normalized'])}")
        if example["discarded"] > 0:
            console.print(f"   [yellow]Discarded: {example['discarded']} tags[/yellow]")


def print_top_tags(stats: dict):
    """Print most common canonical tags."""
    console.print("\n[bold cyan]═══ Top 20 Canonical Tags ═══[/bold cyan]")

    # Count canonical tag frequency
    tag_counts = {}
    for article_path in Path("content/posts").glob("*.md"):
        try:
            post = frontmatter.load(str(article_path))
            tags = post.get("tags", [])
            normalized = normalize_tags(tags, max_tags=5)

            for tag in normalized:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
        except Exception:
            pass

    # Sort and display
    sorted_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:20]

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Tag", style="green")
    table.add_column("Count", justify="right", style="yellow")

    for tag, count in sorted_tags:
        table.add_row(tag, str(count))

    console.print(table)


def main():
    """Main entry point."""
    console.print("[bold cyan]Tag Normalization Analysis[/bold cyan]")
    console.print("Analyzing existing article tags...\n")

    stats = analyze_tags()

    if stats["total_articles"] == 0:
        console.print("[red]No articles found in content/posts/[/red]")
        return

    print_statistics(stats)
    print_examples(stats)
    print_top_tags(stats)

    console.print("\n[bold green]✓ Analysis complete![/bold green]")
    console.print(
        "\nNew articles will automatically use normalized tags via the tag_normalizer."
    )
    console.print(
        "To update existing articles, you can re-generate them or manually edit frontmatter."
    )


if __name__ == "__main__":
    main()
