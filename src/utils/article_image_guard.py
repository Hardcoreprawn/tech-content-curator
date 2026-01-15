"""Guard against broken cover images in article frontmatter."""

from __future__ import annotations

from pathlib import Path

import frontmatter
from rich.console import Console

from .file_io import atomic_write_text
from .logging import get_logger

console = Console()
logger = get_logger(__name__)


def _normalize_cover_value(value: object) -> str:
    if isinstance(value, str):
        return value.strip()
    return ""


def _is_local_image(path: str) -> bool:
    return path.startswith("/images/") or path.startswith("images/")


def _local_image_exists(images_dir: Path, path: str) -> bool:
    filename = path.rsplit("/", 1)[-1]
    return (images_dir / filename).exists()


def guard_article_images(
    content_dir: Path, images_dir: Path, dry_run: bool = False
) -> tuple[int, int]:
    """Remove broken/external cover images from article frontmatter.

    Returns:
        Tuple of (processed_count, modified_count)
    """
    processed = 0
    modified = 0

    for md_path in sorted(content_dir.glob("*.md")):
        processed += 1
        try:
            post = frontmatter.load(md_path)
        except (OSError, ValueError) as exc:
            logger.warning("Failed to read frontmatter", exc_info=True)
            console.print(f"[yellow]⚠ Failed to read {md_path.name}: {exc}[/yellow]")
            continue

        cover = post.metadata.get("cover")
        if not isinstance(cover, dict):
            cover = {}

        image_value = _normalize_cover_value(cover.get("image"))
        icon_value = _normalize_cover_value(post.metadata.get("icon"))

        is_external = image_value.startswith("http")
        is_local = _is_local_image(image_value)
        missing_local = is_local and not _local_image_exists(images_dir, image_value)

        if not image_value:
            continue

        if is_external or missing_local:
            cover["image"] = ""
            cover["alt"] = ""
            post.metadata["cover"] = cover
            if icon_value:
                post.metadata["icon"] = ""
            modified += 1

            reason = "external" if is_external else "missing_local"
            logger.info(
                "Cleared broken cover image",
                extra={
                    "phase": "publish",
                    "event": "cover_image_guard",
                    "article": md_path.name,
                    "reason": reason,
                },
            )
            console.print(
                f"[yellow]⚠ Cleared {reason} cover image in {md_path.name}[/yellow]"
            )

            if not dry_run:
                updated = frontmatter.dumps(post)
                atomic_write_text(md_path, updated)

    return processed, modified


def main() -> None:
    content_dir = Path("content/posts")
    images_dir = Path("site/static/images")
    processed, modified = guard_article_images(content_dir, images_dir)
    console.print(
        f"[green]✓[/green] Image guard complete: {modified} updated / {processed} processed"
    )


if __name__ == "__main__":
    main()
