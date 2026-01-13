"""Tests for recent-article cache date parsing.

Regression coverage: avoid offset-naive vs offset-aware datetime comparisons
when loading markdown frontmatter into the recent content cache.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from src.deduplication.recent_content_cache import RecentContentCache


def _write_post(path: Path, *, frontmatter_yaml: str) -> None:
    content = f"""---
{frontmatter_yaml}
---
Body.
"""
    path.write_text(content, encoding="utf-8")


def test_recent_content_cache_normalizes_dates_to_utc(tmp_path: Path) -> None:
    now_utc = datetime.now(UTC).replace(microsecond=0)

    within_window_utc = (
        (now_utc - timedelta(hours=1)).isoformat().replace("+00:00", "Z")
    )
    within_window_naive = (
        (now_utc - timedelta(hours=2)).replace(tzinfo=None).isoformat()
    )
    today_date = now_utc.date().isoformat()

    old_date = (now_utc - timedelta(days=30)).date().isoformat()

    # 1) generated_at as a quoted ISO string (string branch)
    _write_post(
        tmp_path / "recent_str_utc.md",
        frontmatter_yaml=f"""title: Recent (string, utc)
summary: s
tags: [a]
generated_at: \"{within_window_utc}\"""",
    )

    # 2) generated_at as a quoted naive ISO string (string branch, tzinfo None)
    _write_post(
        tmp_path / "recent_str_naive.md",
        frontmatter_yaml=f"""title: Recent (string, naive)
summary: s
tags: [a]
generated_at: \"{within_window_naive}\"""",
    )

    # 3) date as an unquoted YAML date (often parsed as datetime.date)
    _write_post(
        tmp_path / "recent_date.md",
        frontmatter_yaml=f"""title: Recent (date)
summary: s
tags: [a]
date: {today_date}""",
    )

    # 4) Old article should be ignored
    _write_post(
        tmp_path / "old.md",
        frontmatter_yaml=f"""title: Old
summary: s
tags: [a]
date: {old_date}""",
    )

    cache = RecentContentCache(content_dir=tmp_path, cache_days=7)

    cached_paths = {Path(a.filepath).name for a in cache.cache}
    assert cached_paths == {
        "recent_str_utc.md",
        "recent_str_naive.md",
        "recent_date.md",
    }

    for article in cache.cache:
        assert article.generated_at.tzinfo is not None
        assert article.generated_at.utcoffset() == timedelta(0)
