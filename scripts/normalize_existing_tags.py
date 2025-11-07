#!/usr/bin/env python3
"""Retroactively normalize tags in existing articles.

Applies the canonical tag taxonomy to all published articles,
updating their frontmatter in-place.
"""

import argparse
from pathlib import Path

import frontmatter
from rich.console import Console
from rich.progress import track
from rich.table import Table

from src.content.tag_normalizer import normalize_tags

console = Console()


def normalize_article_tags(filepath: Path, dry_run: bool = True) -> dict:
    """Normalize tags in a single article.

    Returns:
        dict with changes: {
            'original': list[str],
            'normalized': list[str],
            'changed': bool
        }
    """
    post = frontmatter.load(str(filepath))
    original_tags = post.metadata.get("tags", [])

    if not original_tags:
        return {"original": [], "normalized": [], "changed": False}

    # Ensure tags is a list of strings
    if isinstance(original_tags, str):
        original_tags = [original_tags]
    elif not isinstance(original_tags, list):
        original_tags = [str(original_tags)]

    normalized_tags = normalize_tags(original_tags, max_tags=5)
    changed = original_tags != normalized_tags

    if changed and not dry_run:
        post.metadata["tags"] = normalized_tags
        with open(filepath, "wb") as f:
            frontmatter.dump(post, f)

    return {
        "original": original_tags,
        "normalized": normalized_tags,
        "changed": changed,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Normalize tags in existing articles"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be changed without modifying files",
    )
    parser.add_argument(
        "--path",
        type=str,
        default="content/posts",
        help="Path to articles directory (default: content/posts)",
    )
    args = parser.parse_args()

    content_dir = Path(args.path)
    if not content_dir.exists():
        console.print(f"[red]✗[/red] Directory not found: {content_dir}")
        return 1

    articles = list(content_dir.glob("*.md"))
    if not articles:
        console.print(f"[yellow]No articles found in {content_dir}[/yellow]")
        return 0

    console.print(
        f"\n[bold blue]{'DRY RUN: ' if args.dry_run else ''}Normalizing tags in {len(articles)} articles...[/bold blue]\n"
    )

    changes = []
    unchanged = 0

    for filepath in track(articles, description="Processing articles..."):
        result = normalize_article_tags(filepath, dry_run=args.dry_run)
        if result["changed"]:
            changes.append((filepath.name, result))
        else:
            unchanged += 1

    # Summary
    console.print("\n[bold cyan]Summary:[/bold cyan]")
    console.print(f"  Total articles: {len(articles)}")
    console.print(f"  Changed: [yellow]{len(changes)}[/yellow]")
    console.print(f"  Unchanged: [green]{unchanged}[/green]")

    if changes:
        console.print("\n[bold yellow]Changes Preview (first 10):[/bold yellow]")

        table = Table(show_header=True, header_style="bold")
        table.add_column("Article", width=40)
        table.add_column("Before", width=25)
        table.add_column("After", width=25)

        for filename, result in changes[:10]:
            before = ", ".join(result["original"][:3])
            if len(result["original"]) > 3:
                before += f" +{len(result['original']) - 3}"

            after = ", ".join(result["normalized"])

            table.add_row(filename[:40], before, after)

        console.print(table)

        if len(changes) > 10:
            console.print(f"\n[dim]... and {len(changes) - 10} more articles[/dim]")

    if args.dry_run:
        console.print(
            "\n[bold green]✓[/bold green] Dry run complete. Run without --dry-run to apply changes."
        )
    else:
        console.print(
            f"\n[bold green]✓[/bold green] Successfully normalized tags in {len(changes)} articles."
        )

    return 0


if __name__ == "__main__":
    exit(main())
