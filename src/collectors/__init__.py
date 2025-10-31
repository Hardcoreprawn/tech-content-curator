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

# Collector functions will be imported here once refactored
# from .mastodon import collect_from_mastodon, collect_from_mastodon_trending
# from .bluesky import collect_from_bluesky
# from .reddit import collect_from_reddit
# from .hackernews import collect_from_hackernews

__all__ = []
