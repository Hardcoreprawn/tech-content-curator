"""Article candidate selection and filtering.

This module handles the selection of enriched items suitable for article generation.
It applies multiple filters to ensure we only generate articles from high-quality content:

- Quality score thresholds
- Content length and substance checks
- Source deduplication (avoid duplicate articles from same source)
- Cooldown periods (avoid same source too frequently)
- Adaptive filtering (learned duplicate patterns)
- Story clustering (detect same story from multiple sources)

The goal is to maximize article quality while minimizing API costs by filtering
out unsuitable content BEFORE calling expensive generation APIs.
"""

import os
import re

from openai import OpenAI
from rich.console import Console

from ..config import get_content_dir
from ..costs import CostTracker
from ..deduplication import (
    AdaptiveDedupFeedback,
    RecentContentCache,
    filter_duplicate_stories,
    find_story_clusters,
    report_story_clusters,
)
from ..generators.base import BaseGenerator
from ..generators.integrative import IntegrativeListGenerator
from ..models import EnrichedItem
from .deduplication import check_article_exists_for_source, is_source_in_cooldown

console = Console()


def get_available_generators(client: OpenAI) -> list:
    """Get all available generators sorted by priority.

    Args:
        client: OpenAI client instance

    Returns:
        List of generators sorted by priority (highest first)
    """
    from ..generators.general import GeneralArticleGenerator
    from ..generators.integrative import IntegrativeListGenerator

    generators = [
        IntegrativeListGenerator(client),
        GeneralArticleGenerator(client),  # Fallback - always last
    ]

    # Sort by priority (highest first)
    generators.sort(key=lambda g: g.priority, reverse=True)
    return generators


def select_generator(item: EnrichedItem, generators: list) -> BaseGenerator:
    """Select the appropriate generator for an item.

    Checks generators in priority order and returns the first one that can handle the item.

    Args:
        item: The enriched item to generate content for
        generators: List of available generators (sorted by priority)

    Returns:
        The generator that should handle this item
    """
    for generator in generators:
        if generator.can_handle(item):
            return generator

    # Should never reach here since GeneralArticleGenerator can handle anything
    return generators[-1]


