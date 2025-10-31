"""Content collectors package.

This package provides collectors for various social media and content platforms.
Each collector implements a consistent interface for fetching and normalizing
content into CollectedItem objects.

Available Collectors:
- Mastodon: Trending posts from Mastodon instances
- Bluesky: Posts from Bluesky social network
- Reddit: Top posts from technology subreddits
- Hacker News: Top and trending stories

Usage:
    from src.collectors import collect_from_mastodon, collect_from_bluesky
    
    config = get_config()
    mastodon_items = collect_from_mastodon(config)
    bluesky_items = collect_from_bluesky(config)

Design Principles:
- Consistent interface: All collectors return List[CollectedItem]
- Source-specific error handling
- Rate limiting per source
- Async collection for parallel fetching
- Configurable limits and filters

Adding a New Collector:
1. Create a new module (e.g., twitter.py)
2. Implement collect_from_<source>() function
3. Return List[CollectedItem] with normalized data
4. Add proper error handling and rate limiting
5. Export from this __init__.py
"""

"""Content collectors package.

This package provides collectors for various social media and content platforms.
Each collector implements a consistent interface for fetching and normalizing
content into CollectedItem objects.

Available Collectors:
- Mastodon: Trending posts from Mastodon instances (TIER_1)
- Reddit: Hot posts from tech subreddits (TIER_2)
- HackerNews: Top stories (TIER_3)
- GitHub: Trending repositories (TIER_3)

Usage:
    from src.collectors import collect_all_sources, save_collected_items
    
    # Collect from all sources
    items = collect_all_sources()
    
    # Save to file
    save_collected_items(items)

Design Principles:
- Consistent interface: All collectors return List[CollectedItem]
- Source-specific error handling
- Rate limiting per source
- Configurable limits and filters
"""

# Import all collectors
from .mastodon import (
    collect_from_mastodon,
    collect_from_mastodon_trending,
    collect_from_mastodon_public,
)
from .reddit import collect_from_reddit
from .hackernews import collect_from_hackernews
from .github import collect_from_github_trending

# Import utilities
from .orchestrator import (
    collect_all_sources,
    save_collected_items,
    deduplicate_items,
)

# Import base filtering functions (for use by other modules)
from .base import (
    is_entitled_whining,
    is_political_content,
    is_relevant_content,
    clean_html_content,
    extract_title_from_content,
)

__all__ = [
    # Collectors
    "collect_from_mastodon",
    "collect_from_mastodon_trending",
    "collect_from_mastodon_public",
    "collect_from_reddit",
    "collect_from_hackernews",
    "collect_from_github_trending",
    # Orchestration
    "collect_all_sources",
    # Utilities
    "save_collected_items",
    "deduplicate_items",
    # Filters (for use by other modules if needed)
    "is_entitled_whining",
    "is_political_content",
    "is_relevant_content",
    "clean_html_content",
    "extract_title_from_content",
]
