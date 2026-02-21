"""Generate a weekly digest markdown file from recent posts."""

from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

# Add parent directory to path to resolve src imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import get_content_dir
from src.content.digest import build_digest_markdown, load_recent_posts


def main() -> int:
    """Generate weekly digest from the last 7 days of posts."""
    content_dir = get_content_dir()
    now = datetime.now(UTC)
    items = load_recent_posts(content_dir, days=7, now=now)
    digest = build_digest_markdown(
        items, start_date=now - timedelta(days=7), end_date=now
    )

    output_dir = Path("data") / "digests"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"weekly_digest_{now.date().isoformat()}.md"
    output_path.write_text(digest, encoding="utf-8")

    print(f"Wrote digest to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
