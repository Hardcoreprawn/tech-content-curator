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

from ..api.costs import CostTracker
from ..config import get_content_dir
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
from ..utils.logging import get_logger
from .deduplication import check_article_exists_for_source, is_source_in_cooldown

console = Console()
logger = get_logger(__name__)


def get_available_generators(client: OpenAI) -> list:
    """Get all available generators sorted by priority.

    Args:
        client: OpenAI client instance

    Returns:
        List of generators sorted by priority (highest first)
    """
    logger.debug("Loading available generators")
    from ..generators.general import GeneralArticleGenerator
    from ..generators.integrative import IntegrativeListGenerator

    generators = [
        IntegrativeListGenerator(client),
        GeneralArticleGenerator(client),  # Fallback - always last
    ]

    # Sort by priority (highest first)
    generators.sort(key=lambda g: g.priority, reverse=True)
    logger.info(f"Loaded {len(generators)} generators: {[g.name for g in generators]}")
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
    content_dir = get_content_dir()

    # Initialize adaptive dedup systems
    cost_tracker = CostTracker()
    adaptive_feedback = AdaptiveDedupFeedback()
    recent_cache = RecentContentCache(content_dir) if use_adaptive_filtering else None

    logger.info(
        f"Starting candidate selection from {len(items)} enriched items (min_quality={min_quality})"
    )
    rejection_reasons = {}

    for item in items:
        # Primary filter: quality score (AI-based, >= 0.5 for good content)
        # Log both heuristic and AI scores for tracking
        heuristic = getattr(item, "heuristic_score", 0)

        if item.quality_score < min_quality:
            reason = f"low_quality (AI: {item.quality_score:.2f} < {min_quality}, heur: {heuristic:.2f})"
            rejection_reasons[reason] = rejection_reasons.get(reason, 0) + 1
            logger.debug(f"Rejected {item.original.id}: {reason}")
            continue

        # Secondary filters: content substance (allow short if it's clearly technical)
        content_len = len(item.original.content)
        content_lower = item.original.content.lower()

        # If it's a curated list/listicle, allow even if short (handled by specialized generator)
        temp_gen = IntegrativeListGenerator(None)
        if temp_gen.can_handle(item):
            if item.topics:
                candidates.append(item)
                logger.debug(f"Accepted {item.original.id} as list/listicle content")
            else:
                reason = "list_format_but_no_topics"
                rejection_reasons[reason] = rejection_reasons.get(reason, 0) + 1
                logger.debug(f"Rejected {item.original.id}: {reason}")
            continue

        # Allow shorter content if it has strong technical signals (acronyms/links)
        has_link = "http" in content_lower
        has_acronym = bool(re.search(r"\b[A-Z0-9-]{2,10}\b", item.original.content))
        if content_len < 200 and not (has_link or has_acronym):
            reason = f"too_short ({content_len} chars, no links/acronyms)"
            rejection_reasons[reason] = rejection_reasons.get(reason, 0) + 1
            logger.debug(f"Rejected {item.original.id}: {reason}")
            continue

        if not item.topics:
            reason = "no_topics_identified"
            rejection_reasons[reason] = rejection_reasons.get(reason, 0) + 1
            logger.debug(f"Rejected {item.original.id}: {reason}")
            continue

        # Reject items without usable research context to avoid ungrounded articles
        research_summary = (item.research_summary or "").strip()
        if not research_summary or research_summary.lower().startswith(
            "research unavailable"
        ):
            reason = "research_unavailable"
            rejection_reasons[reason] = rejection_reasons.get(reason, 0) + 1
            logger.debug(f"Rejected {item.original.id}: {reason}")
            continue

        # Skip if we've already published an article for this source URL
        try:
            if check_article_exists_for_source(str(item.original.url), content_dir):
                reason = "source_already_published"
                rejection_reasons[reason] = rejection_reasons.get(reason, 0) + 1
                logger.debug(f"Rejected {item.original.id}: {reason}")
                console.print(
                    f"[dim]⏭ Skipping known source:[/dim] {item.original.title[:60]}..."
                )
                continue
        except Exception as e:
            logger.warning(
                f"Source existence check failed for {item.original.id}: {e}",
                exc_info=True,
            )

        # Skip if source is in cooldown period
        cooldown_days = int(os.getenv("SOURCE_COOLDOWN_DAYS", "7"))
        if is_source_in_cooldown(str(item.original.url), content_dir, cooldown_days):
            reason = f"source_in_cooldown ({cooldown_days}d)"
            rejection_reasons[reason] = rejection_reasons.get(reason, 0) + 1
            logger.debug(f"Rejected {item.original.id}: {reason}")
            console.print(
                f"[dim]⏸ In cooldown ({cooldown_days}d):[/dim] {item.original.title[:60]}..."
            )
            continue

        # Adaptive pre-generation filtering
        if use_adaptive_filtering and recent_cache:
            candidate_summary = item.research_summary[:200]

            is_dup, match = recent_cache.is_duplicate_candidate(
                item.original.title, candidate_summary, item.topics
            )

            if is_dup and match:
                recent_cache.report_match(match, item.original.title)
                cost_tracker.record_pre_gen_rejection(item.original.title)
                reason = "adaptive_dedup_match"
                rejection_reasons[reason] = rejection_reasons.get(reason, 0) + 1
                logger.debug(f"Rejected {item.original.id}: {reason}")
                console.print(
                    "[yellow]⏭ Rejected pre-generation (likely duplicate)[/yellow]"
                )
                continue

            # Check against learned duplicate patterns
            matches_pattern, pattern = adaptive_feedback.check_against_patterns(
                item.original.title, item.topics
            )

            if matches_pattern and pattern:
                reason = "learned_pattern_match"
                rejection_reasons[reason] = rejection_reasons.get(reason, 0) + 1
                logger.debug(f"Rejected {item.original.id}: {reason}")
                console.print(
                    f"[yellow]⚠ Matches learned duplicate pattern:[/yellow] "
                    f"{list(pattern.common_tags)[:3]}..."
                )
                console.print(
                    "[yellow]⏭ Rejected pre-generation (pattern match)[/yellow]"
                )
                continue

        candidates.append(item)
        logger.debug(
            f"Accepted {item.original.id} as candidate (quality: {item.quality_score:.3f})"
        )

    # Sort by quality score (best first)
    candidates.sort(key=lambda x: x.quality_score, reverse=True)

    # Show rejection summary
    if rejection_reasons:
        console.print("\n[yellow]📊 Rejection Summary:[/yellow]")
        for reason, count in sorted(
            rejection_reasons.items(), key=lambda x: x[1], reverse=True
        ):
            console.print(f"  {reason}: {count}")
        logger.info(
            f"Rejected {sum(rejection_reasons.values())} items: {rejection_reasons}"
        )

    console.print(
        f"[green]✓[/green] Selected {len(candidates)} candidates from {len(items)} enriched items"
    )
    logger.info(
        f"Candidate selection: {len(candidates)} candidates from {len(items)} items"
    )

    # Story clustering to detect cross-source duplicates
    if deduplicate_stories and len(candidates) > 1:
        console.print(
            "\n[blue]🔍 Checking for duplicate stories across sources...[/blue]"
        )

        # Find and report story clusters
        clusters = find_story_clusters(candidates, min_similarity=0.50)
        report_story_clusters(clusters, verbose=True)
        logger.info(f"Story clustering: found {len(clusters)} potential story clusters")

        # Filter out duplicate stories (keep best source for each story)
        pre_filter = len(candidates)
        candidates = filter_duplicate_stories(candidates, keep_best=True)
        logger.info(
            f"After story dedup: {len(candidates)} candidates (removed {pre_filter - len(candidates)})"
        )

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
