#!/usr/bin/env python3
"""Fix articles with expired Azure blob image URLs.

Finds articles with expired oaidalleapiprodscus.blob.core.windows.net URLs
and regenerates images using DALL-E.
"""

import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import frontmatter
from openai import OpenAI
from rich.console import Console

from src.config import get_config
from src.images.selector import CoverImageSelector

console = Console()
logger = logging.getLogger(__name__)


def has_expired_blob_url(content: str) -> bool:
    """Check if content has Azure blob storage URLs."""
    return "oaidalleapiprodscus.blob.core.windows.net" in content


def extract_slug_from_path(filepath: Path) -> str:
    """Extract slug from article filename."""
    return filepath.stem


def fix_article_images(article_path: Path) -> bool:
    """Fix expired images for a single article.

    Returns:
        True if images were regenerated, False otherwise
    """
    console.print(f"[blue]Checking {article_path.name}...[/blue]")

    # Load article
    content = article_path.read_text()

    if not has_expired_blob_url(content):
        console.print("  [dim]No expired blob URLs found[/dim]")
        return False

    console.print("  [yellow]⚠ Found expired Azure blob URLs[/yellow]")

    # Load article metadata using frontmatter
    article = frontmatter.load(str(article_path))

    title = str(article.get("title", "Article"))
    str(article.get("summary", ""))
    tags = article.get("tags", [])

    console.print(f"  [blue]Regenerating images for: {title}[/blue]")

    # Try stock photos first, then AI as fallback
    config = get_config()
    client = OpenAI(api_key=config.openai_api_key)
    selector = CoverImageSelector(client, config)

    try:
        # Full article content for better context
        full_content = article.content if hasattr(article, "content") else ""
        cover_image = selector.select(title, tags, full_content)
        hero_url = cover_image.url
        icon_url = cover_image.url

        console.print(f"  [green]✓ Selected {cover_image.source} image[/green]")
    except Exception as e:
        console.print(f"  [red]✗ Failed to select image: {e}[/red]")
        return False

    # Update article frontmatter metadata
    if "cover" not in article.metadata or not isinstance(
        article.metadata["cover"], dict
    ):
        article.metadata["cover"] = {}

    article.metadata["cover"]["image"] = hero_url
    article.metadata["icon"] = icon_url

    # Add image attribution
    if cover_image.photographer_name:
        article.metadata["cover"]["photographer"] = cover_image.photographer_name
        if cover_image.photographer_url:
            article.metadata["cover"]["photographer_url"] = cover_image.photographer_url
        article.metadata["cover"]["image_source"] = cover_image.source

    # Save updated article
    with open(article_path, "w") as f:
        f.write(frontmatter.dumps(article))

    console.print("  [green]✓ Updated images:[/green]")
    console.print(f"    Hero: {hero_url}")
    console.print(f"    Icon: {icon_url}")

    return True


def main():
    """Find and fix all articles with expired images."""
    content_dir = Path("content/posts")
    if not content_dir.exists():
        console.print(f"[red]Error: {content_dir} not found[/red]")
        return 1

    articles = list(content_dir.glob("*.md"))
    console.print(f"[bold]Found {len(articles)} articles to check[/bold]\n")

    fixed_count = 0
    for article_path in articles:
        try:
            if fix_article_images(article_path):
                fixed_count += 1
        except Exception as e:
            console.print(f"  [red]✗ Error: {e}[/red]")
            logger.exception(f"Failed to fix {article_path}")

    console.print(f"\n[bold green]✓ Fixed {fixed_count} articles[/bold green]")
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    sys.exit(main())
