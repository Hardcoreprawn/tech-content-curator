"""Reddit collector for TIER_2 content.

Reddit provides high-quality, community-curated tech content from focused
subreddits. We collect from programming, ML, devops, and other tech communities.

Collection strategy:
- Focus on tech-focused subreddits (programming, MachineLearning, etc.)
- Get "hot" posts (similar to trending content)
- Filter for engagement (comments, upvotes)
- Skip stickied posts and low-effort content
- Apply political and entitled content filters

Quality filters:
- Self posts: Must have substantial content (50+ chars)
- Link posts: Must have active discussion (10+ comments)
- Skip political rants and entitled whining
- Respect Reddit API rate limits
"""

import time
from datetime import UTC, datetime

import praw
from pydantic import HttpUrl
from rich.console import Console

from ..models import CollectedItem, PipelineConfig, SourceType
from ..utils.logging import get_logger
from .base import (
    is_entitled_whining,
    is_political_content,
)

logger = get_logger(__name__)
console = Console()


def collect_from_reddit(config: PipelineConfig, limit: int = 20) -> list[CollectedItem]:
    """Collect hot posts from tech-focused subreddits.

    Args:
        config: Pipeline configuration with Reddit credentials
        limit: Maximum number of posts to collect

    Returns:
        List of collected items from Reddit
    """
    if not all(
        [config.reddit_client_id, config.reddit_client_secret, config.reddit_user_agent]
    ):
        logger.debug("Reddit credentials not configured, skipping Reddit collection")
        console.print(
            "[yellow]⚠ Reddit credentials not configured, skipping Reddit collection[/yellow]"
        )
        return []

    logger.debug(f"Starting Reddit collection (limit={limit})")
    console.print("[blue]Collecting from Reddit...[/blue]")

    # Tech-focused subreddits for high-quality content
    tech_subreddits = [
        "programming",
        "MachineLearning",
        "devops",
        "sysadmin",
        "webdev",
        "Python",
        "javascript",
        "rust",
        "golang",
        "cpp",
        "softwarearchitecture",
        "technology",
        "coding",
        "compsci",
        "opensource",
    ]

    try:
        # Initialize Reddit API client (read-only)
        reddit = praw.Reddit(
            client_id=config.reddit_client_id,
            client_secret=config.reddit_client_secret,
            user_agent=config.reddit_user_agent,
            check_for_async=False,
        )

        all_posts = []
        posts_per_subreddit = max(
            2, limit // len(tech_subreddits)
        )  # At least 2 per subreddit

        for subreddit_name in tech_subreddits[
            :8
        ]:  # Limit to 8 subreddits to avoid rate limits
            try:
                logger.debug(f"Collecting from r/{subreddit_name}")
                console.print(f"[dim]  Checking r/{subreddit_name}...[/dim]")
                subreddit = reddit.subreddit(subreddit_name)

                # Get hot posts (similar to trending on Mastodon)
                for post in subreddit.hot(limit=posts_per_subreddit):
                    # Skip stickied posts
                    if post.stickied:
                        continue

                    # For self posts, check if they have enough content
                    # For link posts, include if they have good discussion
                    if post.is_self and len(post.selftext.strip()) < 50:
                        continue
                    elif not post.is_self and post.num_comments < 10:
                        continue  # Link posts need discussion to be valuable

                    all_posts.append(post)

                    if len(all_posts) >= limit:
                        break

                # Rate limiting - be respectful to Reddit API
                from ..config import get_config

                config = get_config()
                time.sleep(config.sleep_intervals.between_subreddit_requests)

                if len(all_posts) >= limit:
                    break

            except Exception as e:
                logger.warning(
                    f"Error collecting from r/{subreddit_name}: {type(e).__name__}"
                )
                console.print(
                    f"[yellow]⚠ Failed to collect from r/{subreddit_name}: {e}[/yellow]"
                )
                continue

        # Process Reddit posts into CollectedItems
        return _process_reddit_posts(all_posts, config)

    except Exception as e:
        logger.error(f"Reddit collection failed: {type(e).__name__} - {e}")
        console.print(f"[red]✗ Reddit collection failed: {e}[/red]")
        return []


