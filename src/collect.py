"""Content collection from social media sources.

This module handles fetching content from various social media platforms.
We start with Mastodon because:
1. Simple REST API
2. Often allows public timeline access without auth
3. Good for tech content (lots of developers use it)

DESIGN DECISIONS:
- Each source gets its own function (collect_from_mastodon, collect_from_bluesky, etc.)
- Functions return List[CollectedItem] - consistent interface
- Error handling is explicit - we want to know when things fail
- Rate limiting is handled per-source since each API is different
- Async collection for parallel fetching from multiple sources
"""

import asyncio
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urljoin

import httpx
import praw
from pydantic import HttpUrl
from rich.console import Console

from .config import get_config, get_data_dir
from .utils.url_tools import normalize_url
from .models import CollectedItem, PipelineConfig, SourceType

console = Console()


def collect_from_mastodon_trending(
    config: PipelineConfig, limit: int = 30
) -> list[CollectedItem]:
    """Collect trending posts from Mastodon for better content quality.

    Trending content is more likely to be:
    - High quality and engaging
    - Already filtered by community engagement
    - More relevant and interesting

    Args:
        config: Pipeline configuration
        limit: Maximum number of posts to collect

    Returns:
        List of collected items from Mastodon trending
    """
    instance = config.mastodon_instances[0]  # Use first instance from list
    console.print(
        f"[blue]Collecting trending content from Mastodon ({instance})...[/blue]"
    )

    # Try trending statuses first (better quality content)
    trending_url = urljoin(instance, "/api/v1/trends/statuses")

    try:
        with httpx.Client(timeout=30.0) as client:
            # Get trending posts
            trending_response = client.get(
                trending_url, params={"limit": min(limit, 20)}
            )

            if trending_response.status_code == 200:
                trending_posts = trending_response.json()
                console.print(
                    f"[green]✓[/green] Found {len(trending_posts)} trending posts"
                )

                if trending_posts:
                    return _process_mastodon_posts(
                        trending_posts, config, "trending", instance
                    )

            # Fallback to public timeline if trending fails
            console.print(
                "[yellow]Trending not available, falling back to public timeline[/yellow]"
            )

    except Exception as e:
        console.print(
            f"[yellow]Trending collection failed: {e}, using public timeline[/yellow]"
        )

    # Fallback to public timeline
    return collect_from_mastodon_public(config, limit)


def collect_from_mastodon(
    config: PipelineConfig, limit: int = 20
) -> list[CollectedItem]:
    """Backward-compatible shim for older callers.

    Uses trending first with a fallback to public timeline.
    """
    try:
        return collect_from_mastodon_trending(config, limit)
    except Exception:
        return collect_from_mastodon_public(config, limit)


def collect_from_mastodon_public(
    config: PipelineConfig, limit: int = 20
) -> list[CollectedItem]:
    """Collect from public timeline as fallback.

    Args:
        config: Pipeline configuration
        limit: Maximum number of posts to collect

    Returns:
        List of collected items from Mastodon public timeline
    """
    instance = config.mastodon_instances[0]  # Use first instance from list
    console.print(f"[blue]Collecting from public timeline ({instance})...[/blue]")

    # Mastodon API endpoint for public timeline
    url = urljoin(instance, "/api/v1/timelines/public")

    # Parameters: only get posts (not boosts), limit results
    params = {
        "only_media": "false",
        "local": "false",  # Include federated content
        "limit": min(limit, 40),  # Mastodon's max is 40
    }

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.get(url, params=params)
            response.raise_for_status()

        posts = response.json()
        console.print(
            f"[green]✓[/green] Retrieved {len(posts)} posts from public timeline"
        )

        return _process_mastodon_posts(posts, config, "public", instance)

    except httpx.HTTPError as e:
        console.print(f"[red]✗[/red] Failed to collect from Mastodon: {e}")
        raise


