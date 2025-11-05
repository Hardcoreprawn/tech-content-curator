"""
Source tier system for content quality and selection.

Different sources have different signal-to-noise ratios. We want to:
1. Collect more from high-quality sources
2. Be more selective with noisy sources
3. Adapt selection percentage based on volume

Tier definitions:
- S-Tier: Curated, high signal (keep 50%+)
- A-Tier: Good signal, some noise (keep 30-40%)
- B-Tier: Mixed quality (keep 15-25%)
- C-Tier: Noisy, requires filtering (keep 5-10%)
"""

from dataclasses import dataclass
from enum import Enum

from ..utils.logging import get_logger

logger = get_logger(__name__)


class SourceTier(str, Enum):
    """Quality tiers for content sources."""

    S_TIER = "S"  # Curated, high-quality (HN top stories, GitHub trending)
    A_TIER = "A"  # Good quality (dev.to trending, tech blogs)
    B_TIER = "B"  # Mixed (Reddit hot, Mastodon trending)
    C_TIER = "C"  # Noisy (Reddit new, Twitter)


@dataclass
class SourceConfig:
    """Configuration for a content source."""

    name: str
    tier: SourceTier
    max_items: int  # Maximum to collect per run
    min_score: float  # Minimum quality score to keep
    description: str
    enabled: bool = True


# Source tier definitions
SOURCE_CONFIGS = {
    # S-Tier: Curated, high signal-to-noise
    "hackernews_top": SourceConfig(
        name="HackerNews Top Stories",
        tier=SourceTier.S_TIER,
        max_items=30,
        min_score=0.5,  # Lower threshold, trust the curation
        description="HN front page - already community-curated for quality",
    ),
    "github_trending": SourceConfig(
        name="GitHub Trending",
        tier=SourceTier.S_TIER,
        max_items=20,
        min_score=0.5,
        description="Trending repos - shows what's hot in open source",
    ),
    # A-Tier: Generally good quality with some noise
    "devto_trending": SourceConfig(
        name="dev.to Trending",
        tier=SourceTier.A_TIER,
        max_items=25,
        min_score=0.6,
        description="Developer blog posts - usually substantive",
    ),
    "lobsters_hot": SourceConfig(
        name="Lobsters Hot",
        tier=SourceTier.A_TIER,
        max_items=20,
        min_score=0.6,
        description="Tech-focused link aggregator with invite-only quality control",
    ),
    # B-Tier: Mixed quality, needs more filtering
    "reddit_programming": SourceConfig(
        name="Reddit r/programming",
        tier=SourceTier.B_TIER,
        max_items=20,
        min_score=0.65,
        description="Programming subreddit - hit or miss quality",
    ),
    "mastodon_trending": SourceConfig(
        name="Mastodon Trending",
        tier=SourceTier.B_TIER,
        max_items=20,
        min_score=0.65,
        description="Federated social media - varied quality",
    ),
    # C-Tier: Noisy, require heavy filtering
    "twitter_tech": SourceConfig(
        name="Twitter/X Tech Topics",
        tier=SourceTier.C_TIER,
        max_items=30,
        min_score=0.75,  # Much higher threshold
        description="Twitter tech hashtags - lots of noise",
        enabled=False,  # Disabled by default
    ),
}


def calculate_selection_percentage(item_count: int, tier: SourceTier) -> float:
    """
    Calculate what percentage of items to keep based on count and tier.

    Logic:
    - Fewer items = keep higher percentage (might miss good stuff)
    - More items = be more selective (can afford to be picky)
    - Higher tier = keep more (better signal-to-noise)
    - Lower tier = keep less (more noise)

    Args:
        item_count: Number of items collected from source
        tier: Quality tier of the source

    Returns:
        Percentage (0.0 to 1.0) of items to keep
    """
    logger.debug(f"Calculating selection percentage: tier={tier.value}, item_count={item_count}")
    # Base percentages by tier (for medium volumes ~30 items)
    base_percentages = {
        SourceTier.S_TIER: 0.60,  # Keep 60% of S-tier
        SourceTier.A_TIER: 0.40,  # Keep 40% of A-tier
        SourceTier.B_TIER: 0.25,  # Keep 25% of B-tier
        SourceTier.C_TIER: 0.10,  # Keep 10% of C-tier
    }

    base = base_percentages[tier]

    # Adjust based on volume
    if item_count <= 5:
        # Very few items - keep most of them unless really bad
        multiplier = 1.5
    elif item_count <= 15:
        # Small collection - keep more to ensure we have content
        multiplier = 1.3
    elif item_count <= 30:
        # Medium collection - use base percentage
        multiplier = 1.0
    elif item_count <= 60:
        # Large collection - be more selective
        multiplier = 0.8
    else:
        # Very large collection - be very selective
        multiplier = 0.6

    percentage = base * multiplier

    # Always keep at least 1 item if we collected anything
    min_items = max(1, int(item_count * 0.05))  # At least 5% or 1 item
    min_percentage = min_items / item_count if item_count > 0 else 0

    final_percentage = max(min_percentage, min(1.0, percentage))
    logger.debug(f"Calculated percentage: {final_percentage:.2%} (base={base:.2%}, multiplier={multiplier:.1f})")
    return final_percentage


