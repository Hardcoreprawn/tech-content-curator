"""Tests for weekly digest generation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import frontmatter

from src.content.digest import build_digest_markdown, load_recent_posts


def _write_post(path: Path, date_str: str, title: str, summary: str) -> None:
    post = frontmatter.Post(
        content="Body",
        title=title,
        date=date_str,
        summary=summary,
    )
    path.write_text(frontmatter.dumps(post), encoding="utf-8")


def test_load_recent_posts_filters_by_days(tmp_path: Path) -> None:
    content_dir = tmp_path / "content" / "posts"
    content_dir.mkdir(parents=True)

    today = datetime(2026, 1, 17, tzinfo=UTC)
    recent_date = (today - timedelta(days=2)).date().isoformat()
    old_date = (today - timedelta(days=20)).date().isoformat()

    _write_post(
        content_dir / "2026-01-15-recent.md",
        recent_date,
        "Recent Post",
        "Recent summary",
    )
    _write_post(
        content_dir / "2025-12-28-old.md",
        old_date,
        "Old Post",
        "Old summary",
    )

    items = load_recent_posts(
        content_dir,
        days=7,
        base_url="https://example.com",
        now=today,
    )

    assert len(items) == 1
    assert items[0].title == "Recent Post"
    assert items[0].url == "https://example.com/posts/recent"


def test_build_digest_markdown_includes_items(tmp_path: Path) -> None:
    content_dir = tmp_path / "content" / "posts"
    content_dir.mkdir(parents=True)

    today = datetime(2026, 1, 17, tzinfo=UTC)
    recent_date = (today - timedelta(days=1)).date().isoformat()

    _write_post(
        content_dir / "2026-01-16-item.md",
        recent_date,
        "Digest Item",
        "Digest summary",
    )

    items = load_recent_posts(
        content_dir,
        days=7,
        base_url="https://example.com",
        now=today,
    )

    digest = build_digest_markdown(
        items, start_date=today - timedelta(days=7), end_date=today
    )

    assert "Weekly Digest" in digest
    assert "Digest Item" in digest
    assert "https://example.com/posts/item" in digest
    assert "Digest summary" in digest