def _process_mastodon_posts(
    posts: list, config: PipelineConfig, source_type: str, instance: str
) -> list[CollectedItem]:
    """Process raw Mastodon posts into CollectedItem objects with filtering.

    Args:
        posts: Raw posts from Mastodon API
        config: Pipeline configuration
        source_type: "trending" or "public" for logging
        instance: The Mastodon instance URL

    Returns:
        List of filtered and processed CollectedItem objects
    """
    console.print(f"[blue]Processing {len(posts)} raw posts...[/blue]")

    # Tracking counters
    items = []
    filtered_counts = {
        "malformed": 0,
        "too_short": 0,
        "too_long": 0,
        "no_content": 0,
        "political": 0,
        "entitled": 0,
        "non_english": 0,
        "off_topic": 0,
        "processed": 0,
    }

    for post in posts:
        try:
            # Extract text content, handling HTML
            content = _clean_html_content(post.get("content", ""))

            # Skip posts that are too long (but be more lenient on short posts)
            if len(content) > config.max_content_length:
                filtered_counts["too_long"] += 1
                continue

            # For very short posts, only keep if they have strong indicators
            if len(content) < 50:
                filtered_counts["too_short"] += 1
                continue
            elif len(content) < config.min_content_length:
                # Check if short post has redeeming qualities
                has_tech_keywords = any(
                    keyword in content.lower()
                    for keyword in [
                        "python",
                        "javascript",
                        "rust",
                        "go",
                        "docker",
                        "kubernetes",
                        "aws",
                        "azure",
                        "api",
                        "github",
                        "open source",
                        "algorithm",
                        "ml",
                        "ai",
                        "devops",
                        "cloud",
                    ]
                )
                has_engagement = (
                    post.get("favourites_count", 0) + post.get("reblogs_count", 0)
                ) > 5
                has_links = "http" in content

                if not (has_tech_keywords or has_engagement or has_links):
                    filtered_counts["too_short"] += 1
                    continue

            # Skip posts without meaningful content
            if not content.strip() or content.strip().startswith("@"):
                filtered_counts["no_content"] += 1
                continue

            # Filter out political content (basic keyword filtering)
            if _is_political_content(content):
                filtered_counts["political"] += 1
                console.print(f"[dim]Filtered political: {content[:50]}...[/dim]")
                continue

            # Filter out entitled whining disguised as insights
            if _is_entitled_whining(content):
                filtered_counts["entitled"] += 1
                console.print(f"[dim]Filtered entitled: {content[:50]}...[/dim]")
                continue

            # Check if content is in English or should be translated
            language = post.get("language", "en")
            if language != "en" and len(content) > 50:
                filtered_counts["non_english"] += 1
                console.print(
                    f"[dim]Filtered non-English ({language}): {content[:50]}...[/dim]"
                )
                continue

            # NEW: Filter for topic relevance (tech/science/policy)
            # Extract title for better relevance checking
            title = _extract_title_from_content(content)
            if not _is_relevant_content(content, title, config):
                filtered_counts["off_topic"] += 1
                console.print(f"[dim]Filtered off-topic: {content[:50]}...[/dim]")
                continue

            item = CollectedItem(
                id=f"mastodon_{post['id']}",
                title=title,
                content=content,
                source=SourceType.MASTODON,
                url=post["url"],
                author=post["account"]["username"],
                collected_at=datetime.now(UTC),
                metadata={
                    "favourites_count": post.get("favourites_count", 0),
                    "reblogs_count": post.get("reblogs_count", 0),
                    "replies_count": post.get("replies_count", 0),
                    "created_at": post.get("created_at"),
                    "language": language,
                    "instance": instance,
                    "source_type": source_type,
                    "source_name": "mastodon_trending",
                },
            )
            items.append(item)
            filtered_counts["processed"] += 1

        except (KeyError, ValueError) as e:
            filtered_counts["malformed"] += 1
            console.print(f"[yellow]⚠[/yellow] Malformed post: {e}")
            continue

    # Print detailed filtering summary
    total_raw = len(posts)
    total_filtered = sum(
        filtered_counts[key] for key in filtered_counts if key != "processed"
    )

    console.print("\n[bold]Collection Summary:[/bold]")
    console.print(f"  Raw posts retrieved: {total_raw}")
    console.print(f"  Successfully processed: {filtered_counts['processed']}")
    console.print(f"  Total filtered out: {total_filtered}")

    if total_filtered > 0:
        console.print("[dim]  Filter breakdown:[/dim]")
        for reason, count in filtered_counts.items():
            if reason != "processed" and count > 0:
                console.print(
                    f"[dim]    {reason.replace('_', ' ').title()}: {count}[/dim]"
                )

    console.print(
        f"[green]✓[/green] Final result: {len(items)} items from Mastodon {source_type}"
    )
    return items


