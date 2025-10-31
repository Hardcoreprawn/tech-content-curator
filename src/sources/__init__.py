"""Source management package.

This package handles source prioritization, quality assessment, and filtering
logic for content sources.

Features:
- Source tier classification (TIER_1, TIER_2, TIER_3, TIER_FALLBACK)
- Quality-based selection percentages
- Source reputation tracking
- Selection strategy calculation

Components:
- tiers: Source tier definitions and selection logic
- filtering: Source-based filtering rules

Usage:
    from src.sources import SourceTier, get_selection_strategy
    
    strategy = get_selection_strategy("mastodon", item_count=100)
    # Returns: {"tier": "TIER_1", "percentage": 80, "keep": 80}

Design Principles:
- High-quality sources get priority
- Fallback to lower tiers when needed
- Configurable selection percentages
- Clear tier definitions
- Dynamic strategy based on available content

Source Tier Definitions:
- TIER_1 (80%): Mastodon trending - High engagement, community filtered
- TIER_2 (50%): Bluesky, Reddit - Good quality, moderated
- TIER_3 (30%): Hacker News, general feeds - Mixed quality
- TIER_FALLBACK (10%): Last resort, minimal filtering

Selection Strategy:
1. Try to get enough from TIER_1 sources
2. Supplement with TIER_2 if needed
3. Use TIER_3 sparingly
4. Fallback only when desperate
"""

# Import source management modules
from .tiers import (
    SourceTier,
    SourceConfig,
    get_selection_strategy,
    calculate_selection_percentage,
)

__all__ = [
    "SourceTier",
    "SourceConfig",
    "get_selection_strategy",
    "calculate_selection_percentage",
]
