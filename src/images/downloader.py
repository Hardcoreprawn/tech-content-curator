"""Download external images and persist local hero/icon derivatives.

Saves images to `site/static/images/<slug>.png` and `<slug>-icon.png` and
records a small license/attribution entry in `data/IMAGE_LICENSES.json`.
"""

from __future__ import annotations

import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path

import httpx
from PIL import Image

from ..config import get_project_root
from ..utils.logging import get_logger
from .library import _make_derivatives

logger = get_logger(__name__)


def _licenses_path() -> Path:
    p = get_project_root() / "data" / "IMAGE_LICENSES.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    if not p.exists():
        p.write_text("{}", encoding="utf-8")
    return p


def _record_license(
    slug: str, original_url: str, meta: dict, hero_path: str, icon_path: str
) -> None:
    p = _licenses_path()
    try:
        data = json.loads(p.read_text(encoding="utf-8") or "{}")
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        data = {}

    data[slug] = {
        "original_url": original_url,
        "photographer": meta.get("photographer"),
        "photographer_url": meta.get("photographer_url"),
        "source": meta.get("source"),
        "hero_path": hero_path,
        "icon_path": icon_path,
        "saved_at": datetime.now(UTC).isoformat(),
    }

    p.write_text(json.dumps(data, indent=2), encoding="utf-8")


def download_and_persist(
    url: str, slug: str, meta: dict | None = None, base_url: str = ""
) -> tuple[str, str]:
    """Download an external image and persist hero/icon derivatives.

    Args:
        url: External image URL
        slug: Article slug used for filenames
        meta: Optional attribution metadata (photographer, source, etc.)
        base_url: If provided, returned URLs will be absolute using this base; otherwise Hugo-relative paths are returned

    Returns:
        Tuple (hero_url, icon_url) — Hugo-relative paths like `/images/<slug>.png`

    Raises:
        ValueError on invalid content-type or download failure
    """
    meta = meta or {}
    logger.debug(f"Downloading image for slug={slug} from {url}")
    timeout = httpx.Timeout(10.0, read=30.0)
    headers = {"User-Agent": "tech-content-curator/1.0"}

    try:
        with httpx.stream("GET", url, timeout=timeout, headers=headers) as resp:
            resp.raise_for_status()
            content_type = resp.headers.get("content-type", "")
            if not content_type.startswith("image/"):
                raise ValueError(
                    f"URL did not return an image (content-type={content_type})"
                )

            # Save to a temporary file
            with tempfile.NamedTemporaryFile(delete=False) as tmpf:
                for chunk in resp.iter_bytes():
                    tmpf.write(chunk)
                tmp_path = Path(tmpf.name)

    except (httpx.HTTPError, OSError, ValueError) as e:
        logger.exception("Failed to download image %s", url)
        raise ValueError(f"Failed to download image: {e}") from e

    try:
        # Validate image by opening with Pillow
        with Image.open(tmp_path) as _img:
            pass
    except (OSError, ValueError) as e:
        tmp_path.unlink(missing_ok=True)
        logger.exception("Downloaded file is not a valid image")
        raise ValueError("Downloaded file is not a valid image") from e

    # Create derivatives using existing library helper
    try:
        hero_url, icon_url = _make_derivatives(tmp_path, slug, base_url)
    finally:
        # Remove temp file
        tmp_path.unlink(missing_ok=True)

    # Record license/attribution for auditing
    _record_license(slug, url, meta or {}, hero_url, icon_url)

    return hero_url, icon_url