def get_selection_strategy(source_name: str, item_count: int) -> dict:
    """
    Get the selection strategy for a source.

    Args:
        source_name: Name of the source
        item_count: Number of items collected

    Returns:
        Dict with selection parameters
    """
    logger.debug(f"Getting selection strategy for source: {source_name}, collected={item_count}")
    config = SOURCE_CONFIGS.get(source_name)
    if not config:
        # Unknown source - default to B-tier behavior
        logger.warning(f"Unknown source: {source_name}, defaulting to B-tier behavior")
        tier = SourceTier.B_TIER
        min_score = 0.65
    else:
        tier = config.tier
        min_score = config.min_score

    keep_percentage = calculate_selection_percentage(item_count, tier)
    target_count = int(item_count * keep_percentage)

    strategy_info = {
        "tier": tier.value,
        "keep_percentage": keep_percentage,
        "target_count": max(1, target_count),  # At least 1
        "min_score": min_score,
        "strategy": _describe_strategy(tier, item_count, target_count),
    }
    logger.info(f"Strategy: {strategy_info['strategy']} (min_score={min_score})")
    return strategy_info


def _describe_strategy(tier: SourceTier, collected: int, keeping: int) -> str:
    """Generate human-readable strategy description."""
    percentage = (keeping / collected * 100) if collected > 0 else 0

    tier_desc = {
        SourceTier.S_TIER: "high-quality curated",
        SourceTier.A_TIER: "good quality",
        SourceTier.B_TIER: "mixed quality",
        SourceTier.C_TIER: "noisy",
    }

    return (
        f"{tier.value}-tier ({tier_desc[tier]}): "
        f"keeping top {keeping}/{collected} ({percentage:.0f}%)"
    )


def select_best_items(items: list, scores: list[float], source_name: str) -> list:
    """
    Select the best items from a source based on tier and volume.

    Args:
        items: List of collected items
        scores: Corresponding quality scores
        source_name: Name of the source

    Returns:
        Filtered list of items
    """
    logger.debug(f"Selecting best items from {source_name}: {len(items)} items, {len(scores)} scores")
    if not items:
        logger.debug("No items to select")
        return []

    strategy = get_selection_strategy(source_name, len(items))

    # Combine items with scores and sort by score
    item_scores = list(zip(items, scores, strict=False))
    item_scores.sort(key=lambda x: x[1], reverse=True)

    # Apply both percentage-based and score-based filtering
    selected = []
    filtered_low_score = 0
    for item, score in item_scores:
        # Stop if we've hit our target count
        if len(selected) >= strategy["target_count"]:
            break

        # Skip if below minimum score threshold
        if score < strategy["min_score"]:
            filtered_low_score += 1
            continue

        selected.append(item)

    # If we got nothing but we have items, take at least the best one
    if not selected and items:
        logger.warning(f"No items met score threshold (min={strategy['min_score']}), taking best item")
        selected.append(item_scores[0][0])

    logger.info(f"Selected {len(selected)}/{len(items)} items from {source_name} (filtered {filtered_low_score} low-score items)")
    return selected


# Example usage and testing
if __name__ == "__main__":
    print("Source Tier Selection Examples:")
    print("=" * 80)

    test_cases = [
        ("hackernews_top", 30),
        ("hackernews_top", 5),
        ("hackernews_top", 100),
        ("reddit_programming", 30),
        ("reddit_programming", 5),
        ("reddit_programming", 100),
        ("twitter_tech", 50),
    ]

    for source, count in test_cases:
        strategy = get_selection_strategy(source, count)
        print(f"\n{source}: {count} items collected")
        print(f"  {strategy['strategy']}")
        print(f"  Min score: {strategy['min_score']}")