def _process_reddit_posts(posts: list, config: PipelineConfig) -> list[CollectedItem]:
    """Process raw Reddit posts into CollectedItem objects with filtering.

    Args:
        posts: Raw posts from Reddit API
        config: Pipeline configuration

    Returns:
        List of filtered and processed CollectedItem objects
    """
    console.print(f"[blue]Processing {len(posts)} Reddit posts...[/blue]")

    # Tracking counters
    items = []
    filtered_counts = {
        "malformed": 0,
        "too_short": 0,
        "too_long": 0,
        "no_content": 0,
        "political": 0,
        "entitled": 0,
        "processed": 0,
    }
    logger.debug(f"Starting to process {len(posts)} Reddit posts")

    for post in posts:
        try:
            # Use selftext for text posts, title + selftext for discussion
            content = post.title
            if post.selftext.strip():
                content += "\n\n" + post.selftext.strip()

            # Skip posts that are too long or too short
            if len(content) > config.max_content_length:
                filtered_counts["too_long"] += 1
                continue

            if len(content) < config.min_content_length:
                # For Reddit, be more lenient on short posts if they have good engagement
                if post.score < 20 or post.num_comments < 5:
                    filtered_counts["too_short"] += 1
                    continue

            # Skip posts without meaningful content
            if not content.strip():
                filtered_counts["no_content"] += 1
                continue

            # Apply same political filtering as Mastodon
            if is_political_content(content):
                filtered_counts["political"] += 1
                console.print(f"[dim]Filtered political: {content[:50]}...[/dim]")
                continue

            # Apply entitled content filtering
            if is_entitled_whining(content):
                filtered_counts["entitled"] += 1
                console.print(f"[dim]Filtered entitled: {content[:50]}...[/dim]")
                continue

            item = CollectedItem(
                id=f"reddit_{post.id}",
                title=post.title,
                content=content,
                source=SourceType.REDDIT,
                url=HttpUrl(f"https://reddit.com{post.permalink}"),
                author=str(post.author) if post.author else "deleted",
                collected_at=datetime.now(UTC),
                metadata={
                    "score": post.score,
                    "upvote_ratio": post.upvote_ratio,
                    "num_comments": post.num_comments,
                    "subreddit": post.subreddit.display_name,
                    "created_utc": post.created_utc,
                    "is_self": post.is_self,
                    "over_18": post.over_18,
                    "source_name": "reddit_programming",
                },
            )
            items.append(item)
            filtered_counts["processed"] += 1

        except Exception as e:
            filtered_counts["malformed"] += 1
            logger.debug(f"Malformed Reddit post: {type(e).__name__}")
            console.print(f"[yellow]⚠[/yellow] Malformed Reddit post: {e}")
            continue

    # Print detailed filtering summary
    total_raw = len(posts)
    total_filtered = sum(
        filtered_counts[key] for key in filtered_counts if key != "processed"
    )

    console.print("\n[bold]Reddit Collection Summary:[/bold]")
    console.print(f"  Raw posts retrieved: {total_raw}")
    console.print(f"  Successfully processed: {filtered_counts['processed']}")
    console.print(f"  Total filtered out: {total_filtered}")

    if total_filtered > 0:
        console.print("[dim]  Filter breakdown:[/dim]")
        for reason, count in filtered_counts.items():
            if reason != "processed" and count > 0:
                reason_name = reason.replace("_", " ").title()
                console.print(f"[dim]    {reason_name}: {count}[/dim]")

    console.print(f"[green]✓[/green] Final result: {len(items)} items from Reddit")
    logger.info(
        f"Processed Reddit collection: {len(items)} items kept, {total_filtered} filtered"
    )
    return items
