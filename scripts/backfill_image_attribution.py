#!/usr/bin/env python3
"""Backfill photographer attribution for existing articles with stock photos.

Fetches photographer info from Unsplash/Pexels APIs and adds it to article frontmatter.
"""

import logging
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from typing import Any

import frontmatter
import httpx
from rich.console import Console

from src.config import get_config

console = Console()
logger = logging.getLogger(__name__)


def extract_unsplash_photo_id(url: str) -> str | None:
    """Extract photo ID from Unsplash URL."""
    # Format: https://images.unsplash.com/photo-{id}?...
    match = re.search(r"photo-([a-zA-Z0-9_-]+)", url)
    return match.group(1) if match else None


def extract_pexels_photo_id(url: str) -> str | None:
    """Extract photo ID from Pexels URL."""
    # Format: https://images.pexels.com/photos/{id}/...
    match = re.search(r"/photos/(\d+)", url)
    return match.group(1) if match else None


def get_unsplash_attribution(
    photo_id: str, api_key: str
) -> tuple[str, str | None] | None:
    """Fetch photographer info from Unsplash API.

    Returns:
        Tuple of (photographer_name, photographer_url) or None
    """
    try:
        response = httpx.get(
            f"https://api.unsplash.com/photos/{photo_id}",
            headers={"Authorization": f"Client-ID {api_key}"},
            timeout=10.0,
        )
        response.raise_for_status()
        data = response.json()

        user = data.get("user", {})
        photographer_name = user.get("name", "Unknown")
        photographer_username = user.get("username", "")
        photographer_url = (
            f"https://unsplash.com/@{photographer_username}"
            if photographer_username
            else None
        )

        return (photographer_name, photographer_url)
    except Exception as e:
        logger.warning(f"Failed to fetch Unsplash attribution for {photo_id}: {e}")
        return None


def get_pexels_attribution(
    photo_id: str, api_key: str
) -> tuple[str, str | None] | None:
    """Fetch photographer info from Pexels API.

    Returns:
        Tuple of (photographer_name, photographer_url) or None
    """
    try:
        response = httpx.get(
            f"https://api.pexels.com/v1/photos/{photo_id}",
            headers={"Authorization": api_key},
            timeout=10.0,
        )
        response.raise_for_status()
        data = response.json()

        photographer_name = data.get("photographer", "Unknown")
        photographer_url = data.get("photographer_url")

        return (photographer_name, photographer_url)
    except Exception as e:
        logger.warning(f"Failed to fetch Pexels attribution for {photo_id}: {e}")
        return None


def backfill_article_attribution(article_path: Path, config: Any) -> bool:
    """Add photographer attribution to an article if missing.

    Returns:
        True if attribution was added, False otherwise
    """
    try:
        with open(article_path) as f:
            article = frontmatter.load(f)

        if "cover" not in article.metadata or not isinstance(
            article.metadata["cover"], dict
        ):
            return False

        cover = article.metadata["cover"]
        image_url = cover.get("image", "")

        # Skip if already has attribution
        if cover.get("photographer"):
            return False

        # Detect source and fetch attribution
        photographer_name = None
        photographer_url = None
        image_source = None

        if "unsplash.com" in image_url:
            photo_id = extract_unsplash_photo_id(image_url)
            if photo_id and config.unsplash_api_key:
                attribution = get_unsplash_attribution(
                    photo_id, config.unsplash_api_key
                )
                if attribution:
                    photographer_name, photographer_url = attribution
                    image_source = "unsplash"

        elif "pexels.com" in image_url:
            photo_id = extract_pexels_photo_id(image_url)
            if photo_id and config.pexels_api_key:
                attribution = get_pexels_attribution(photo_id, config.pexels_api_key)
                if attribution:
                    photographer_name, photographer_url = attribution
                    image_source = "pexels"

        elif (
            "oaidalleapiprodscus.blob.core.windows.net" in image_url
            or "/images/" in image_url
        ):
            # DALL-E generated or local image
            photographer_name = "OpenAI DALL-E 3"
            photographer_url = "https://openai.com/dall-e-3"
            image_source = "dalle-3"

        # Update frontmatter if we got attribution
        if photographer_name:
            cover["photographer"] = photographer_name
            if photographer_url:
                cover["photographer_url"] = photographer_url
            if image_source:
                cover["image_source"] = image_source

            # Save updated article
            with open(article_path, "w") as f:
                f.write(frontmatter.dumps(article))

            console.print(
                f"[green]✓[/green] {article_path.name}: {photographer_name} ({image_source})"
            )
            return True

        return False

    except Exception as e:
        console.print(f"[red]✗[/red] {article_path.name}: {e}")
        logger.exception(f"Failed to backfill {article_path}")
        return False


def main():
    """Backfill attribution for all articles missing it."""
    config = get_config()

    if not config.unsplash_api_key and not config.pexels_api_key:
        console.print("[red]Error: No API keys configured[/red]")
        return 1

    content_dir = Path("content/posts")
    if not content_dir.exists():
        console.print(f"[red]Error: {content_dir} not found[/red]")
        return 1

    articles = list(content_dir.glob("*.md"))
    console.print(f"[bold]Checking {len(articles)} articles...[/bold]\n")

    updated_count = 0
    for article_path in articles:
        if backfill_article_attribution(article_path, config):
            updated_count += 1

    console.print(
        f"\n[bold green]✓ Updated {updated_count} articles with attribution[/bold green]"
    )
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    sys.exit(main())
