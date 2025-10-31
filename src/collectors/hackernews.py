"""HackerNews content collector.

Collects top stories from HackerNews.
HackerNews is TIER_3 source - community-curated, high signal-to-noise.
"""

import time
from datetime import UTC, datetime

import httpx
from rich.console import Console

from ..models import CollectedItem, SourceType

console = Console()


def collect_from_hackernews(limit: int = 30) -> list[CollectedItem]:
    """Collect top stories from HackerNews.

    HackerNews is S-tier: community-curated, high signal-to-noise.

    Args:
        limit: Maximum number of stories to collect

    Returns:
        List of collected items from HackerNews
    """
    console.print("[blue]Collecting from HackerNews...[/blue]")

    items = []

    try:
        # HackerNews has a nice simple API
        with httpx.Client(timeout=30.0) as client:
            # Get top story IDs
            response = client.get(
                "https://hacker-news.firebaseio.com/v0/topstories.json"
            )
            response.raise_for_status()
            story_ids = response.json()[:limit]  # Top N stories

            console.print(f"  Fetching {len(story_ids)} top stories...")

            for story_id in story_ids:
                try:
                    # Get story details
                    response = client.get(
                        f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json"
                    )
                    response.raise_for_status()
                    story = response.json()

                    if not story or story.get("type") != "story":
                        continue

                    # Build content from title and text (if available)
                    content = story.get("title", "")
                    if story.get("text"):
                        content += f"\n\n{story['text']}"

                    # HN URLs can be external links or HN discussions
                    url = story.get(
                        "url", f"https://news.ycombinator.com/item?id={story_id}"
                    )

                    item = CollectedItem(
                        id=f"hn_{story_id}",
                        title=story.get("title", ""),
                        content=content,
                        source=SourceType.HACKERNEWS,
                        url=url,
                        author=story.get("by", "unknown"),
                        collected_at=datetime.now(UTC),
                        metadata={
                            "score": story.get("score", 0),
                            "comments": story.get("descendants", 0),
                            "time": story.get("time", 0),
                            "source_name": "hackernews",
                            "story_type": story.get("type"),
                        },
                    )
                    items.append(item)

                except Exception as e:
                    console.print(
                        f"[yellow]⚠[/yellow] Failed to fetch HN story {story_id}: {e}"
                    )
                    continue

                # Rate limiting - be nice to HN
                time.sleep(0.1)

    except Exception as e:
        console.print(f"[red]✗[/red] HackerNews collection failed: {e}")
        return []

    console.print(f"[green]✓[/green] Collected {len(items)} stories from HackerNews")
    return items