def _is_entitled_whining(content: str) -> bool:
    """Check if content is entitled complaining masquerading as insights.

    Filters out first-world problems, privileged complaints, and non-actionable
    whining that assumes everyone has the same lifestyle/resources.

    Args:
        content: The post content to check

    Returns:
        True if content appears to be entitled whining, False otherwise
    """
    content_lower = content.lower()

    # Only catch the most egregious entitled content
    # Look for complaint + privilege + universality assumptions

    # Privilege indicators (only filter if combined with complaints)
    privilege_indicators = [
        "first class",
        "business class",
        "premium subscription",
        "luxury",
        "my expensive",
        "high-end",
        "enterprise plan",
        "traveling weekly",
    ]

    # Complaint tone (strong negative emotions)
    complaint_tone = [
        "ridiculous that",
        "stupid that",
        "hate that",
        "annoying that",
        "frustrating that",
        "unacceptable",
        "outrageous",
    ]

    # Universal assumptions (claiming to speak for everyone)
    universal_claims = [
        "everyone needs",
        "people want",
        "we all",
        "most important",
        "should be standard",
        "essential for everyone",
    ]

    # Only filter if it hits multiple categories
    has_privilege = any(
        indicator in content_lower for indicator in privilege_indicators
    )
    has_complaint = any(tone in content_lower for tone in complaint_tone)
    has_assumption = any(claim in content_lower for claim in universal_claims)

    # Filter only if it's complaint + privilege + assumption (the trifecta of entitlement)
    if has_complaint and has_privilege and has_assumption:
        return True

    # Or if it's just extremely whiny regardless of topic
    whiny_count = sum(
        1
        for word in ["ridiculous", "stupid", "hate", "annoying", "frustrating"]
        if word in content_lower
    )
    if whiny_count >= 2:  # Multiple whiny words = filter
        return True

    return False


def _is_political_content(content: str) -> bool:
    """Check if content appears to be geopolitical/state-level political content.

    Focuses on avoiding content that condemns countries, governments, or
    involves international conflicts. Less concerned with party politics.

    Args:
        content: The post content to check

    Returns:
        True if content appears to be geopolitical/inflammatory, False otherwise
    """
    content_lower = content.lower()
    import re

    # High-confidence geopolitical/conflict keywords - always filter
    conflict_keywords = [
        "ukraine",
        "russia",
        "putin",
        "israel",
        "palestine",
        "gaza",
        "invasion",
        "bombing",
        "sanctions",
        "dictatorship",
        "regime",
        "nazi",
        "terrorism",
        "extremist",
    ]

    for keyword in conflict_keywords:
        pattern = r"\b" + re.escape(keyword) + r"\b"
        if re.search(pattern, content_lower):
            return True

    # Medium-confidence keywords - only filter if combined with negative sentiment
    sensitive_keywords = ["war", "military", "government", "immigration", "border"]
    negative_sentiment = [
        "crackdown",
        "oppression",
        "violation",
        "corrupt",
        "failed",
        "terrible",
        "awful",
        "disaster",
        "crisis",
        "condemn",
    ]

    has_sensitive = any(
        re.search(r"\b" + re.escape(k) + r"\b", content_lower)
        for k in sensitive_keywords
    )
    has_negative = any(
        re.search(r"\b" + re.escape(n) + r"\b", content_lower)
        for n in negative_sentiment
    )

    if has_sensitive and has_negative:
        return True

    # Filter protest/unrest content that tends to be inflammatory
    unrest_keywords = ["protest", "riot", "uprising", "revolution", "rally"]
    for keyword in unrest_keywords:
        pattern = r"\b" + re.escape(keyword) + r"\b"
        if re.search(pattern, content_lower):
            return True

    # Check for excessive use of political symbols/emojis
    political_symbols = ["🤮", "💩", "🤬", "😡", "🔥", "💯"]
    symbol_count = sum(content.count(symbol) for symbol in political_symbols)
    if symbol_count > 2:  # More than 2 political symbols suggests political content
        return True

    return False


