"""Weekly digest generation for recent posts."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import frontmatter

from ..config import get_config
from ..utils.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class DigestItem:
    """Summary entry for weekly digest output."""

    title: str
    url: str
    summary: str
    published_at: datetime


def _parse_date(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day, tzinfo=UTC)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value)
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
        except ValueError:
            try:
                parsed_date = date.fromisoformat(value)
                return datetime(
                    parsed_date.year, parsed_date.month, parsed_date.day, tzinfo=UTC
                )
            except ValueError:
                return None
    return None


def _slug_from_filename(filename: str) -> str:
    stem = Path(filename).stem
    parts = stem.split("-", 3)
    return parts[3] if len(parts) == 4 else stem


def _post_url(slug: str, base_url: str) -> str:
    return f"{base_url.rstrip('/')}/posts/{slug}"


def load_recent_posts(
    content_dir: Path,
    days: int = 7,
    base_url: str | None = None,
    now: datetime | None = None,
) -> list[DigestItem]:
    """Load recent posts from content directory.

    Args:
        content_dir: Path to content/posts directory
        days: Number of days to include
        base_url: Optional site base URL (defaults to config)
        now: Optional current time override (for tests)

    Returns:
        List of DigestItem entries sorted by newest first
    """
    if base_url is None:
        base_url = get_config().hugo_base_url
    now = now or datetime.now(UTC)
    cutoff = now - timedelta(days=days)

    items: list[DigestItem] = []

    for path in sorted(content_dir.glob("*.md")):
        try:
            post = frontmatter.load(str(path))
        except (OSError, ValueError) as exc:
            logger.warning(
                "Failed to parse post",
                exc_info=True,
                extra={"path": str(path), "error": str(exc)},
            )
            continue

        published = _parse_date(post.get("date"))
        if not published or published < cutoff:
            continue

        title = str(post.get("title") or path.stem)
        summary = str(post.get("summary") or "")
        slug = _slug_from_filename(path.name)
        url = _post_url(slug, base_url)

        items.append(
            DigestItem(
                title=title,
                url=url,
                summary=summary,
                published_at=published,
            )
        )

    items.sort(key=lambda item: item.published_at, reverse=True)
    return items


def build_digest_markdown(
    items: Iterable[DigestItem],
    start_date: datetime,
    end_date: datetime,
) -> str:
    """Build markdown for a weekly digest.

    Args:
        items: DigestItem entries
        start_date: Digest start date
        end_date: Digest end date

    Returns:
        Markdown digest string
    """
    lines = [
        "# Weekly Digest",
        "",
        f"Coverage: {start_date.date().isoformat()} → {end_date.date().isoformat()}",
        "",
    ]

    items_list = list(items)
    if not items_list:
        lines.append("No new posts in this period.")
        return "\n".join(lines)

    for item in items_list:
        lines.append(f"- [{item.title}]({item.url}) — {item.summary}")

    return "\n".join(lines)
