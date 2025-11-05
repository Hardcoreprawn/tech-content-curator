"""Catalog and reuse existing AI-generated images.

Scans content/posts/*.md frontmatter to build a map of:
  tag -> list of (image_path, article_slug)

When generating a new article, we prefer an existing AI image with a matching tag
over creating a new one or falling back to gradients.
"""

from __future__ import annotations

import json
from pathlib import Path

import frontmatter
from rich.console import Console

from ..config import get_content_dir, get_project_root
from ..utils.logging import get_logger

logger = get_logger(__name__)
console = Console()


def _catalog_path() -> Path:
    return get_project_root() / "data" / "image_catalog.json"


def build_image_catalog(
    force_rebuild: bool = False,
) -> dict[str, list[tuple[str, str]]]:
    """Build or load a catalog of tag->images from existing articles.

    Returns:
        Dict mapping tag -> [(image_url, article_slug), ...]
    """
    logger.debug(f"Building image catalog (force_rebuild={force_rebuild})")
    catalog_file = _catalog_path()
    if catalog_file.exists() and not force_rebuild:
        logger.debug("Loading existing image catalog from file")
        with open(catalog_file, encoding="utf-8") as f:
            return json.load(f)

    console.print("[dim]Building image catalog from existing articles...[/dim]")
    catalog: dict[str, list[tuple[str, str]]] = {}
    content_dir = get_content_dir()

    for md_file in content_dir.glob("*.md"):
        try:
            post = frontmatter.load(str(md_file))
            meta = post.metadata or {}
            tags = meta.get("tags", [])
            cover = meta.get("cover", {})
            image_url = cover.get("image") if isinstance(cover, dict) else None

            # Skip if no image or if it's a gradient/default
            if (
                not image_url
                or "library/" in image_url
                or "default-social" in image_url
            ):
                continue

            # Extract slug from image URL (e.g., /images/2025-10-30-something.png -> 2025-10-30-something)
            slug = Path(image_url).stem

            for tag in tags:
                tag_lower = tag.lower()
                if tag_lower not in catalog:
                    catalog[tag_lower] = []
                catalog[tag_lower].append((image_url, slug))

        except Exception as e:
            logger.warning(f"Failed to parse {md_file.name}: {type(e).__name__}: {e}")
            console.print(f"[yellow]⚠[/yellow] Failed to parse {md_file.name}: {e}")

    # Save catalog
    catalog_file.parent.mkdir(parents=True, exist_ok=True)
    with open(catalog_file, "w", encoding="utf-8") as f:
        json.dump(catalog, f, indent=2)

    logger.info(f"Image catalog built: {len(catalog)} unique tags, {sum(len(v) for v in catalog.values())} total images")
    console.print(f"[green]✓[/green] Image catalog built: {len(catalog)} unique tags")
    return catalog


def find_reusable_image(tags: list[str]) -> tuple[str, str] | None:
    """Find an existing AI image matching one of the given tags.

    Returns:
        (hero_url, icon_url) if found, else None
    """
    logger.debug(f"Looking for reusable image matching tags: {tags}")
    catalog = build_image_catalog()
    for tag in tags:
        candidates = catalog.get(tag.lower(), [])
        if candidates:
            # Pick the first match (could randomize or pick by quality later)
            image_url, _slug = candidates[0]
            # Derive icon path (convention: <slug>-icon.png)
            icon_url = image_url.replace(".png", "-icon.png")
            logger.debug(f"Found reusable image for tag '{tag}': {image_url}")
            return (image_url, icon_url)
    logger.debug(f"No reusable image found for tags: {tags}")
    return None