def _is_relevant_content(content: str, title: str, config: PipelineConfig) -> bool:
    """Check if content is relevant to our target topics (tech, science, policy).
    
    Configurable via environment variables to tune filtering.
    
    Args:
        content: The post content to check
        title: The post title/first line
        config: Pipeline configuration with relevance settings
        
    Returns:
        True if content appears relevant, False otherwise
    """
    content_lower = content.lower()
    title_lower = title.lower()
    combined = content_lower + " " + title_lower
    
    # Parse negative keywords from config
    negative_keywords = [
        kw.strip()
        for kw in config.relevance_negative_keywords.split(",")
        if kw.strip()
    ]
    
    # Check for negative keywords first (quick rejection)
    for keyword in negative_keywords:
        if keyword in combined:
            return False
    
    # Check for technical domain links (github, arxiv, technical blogs)
    tech_domains = [
        "github.com",
        "gitlab.com",
        "arxiv.org",
        "stackoverflow.com",
        "dev.to",
        "medium.com",
        "hackernews",
        "lobste.rs",
    ]
    has_tech_link = any(domain in content_lower for domain in tech_domains)
    if has_tech_link:
        return True
    
    # TECH KEYWORDS (primary focus)
    tech_keywords = [
        # Programming languages
        "python",
        "javascript",
        "typescript",
        "rust",
        "go",
        "java",
        "c++",
        "ruby",
        "php",
        "swift",
        "kotlin",
        "scala",
        # Technologies & platforms
        "docker",
        "kubernetes",
        "aws",
        "azure",
        "gcp",
        "linux",
        "unix",
        "api",
        "github",
        "gitlab",
        "git",
        "database",
        "sql",
        "nosql",
        # Concepts & practices
        "algorithm",
        "ml",
        "ai",
        "llm",
        "machine learning",
        "deep learning",
        "devops",
        "cloud",
        "serverless",
        "microservices",
        "backend",
        "frontend",
        "open source",
        "opensource",
        "software",
        "programming",
        "coding",
        "developer",
        "security",
        "encryption",
        "privacy",
        "vulnerability",
        "exploit",
        # Tools & frameworks
        "react",
        "vue",
        "angular",
        "django",
        "flask",
        "rails",
        "node",
        "tensorflow",
        "pytorch",
        "jupyter",
        "vscode",
        "vim",
        "emacs",
        # Tech companies & projects (when discussing tech aspects)
        "openai",
        "anthropic",
        "meta ai",
        "google ai",
        "microsoft",
        "apple",
        # Tech topics
        "app",
        "webapp",
        "mobile",
        "ios",
        "android",
        "web development",
        "data science",
        "analytics",
        "visualization",
        "server",
        "infrastructure",
        "cli",
        "terminal",
        "shell",
        "bash",
        "deployment",
        "ci/cd",
        "performance",
        "optimization",
        "testing",
        "debugging",
    ]
    
    # SCIENCE KEYWORDS (future expansion)
    science_keywords = [
        "research",
        "study",
        "paper",
        "journal",
        "peer review",
        "experiment",
        "hypothesis",
        "data analysis",
        "methodology",
        "physics",
        "chemistry",
        "biology",
        "astronomy",
        "neuroscience",
        "climate",
        "environment",
        "sustainability",
    ]
    
    # POLICY KEYWORDS (future expansion - tech policy specifically)
    policy_keywords = [
        "regulation",
        "privacy law",
        "gdpr",
        "antitrust",
        "net neutrality",
        "copyright",
        "patent",
        "open access",
        "digital rights",
        "data protection",
        "tech policy",
    ]
    
    # Check for positive keywords based on config toggles
    has_tech = config.allow_tech_content and any(
        keyword in combined for keyword in tech_keywords
    )
    has_science = config.allow_science_content and any(
        keyword in combined for keyword in science_keywords
    )
    has_policy = config.allow_policy_content and any(
        keyword in combined for keyword in policy_keywords
    )
    
    return has_tech or has_science or has_policy