def select_article_candidates(
    items: list[EnrichedItem],
    min_quality: float = 0.5,
    use_adaptive_filtering: bool = True,
    deduplicate_stories: bool = True,
) -> list[EnrichedItem]:
    """Select items suitable for article generation.

    This filters items based on quality score and other criteria.
    We only want to spend API credits on content that will make good articles.

    NEW: Now includes adaptive dedup filtering to reject likely duplicates
    BEFORE generation, saving API costs.

    NEW: Story clustering to detect when multiple sources cover the same story.

    Args:
        items: List of enriched items
        min_quality: Minimum quality score (0.0-1.0)
        use_adaptive_filtering: If True, use recent content cache and learned patterns
        deduplicate_stories: If True, filter out duplicate stories from different sources

    Returns:
        List of items suitable for article generation
    """
    candidates = []
    # Preload content directory once for existing-source checks
    content_dir = get_content_dir()

    # Initialize adaptive dedup systems
    cost_tracker = CostTracker()
    adaptive_feedback = AdaptiveDedupFeedback()
    recent_cache = RecentContentCache(content_dir) if use_adaptive_filtering else None

    for item in items:
        # Primary filter: quality score
        if item.quality_score < min_quality:
            continue

        # Secondary filters: content substance (allow short if it's clearly technical)
        content_len = len(item.original.content)
        content_lower = item.original.content.lower()

        # If it's a curated list/listicle, allow even if short (handled by specialized generator)
        # Use the IntegrativeListGenerator to check
        temp_gen = IntegrativeListGenerator(None)  # No client needed for can_handle
        if temp_gen.can_handle(item):
            if item.topics:
                candidates.append(item)
            continue

        # Allow shorter content if it has strong technical signals (acronyms/links)
        has_link = "http" in content_lower
        has_acronym = bool(re.search(r"\b[A-Z0-9-]{2,10}\b", item.original.content))
        if content_len < 200 and not (
            has_link or has_acronym
        ):  # Too short without signals
            continue

        if not item.topics:  # No topics identified
            continue

        # Skip if we've already published an article for this source URL
        try:
            if check_article_exists_for_source(str(item.original.url), content_dir):
                console.print(
                    f"[dim]⏭ Skipping known source:[/dim] {item.original.title[:60]}..."
                )
                continue
        except Exception:
            # If the existence check fails for any reason, fall back to allowing the item
            pass

        # Skip if source is in cooldown period (avoid republishing same sources too frequently)
        cooldown_days = int(os.getenv("SOURCE_COOLDOWN_DAYS", "7"))
        if is_source_in_cooldown(str(item.original.url), content_dir, cooldown_days):
            console.print(
                f"[dim]⏸ In cooldown ({cooldown_days}d):[/dim] {item.original.title[:60]}..."
            )
            continue

        # NEW: Adaptive pre-generation filtering
        # Check if this would likely be a duplicate BEFORE spending API credits
        if use_adaptive_filtering and recent_cache:
            # Use enrichment summary as proxy for article content
            candidate_summary = item.research_summary[:200]  # First 200 chars

            # Check against recent articles
            is_dup, match = recent_cache.is_duplicate_candidate(
                item.original.title, candidate_summary, item.topics
            )

            if is_dup and match:
                recent_cache.report_match(match, item.original.title)
                cost_tracker.record_pre_gen_rejection(item.original.title)
                console.print(
                    "[yellow]⏭ Rejected pre-generation (likely duplicate)[/yellow]"
                )
                continue

            # Check against learned duplicate patterns
            matches_pattern, pattern = adaptive_feedback.check_against_patterns(
                item.original.title, item.topics
            )

            if matches_pattern and pattern:
                console.print(
                    f"[yellow]⚠ Matches learned duplicate pattern:[/yellow] "
                    f"{list(pattern.common_tags)[:3]}..."
                )
                cost_tracker.record_pre_gen_rejection(item.original.title)
                console.print(
                    "[yellow]⏭ Rejected pre-generation (pattern match)[/yellow]"
                )
                continue

        candidates.append(item)

    # Sort by quality score (best first)
    candidates.sort(key=lambda x: x.quality_score, reverse=True)

    console.print(
        f"[green]✓[/green] Selected {len(candidates)} candidates from {len(items)} enriched items"
    )

    # NEW: Story clustering to detect cross-source duplicates
    # This catches "Affinity Studio" from HackerNews + "Affinity Software" from Mastodon
    if deduplicate_stories and len(candidates) > 1:
        console.print(
            "\n[blue]🔍 Checking for duplicate stories across sources...[/blue]"
        )

        # Find and report story clusters
        clusters = find_story_clusters(candidates, min_similarity=0.50)
        report_story_clusters(clusters, verbose=True)

        # Filter out duplicate stories (keep best source for each story)
        candidates = filter_duplicate_stories(candidates, keep_best=True)

    # Print cache stats if using adaptive filtering
    if use_adaptive_filtering and recent_cache:
        stats = recent_cache.get_cache_stats()
        console.print(
            f"[dim]Recent cache: {stats['cached_articles']} articles, "
            f"{stats['unique_tags']} unique tags[/dim]"
        )

    return candidates


def select_diverse_candidates(
    candidates: list[EnrichedItem], max_articles: int = 5
) -> list[EnrichedItem]:
    """Select diverse set of candidates to avoid topic clustering.

    This ensures we don't generate 5 articles all about the same topic.
    Spreads articles across different topics for better content diversity.

    Args:
        candidates: List of candidate items (already sorted by quality)
        max_articles: Maximum number of articles to select

    Returns:
        Diverse subset of candidates
    """
    if len(candidates) <= max_articles:
        return candidates

    selected = []
    seen_topics = set()

    # First pass: select items with unique topics
    for item in candidates:
        if len(selected) >= max_articles:
            break

        # Check if this item introduces new topics
        item_topics = set(item.topics[:3])  # Consider top 3 topics
        if not item_topics & seen_topics:  # No overlap with seen topics
            selected.append(item)
            seen_topics.update(item_topics)

    # Second pass: fill remaining slots with best remaining items
    remaining = [c for c in candidates if c not in selected]
    while len(selected) < max_articles and remaining:
        selected.append(remaining.pop(0))

    return selected
