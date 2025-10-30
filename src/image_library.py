"""Reusable image library and local variant generation.

Goals:
- Avoid per-article AI image costs by reusing a small set of abstract base images
- Keep variety by applying deterministic color variants per article
- Stay relevant by picking a base image based on primary tag/topic

Outputs:
- Hero image: 1792x1024
- Icon image: 512x512 (square)

Base images live in site/static/images/library/*.png (1024x1024).
Article-specific variants are saved in site/static/images/ as <slug>.png and <slug>-icon.png.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Iterable, Tuple

from PIL import Image, ImageDraw
from rich.console import Console

from .config import get_project_root
from .image_catalog import find_reusable_image

console = Console()


def _images_dir() -> Path:
    return get_project_root() / "site" / "static" / "images"


def _library_dir() -> Path:
    d = _images_dir() / "library"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _ensure_posts_dir() -> Path:
    d = _images_dir()
    d.mkdir(parents=True, exist_ok=True)
    return d


def _hash_to_index(seed: str, modulo: int) -> int:
    h = hashlib.sha1(seed.encode("utf-8")).hexdigest()
    return int(h[:8], 16) % max(1, modulo)


def build_gradient_library_if_empty(count: int = 12) -> list[Path]:
    """Create a small set of abstract gradient squares if library is empty.

    Returns the list of library image paths (existing + created).
    """
    lib = _library_dir()
    existing = sorted(lib.glob("abstract-*.png"))
    if existing:
        return existing

    console.print(f"[dim]Building abstract gradient library ({count} images)...[/dim]")
    size = 1024
    for i in range(1, count + 1):
        img = Image.new("RGB", (size, size))
        draw = ImageDraw.Draw(img)
        # Simple multi-stop linear gradient left->right
        # Vary hue bands by index to produce diverse palettes
        for x in range(size):
            t = x / (size - 1)
            # Palette: cycle through 3 color anchors per image
            base = (i * 37) % 360  # pseudo hue seed
            r = int(128 + 127 * (t))
            g = int(128 + 127 * (1 - t))
            b = int(128 + 127 * (0.5 - abs(t - 0.5)) * 2)
            # shift channels differently per image to diversify palettes
            r = (r + (base * 3) % 70) % 256
            g = (g + (base * 5) % 70) % 256
            b = (b + (base * 7) % 70) % 256
            draw.line([(x, 0), (x, size)], fill=(r, g, b))
        # Soft vignette circle to add depth
        vignette = Image.new("L", (size, size), 0)
        vdraw = ImageDraw.Draw(vignette)
        vdraw.ellipse([size * -0.2, size * -0.2, size * 1.2, size * 1.2], fill=180)
        img.putalpha(vignette)
        out = img.convert("RGB")
        out_path = lib / f"abstract-{i:02d}.png"
        out.save(out_path, "PNG")
    return sorted(lib.glob("abstract-*.png"))


def _apply_variant(base: Image.Image, variant_seed: str) -> Image.Image:
    """Apply a deterministic color shift variant based on seed."""
    # Simple HSV-like channel rotation using per-pixel transform
    # Keep it fast: apply per-channel multipliers derived from hash
    h = hashlib.md5(variant_seed.encode("utf-8")).digest()
    # Derive subtle +/- 20% multipliers per channel
    def scale(byte: int) -> float:
        return 0.8 + (byte / 255.0) * 0.4  # [0.8, 1.2]

    rm, gm, bm = scale(h[0]), scale(h[1]), scale(h[2])
    r, g, b = base.split()
    r = r.point(lambda v: max(0, min(255, int(v * rm))))
    g = g.point(lambda v: max(0, min(255, int(v * gm))))
    b = b.point(lambda v: max(0, min(255, int(v * bm))))
    return Image.merge("RGB", (r, g, b))


def _make_derivatives(base_path: Path, slug: str, base_url: str = "") -> Tuple[str, str]:
    """Create hero (1792x1024) and icon (512x512) from a base image with a variant.

    Args:
        base_path: Path to the source image
        slug: Article slug for filename
        base_url: Base URL for the site (e.g., "https://example.com/blog/")

    Returns:
        Tuple of web paths (hero_url, icon_url).
    """
    images_dir = _ensure_posts_dir()
    with Image.open(base_path) as base:
        # Variant for variety per-article
        variant = _apply_variant(base.convert("RGB"), slug)
        # Hero
        hero = variant.resize((1792, 1024), Image.Resampling.LANCZOS)
        hero_path = images_dir / f"{slug}.png"
        hero.save(hero_path, "PNG")
        # Icon (center crop then 512)
        w, h = variant.size
        s = min(w, h)
        left = (w - s) // 2
        top = (h - s) // 2
        icon = variant.crop((left, top, left + s, top + s)).resize(
            (512, 512), Image.Resampling.LANCZOS
        )
        icon_path = images_dir / f"{slug}-icon.png"
        icon.save(icon_path, "PNG")
    
    # Return absolute URLs if base_url provided, otherwise relative paths
    if base_url:
        base_url = base_url.rstrip("/")
        return (f"{base_url}/images/{slug}.png", f"{base_url}/images/{slug}-icon.png")
    else:
        return (f"/images/{slug}.png", f"/images/{slug}-icon.png")


def select_or_create_cover_image(tags: Iterable[str], slug: str, base_url: str = "") -> Tuple[str, str]:
    """Pick a reusable base by tag and create local variants for this article.

    Strategy (priority order):
    1. Reuse an existing AI-generated image if tag matches (no cost)
    2. Fall back to gradient library and create local variants

    Args:
        tags: Article tags for image selection
        slug: Article slug for filename
        base_url: Base URL for the site (e.g., "https://example.com/blog/")

    Returns:
        Tuple of (hero_url, icon_url)
    """
    # First, try to find an existing AI image by tag
    existing = find_reusable_image(list(tags))
    if existing:
        # If we found an existing image, make sure it has the proper base URL
        hero_url, icon_url = existing
        if base_url and not hero_url.startswith("http"):
            base_url = base_url.rstrip("/")
            hero_url = f"{base_url}{hero_url}" if hero_url.startswith("/") else f"{base_url}/{hero_url}"
            icon_url = f"{base_url}{icon_url}" if icon_url.startswith("/") else f"{base_url}/{icon_url}"
        return (hero_url, icon_url)

    # Fall back to gradient library
    bases = build_gradient_library_if_empty()
    key = "-".join(list(tags)[:1]) or slug
    idx = _hash_to_index(key.lower(), len(bases))
    base_path = bases[idx]
    return _make_derivatives(base_path, slug, base_url)