def _clean_html_content(html_content: str) -> str:
    """Remove HTML tags from Mastodon content.

    Mastodon posts come as HTML. We need plain text for processing.
    This is a simple approach - for production you might use BeautifulSoup.
    """
    import re

    # Remove HTML tags
    text = re.sub(r"<[^>]+>", "", html_content)

    # Decode HTML entities
    import html

    text = html.unescape(text)

    # Clean up whitespace
    text = " ".join(text.split())

    return text.strip()


def _extract_title_from_content(content: str, max_length: int = 80) -> str:
    """Extract a title from post content.

    Social media posts don't have titles, so we create one from the first line.
    """
    # Get first sentence or first line
    first_line = content.split("\n")[0].strip()
    first_sentence = first_line.split(".")[0].strip()

    # Use the shorter of first line or first sentence
    title = first_sentence if len(first_sentence) < len(first_line) else first_line

    # Truncate if too long
    if len(title) > max_length:
        title = title[: max_length - 3] + "..."

    return title or "Untitled Post"


def save_collected_items(
    items: list[CollectedItem], timestamp: str | None = None
) -> Path:
    """Save collected items to JSON file.

    Why JSON files instead of a database:
    - Simple to debug (you can open the file and see what's in it)
    - No setup required
    - Easy to process with other tools
    - Good enough for this scale

    Args:
        items: List of collected items to save
        timestamp: Optional timestamp for filename, defaults to now

    Returns:
        Path to the saved file
    """
    if not timestamp:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    filename = f"collected_{timestamp}.json"
    filepath = get_data_dir() / filename

    # Convert Pydantic models to dict for JSON serialization
    data = {
        "collected_at": datetime.now(UTC).isoformat(),
        "total_items": len(items),
        "items": [item.model_dump() for item in items],
    }

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)

    console.print(f"[green]✓[/green] Saved {len(items)} items to {filename}")
    return filepath


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
        console.print(
            "[yellow]⚠ Reddit credentials not configured, skipping Reddit collection[/yellow]"
        )
        return []

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
                time.sleep(0.5)  # 500ms between subreddit requests

                if len(all_posts) >= limit:
                    break

            except Exception as e:
                console.print(
                    f"[yellow]⚠ Failed to collect from r/{subreddit_name}: {e}[/yellow]"
                )
                continue

        # Process Reddit posts into CollectedItems
        return _process_reddit_posts(all_posts, config)

    except Exception as e:
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
            if _is_political_content(content):
                filtered_counts["political"] += 1
                console.print(f"[dim]Filtered political: {content[:50]}...[/dim]")
                continue

            # Apply entitled content filtering
            if _is_entitled_whining(content):
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
    return items


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


