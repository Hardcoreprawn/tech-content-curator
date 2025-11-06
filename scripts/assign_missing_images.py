#!/usr/bin/env python3
"""Assign gradient library images to articles missing cover images."""

import sys
from pathlib import Path

import frontmatter

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import get_config
from src.images import select_or_create_cover_image


def main():
    content_dir = Path("content/posts")
    articles = list(content_dir.glob("*.md"))

    # Get Hugo base URL from config
    config = get_config()
    base_url = config.hugo_base_url

    fixed = 0
    for article_path in articles:
        post = frontmatter.load(str(article_path))

        # Check if already has cover image
        cover = post.metadata.get("cover", {})
        if isinstance(cover, dict) and cover.get("image"):
            continue

        # Extract tags and slug
        tags = post.metadata.get("tags", [])
        slug = article_path.stem

        # Generate gradient image with base URL
        hero_path, icon_path = select_or_create_cover_image(tags, slug, base_url)

        # Update frontmatter
        post.metadata["cover"] = {
            "image": hero_path,
            "alt": post.metadata.get("title", "Article cover image"),
            "caption": "",
        }
        post.metadata["images"] = [icon_path]

        # Save
        with open(article_path, "w", encoding="utf-8") as f:
            f.write(frontmatter.dumps(post))

        fixed += 1
        print(f"✓ {slug}")

    print(f"\n✅ Assigned images to {fixed} articles")


if __name__ == "__main__":
    main()
