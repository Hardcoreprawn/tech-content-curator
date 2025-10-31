#!/usr/bin/env python3
"""
Test script for post-generation deduplication.

Run this to:
1. Load all existing articles
2. Check for duplicates
3. Report findings
4. Show which articles should be removed

Usage:
    python scripts/test_dedup.py              # Check all articles
    python scripts/test_dedup.py --verbose    # Show detailed metrics
    python scripts/test_dedup.py --remove     # Actually remove duplicates (careful!)
"""

import argparse
import json
import sys
from pathlib import Path

import frontmatter
from rich.console import Console
from rich.table import Table

from src.config import get_content_dir
from src.post_gen_dedup import find_duplicate_articles, report_duplicate_candidates

# Ensure UTF-8 encoding on Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

console = Console(force_terminal=False, legacy_windows=False)


def load_article_metadata(article_path: Path) -> dict:
    """Load article metadata from markdown file."""
    try:
        with open(article_path, encoding="utf-8") as f:
            post = frontmatter.load(f)

        return {
            "path": str(article_path),
            "filename": article_path.name,
            "title": post.metadata.get("title", ""),
            "summary": post.metadata.get("summary", ""),
            "tags": post.metadata.get("tags", []),
            "date": post.metadata.get("date", ""),
            "quality_score": post.metadata.get("quality_score", 0),
            "sources": post.metadata.get("sources", []),
        }
    except Exception as e:
        console.print(f"[red]Error loading {article_path.name}: {e}[/red]")
        return None


def get_source_info(metadata: dict) -> str:
    """Get source info from metadata."""
    sources = metadata.get("sources", [])
    if sources:
        source = sources[0]
        author = source.get("author", "unknown")
        platform = source.get("platform", "unknown")
        return f"{author} ({platform})"
    return "unknown source"


def main():
    parser = argparse.ArgumentParser(
        description="Test deduplication on existing articles"
    )
    parser.add_argument(
        "--verbose", action="store_true", help="Show detailed similarity metrics"
    )
    parser.add_argument(
        "--remove",
        action="store_true",
        help="Remove duplicate articles (keeps higher quality)",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Show what would be removed (no action)"
    )
    args = parser.parse_args()

    # Load all articles
    content_dir = get_content_dir()
    posts_dir = content_dir  # get_content_dir() already returns the posts directory

    if not posts_dir.exists():
        console.print(f"[red]Posts directory not found: {posts_dir}[/red]")
        return

    article_files = sorted(posts_dir.glob("*.md"))
    console.print(f"\n[blue]Loading {len(article_files)} articles...[/blue]")

    # Load metadata
    articles = []
    for article_file in article_files:
        metadata = load_article_metadata(article_file)
        if metadata:
            articles.append(metadata)

    console.print(f"[green]✓ Loaded {len(articles)} articles[/green]\n")

    # Find duplicates
    console.print("[yellow]Checking for duplicates...[/yellow]\n")
    duplicates = find_duplicate_articles(articles)

    if not duplicates:
        console.print("[green]✓ No duplicates found![/green]")
        return

    # Report duplicates
    report_duplicate_candidates(duplicates, verbose=args.verbose)

    # Create detailed table
    table = Table(title="Duplicate Candidates", show_header=True, header_style="bold")
    table.add_column("Pair", width=5)
    table.add_column("Article 1", width=35)
    table.add_column("Article 2", width=35)
    table.add_column("Similarity", width=12)
    table.add_column("Action", width=20)

    for i, dup in enumerate(duplicates, 1):
        article1 = next((a for a in articles if a["path"] == str(dup.article1_path)), None)
        article2 = next((a for a in articles if a["path"] == str(dup.article2_path)), None)

        if not article1 or not article2:
            continue

        # Determine which to keep (higher quality score)
        score1 = article1.get("quality_score", 0)
        score2 = article2.get("quality_score", 0)

        if score1 >= score2:
            keep = "Keep Article 1"
            remove = "Remove Article 2"
        else:
            keep = "Remove Article 1"
            remove = "Keep Article 2"

        table.add_row(
            str(i),
            f"{article1['filename']}\n[dim]{get_source_info(article1)}[/dim]",
            f"{article2['filename']}\n[dim]{get_source_info(article2)}[/dim]",
            f"{dup.overall_score:.0%}",
            f"[green]{keep}[/green]\n[red]{remove}[/red]",
        )

    console.print(table)

    # Handle removal
    if args.remove or args.dry_run:
        console.print("\n[yellow]Analyzing removal candidates...[/yellow]\n")

        to_remove = []
        for dup in duplicates:
            article1 = next((a for a in articles if a["path"] == str(dup.article1_path)), None)
            article2 = next((a for a in articles if a["path"] == str(dup.article2_path)), None)

            if not article1 or not article2:
                continue

            score1 = article1.get("quality_score", 0)
            score2 = article2.get("quality_score", 0)

            # Strategy: Remove article2 (keep article1 for consistency)
            # Primary: Remove lower quality version
            # Secondary: Remove second article (keep first) if equal quality
            reason = ""
            
            if abs(score1 - score2) > 0.01:  # Meaningful quality difference
                if score1 < score2:
                    to_remove.append(
                        {
                            "path": Path(article1["path"]),
                            "reason": f"Lower quality ({score1:.2f} vs {score2:.2f})",
                            "duplicate_of": article2["filename"],
                        }
                    )
                elif score2 < score1:
                    to_remove.append(
                        {
                            "path": Path(article2["path"]),
                            "reason": f"Lower quality ({score2:.2f} vs {score1:.2f})",
                            "duplicate_of": article1["filename"],
                        }
                    )
            else:
                # Equal quality: Keep article1 (first), remove article2 (second)
                # This is deterministic and prevents unnecessary churn
                to_remove.append(
                    {
                        "path": Path(article2["path"]),
                        "reason": f"Duplicate (keep first article, equal quality {score1:.2f}≈{score2:.2f})",
                        "duplicate_of": article1["filename"],
                    }
                )

        if to_remove:
            console.print(f"[yellow]Found {len(to_remove)} articles to remove:[/yellow]\n")

            for item in to_remove:
                console.print(f"  [red]✗[/red] {item['path'].name}")
                console.print(f"    Reason: {item['reason']}")
                console.print(f"    Duplicate of: {item['duplicate_of']}")

            if args.dry_run:
                console.print("\n[cyan]DRY RUN - No files removed[/cyan]")
            elif args.remove:
                console.print("\n[yellow]Removing duplicates...[/yellow]")
                for item in to_remove:
                    try:
                        item["path"].unlink()
                        console.print(f"[green]✓ Removed {item['path'].name}[/green]")
                    except Exception as e:
                        console.print(f"[red]✗ Failed to remove {item['path'].name}: {e}[/red]")

                console.print("\n[green]Removal complete![/green]")
                console.print("[yellow]Don't forget to commit and push changes[/yellow]")
        else:
            console.print("[green]✓ No articles need removal[/green]")


if __name__ == "__main__":
    main()