def collect_from_github_trending(
    language: str | None = None, limit: int = 20
) -> list[CollectedItem]:
    """Collect trending repositories from GitHub.

    GitHub trending is S-tier: shows what's hot in open source.

    Args:
        language: Filter by programming language (None = all languages)
        limit: Maximum number of repos to collect

    Returns:
        List of collected items from GitHub Trending
    """
    console.print(
        f"[blue]Collecting from GitHub Trending{f' ({language})' if language else ''}...[/blue]"
    )

    items = []

    try:
        # GitHub trending doesn't have an official API, but we can scrape it
        # For now, use GitHub's search API with recent stars as proxy
        with httpx.Client(timeout=30.0) as client:
            # Search for recently starred repos
            params = {
                "q": "stars:>100 pushed:>2025-10-01",  # Active repos with good engagement
                "sort": "stars",
                "order": "desc",
                "per_page": limit,
            }

            if language:
                params["q"] += f" language:{language}"

            response = client.get(
                "https://api.github.com/search/repositories",
                params=params,
                headers={"Accept": "application/vnd.github.v3+json"},
            )

            if response.status_code == 403:
                console.print("[yellow]⚠[/yellow] GitHub API rate limit hit, skipping")
                return []

            response.raise_for_status()
            data = response.json()

            repos = data.get("items", [])[:limit]
            console.print(f"  Found {len(repos)} trending repositories...")

            for repo in repos:
                try:
                    # Build content from repo description and README preview
                    content = (
                        f"{repo['name']}\n\n{repo.get('description', 'No description')}"
                    )

                    item = CollectedItem(
                        id=f"github_{repo['id']}",
                        title=f"{repo['full_name']}: {repo.get('description', '')[:100]}",
                        content=content,
                        source=SourceType.GITHUB,
                        url=repo["html_url"],
                        author=repo["owner"]["login"],
                        collected_at=datetime.now(UTC),
                        metadata={
                            "stars": repo["stargazers_count"],
                            "forks": repo["forks_count"],
                            "watchers": repo["watchers_count"],
                            "language": repo.get("language"),
                            "topics": repo.get("topics", []),
                            "source_name": "github_trending",
                            "open_issues": repo.get("open_issues_count", 0),
                        },
                    )
                    items.append(item)

                except Exception as e:
                    console.print(
                        f"[yellow]⚠[/yellow] Failed to process GitHub repo: {e}"
                    )
                    continue

    except Exception as e:
        console.print(f"[red]✗[/red] GitHub trending collection failed: {e}")
        return []

    console.print(f"[green]✓[/green] Collected {len(items)} trending repos from GitHub")
    return items


def _deduplicate_items(items: list[CollectedItem]) -> list[CollectedItem]:
    """Remove duplicate content using semantic deduplication with learning.

    Uses adaptive semantic analysis to detect duplicates across instances.
    Learns patterns from duplicates to improve future detection.
    Keeps the item with the highest engagement when duplicates are found.

    Args:
        items: List of collected items to deduplicate

    Returns:
        List of unique items
    """
    if not items:
        return items

    console.print(f"[yellow]Deduplicating {len(items)} items...[/yellow]")

    # First pass: Remove exact URL duplicates (same post on multiple instances)
    url_groups: dict[str, list[CollectedItem]] = {}
    for item in items:
        # Normalize URL to collapse trivial differences (case, default ports, trackers)
        url = normalize_url(str(item.url))
        if url not in url_groups:
            url_groups[url] = []
        url_groups[url].append(item)

    # Keep highest engagement item from each URL group
    url_deduped = []

    def get_engagement(item: CollectedItem) -> int:
        """Calculate engagement score for an item."""
        if not item.metadata:
            return 0
        return (
            item.metadata.get("favourites_count", 0)  # Mastodon
            + item.metadata.get("score", 0)  # Reddit/HN
            + item.metadata.get("reblogs_count", 0) * 2
            + item.metadata.get("replies_count", 0) * 3
            + item.metadata.get("comments", 0) * 3
        )  # HN

    url_dups_removed = 0
    for _url, group in url_groups.items():
        best_item = max(group, key=get_engagement)
        url_deduped.append(best_item)
        if len(group) > 1:
            url_dups_removed += len(group) - 1

    if url_dups_removed > 0:
        console.print(f"[dim]Removed {url_dups_removed} exact URL duplicates[/dim]")

    # Second pass: Semantic deduplication for similar but not identical content
    console.print(
        f"[yellow]Running semantic deduplication on {len(url_deduped)} items...[/yellow]"
    )

    # Use the semantic deduplicator with feedback
    from .dedup_feedback import DeduplicationFeedbackSystem
    from .semantic_dedup import SemanticDeduplicator

    deduplicator = SemanticDeduplicator()
    feedback_system = DeduplicationFeedbackSystem()

    # Type ignore needed because semantic dedup uses generic Protocol
    duplicate_groups = deduplicator.find_duplicates(url_deduped, threshold=0.6)  # type: ignore

    # Create set of items that are duplicates
    duplicate_items = set()
    unique_items = []

    for group in duplicate_groups:
        # Sort by engagement metrics - cast to CollectedItem for type checker
        best_item = max(group, key=lambda x: get_engagement(x))  # type: ignore
        unique_items.append(best_item)

        # Mark others as duplicates
        for item in group:
            if item != best_item:
                duplicate_items.add(id(item))

        console.print(
            f"[dim]Removed {len(group) - 1} semantic duplicates of: {best_item.content[:50]}...[/dim]"
        )

    # Add non-duplicate items from the URL-deduplicated set
    for item in url_deduped:
        if id(item) not in duplicate_items:
            # Check if this item is already in unique_items (from duplicate groups)
            if not any(id(unique_item) == id(item) for unique_item in unique_items):
                unique_items.append(item)

    semantic_dedupe_count = len(url_deduped) - len(unique_items)
    if semantic_dedupe_count > 0:
        console.print(
            f"[blue]Removed {semantic_dedupe_count} semantic duplicates using learned patterns[/blue]"
        )

        # Record feedback for learning
        feedback_system.record_deduplication_session(
            url_deduped, unique_items, deduplicator
        )

        # Show pattern stats
        stats = deduplicator.get_pattern_stats()
        if stats.get("total_patterns", 0) > 0:
            console.print(
                f"[dim]Using {stats['total_patterns']} learned patterns with {stats.get('avg_confidence', 0):.2f} avg confidence[/dim]"
            )

        # Show improvement suggestions periodically
        if len(feedback_system.feedback_history) % 5 == 0:  # Every 5 sessions
            suggestions = feedback_system.suggest_improvements()
            if (
                suggestions
                and suggestions[0] != "Deduplication performance looks good!"
            ):
                console.print(f"[yellow]💡 Suggestion: {suggestions[0]}[/yellow]")

    return unique_items


def collect_all_sources() -> list[CollectedItem]:
    """Collect content from all configured sources.

    This is the main entry point for content collection.
    It tries each source and combines results, with deduplication.
    """
    config = get_config()
    all_items = []

    console.print("[bold blue]Starting content collection...[/bold blue]")

    # Collect from multiple Mastodon instances
    for instance in config.mastodon_instances:
        console.print(f"\n[blue]Trying instance: {instance}[/blue]")
        try:
            # Create a temporary config for this instance
            instance_config = PipelineConfig(
                openai_api_key=config.openai_api_key,
                mastodon_instances=[instance],
                articles_per_run=config.articles_per_run,
                min_content_length=config.min_content_length,
                max_content_length=config.max_content_length,
            )
            mastodon_items = collect_from_mastodon_trending(instance_config)
            all_items.extend(mastodon_items)

            # Limit total items to avoid overwhelming processing
            if len(all_items) >= 80:  # Increased limit for more filtering options
                console.print(
                    "[yellow]Reached item limit, stopping collection[/yellow]"
                )
                break

        except Exception as e:
            console.print(f"[yellow]⚠[/yellow] Instance {instance} failed: {e}")

    # Reddit collection temporarily disabled (blocked, testing rate limiting)
    # TODO: Re-enable once block is lifted to test new rate limiter
    # try:
    #     reddit_limit = min(20, 80 - len(all_items))  # Don't exceed total limit
    #     if reddit_limit > 0:
    #         reddit_items = collect_from_reddit(config, reddit_limit)
    #         all_items.extend(reddit_items)
    # except Exception as e:
    #     console.print(f"[yellow]⚠[/yellow] Reddit collection failed: {e}")

    # Collect from HackerNews, GitHub trending concurrently
    console.print("[blue]Collecting from HackerNews and GitHub in parallel...[/blue]")
    
    async def collect_parallel_sources():
        """Collect from multiple sources concurrently."""
        tasks = []
        
        # HackerNews
        hn_limit = min(20, 100 - len(all_items))
        if hn_limit > 0:
            async def collect_hn():
                try:
                    return await asyncio.to_thread(collect_from_hackernews, hn_limit)
                except Exception as e:
                    console.print(f"[yellow]⚠[/yellow] HackerNews collection failed: {e}")
                    return []
            tasks.append(collect_hn())
        
        # GitHub trending
        gh_limit = min(15, 100 - len(all_items))
        if gh_limit > 0:
            async def collect_gh():
                try:
                    return await asyncio.to_thread(collect_from_github_trending, None, gh_limit)
                except Exception as e:
                    console.print(f"[yellow]⚠[/yellow] GitHub trending collection failed: {e}")
                    return []
            tasks.append(collect_gh())
        
        # Run all tasks concurrently
        results = await asyncio.gather(*tasks)
        return [item for result in results for item in result]
    
    # Run async collection
    try:
        parallel_items = asyncio.run(collect_parallel_sources())
        all_items.extend(parallel_items)
    except Exception as e:
        console.print(f"[yellow]⚠[/yellow] Parallel collection failed: {e}")

    # TODO: Add dev.to, Lobsters, and potentially Twitter/X

    console.print(
        f"[bold green]✓ Collection complete: {len(all_items)} total items[/bold green]"
    )

    # Deduplicate content across instances
    if all_items:
        all_items = _deduplicate_items(all_items)
        console.print(
            f"[bold green]✓ After deduplication: {len(all_items)} unique items[/bold green]"
        )

        # Apply tier-based filtering
        from .source_tiers import SOURCE_CONFIGS, SourceTier

        console.print("\n[blue]Applying tier-based filtering...[/blue]")

        # Group items by source and apply tier-specific minimum scores
        filtered_items = []
        source_stats = {}

        for item in all_items:
            source_name = (
                item.metadata.get("source_name", "unknown")
                if item.metadata
                else "unknown"
            )

            # Map source names to tier configs
            source_key = None
            if "hackernews" in source_name.lower():
                source_key = "hackernews_top"
            elif "github" in source_name.lower():
                source_key = "github_trending"
            elif "reddit" in source_name.lower():
                source_key = "reddit_programming"  # Default to B-tier
            elif "mastodon" in source_name.lower():
                source_key = "mastodon_trending"

            # Get minimum score threshold for this source's tier
            if source_key and source_key in SOURCE_CONFIGS:
                config = SOURCE_CONFIGS[source_key]
                tier = config.tier
            else:
                # Unknown source - use B-tier defaults
                tier = SourceTier.B_TIER

            # Track stats
            if source_name not in source_stats:
                source_stats[source_name] = {"total": 0, "kept": 0, "tier": tier.value}
            source_stats[source_name]["total"] += 1

            # Note: At this point items don't have quality scores yet
            # Score filtering happens later in the pipeline after enrichment
            # Here we just prepare items for enrichment
            filtered_items.append(item)
            source_stats[source_name]["kept"] += 1

        # Display stats
        for source, stats in source_stats.items():
            console.print(
                f"[dim]  {source}: {stats['kept']}/{stats['total']} items ({stats['tier']}-tier)[/dim]"
            )

        all_items = filtered_items
        console.print(
            f"[bold green]✓ Final result: {len(all_items)} items prepared for enrichment[/bold green]"
        )

    # Save to file
    if all_items:
        save_collected_items(all_items)

    return all_items


if __name__ == "__main__":
    """Run collection if this file is executed directly."""
    items = collect_all_sources()
    console.print(f"Collected {len(items)} items total")
