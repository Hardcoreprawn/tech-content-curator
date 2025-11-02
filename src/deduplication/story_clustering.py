"""Story clustering for cross-source deduplication.

This module identifies when multiple items from different sources are about the SAME
underlying news story, even if they have different angles or perspectives.

Example:
- Item 1 (HackerNews): "Affinity Studio Goes Free"
- Item 2 (Mastodon): "Affinity Software's Freemium Shift: What Artists Need to Know"
→ Both are about Affinity's business model change, should be consolidated

This is different from post_gen_dedup.py which catches near-identical duplicates.
This catches RELATED articles about the same story before generation.

See: docs/RELATED-ARTICLES-CURATION.md
"""

from dataclasses import dataclass
from difflib import SequenceMatcher

from rich.console import Console

from ..models import EnrichedItem
from .post_gen_dedup import calculate_entity_similarity, extract_entities

console = Console()


@dataclass
class StoryCluster:
    """A group of items that are about the same underlying story."""

    items: list[EnrichedItem]
    primary_item: EnrichedItem  # Highest quality item
    story_signature: str  # Key entities/topics that define this story
    consolidation_score: float  # How confident we are these are the same story

    @property
    def should_consolidate(self) -> bool:
        """Should these items be merged into one article?"""
        # Only consolidate if we have multiple items and high confidence
        return len(self.items) > 1 and self.consolidation_score > 0.6

    @property
    def sources_summary(self) -> str:
        """Human-readable summary of sources in this cluster."""
        sources = [item.original.source for item in self.items]
        return f"{len(self.items)} sources: {', '.join(set(sources))}"


def extract_story_entities(item: EnrichedItem) -> set[str]:
    """Extract key entities that define what story this is about.

    Focuses on:
    - Company/product names (Affinity, Microsoft, ICC)
    - Key concepts (freemium, open-source, acquisition)
    - Technology terms

    Args:
        item: Enriched item

    Returns:
        Set of normalized entity strings
    """
    # Combine title + summary for better entity extraction
    text = f"{item.original.title} {item.research_summary}"
    entities = extract_entities(text)

    # Also include topics as entities (they're already extracted/classified)
    entities.update(topic.lower() for topic in item.topics)

    return entities


def calculate_story_similarity(item1: EnrichedItem, item2: EnrichedItem) -> float:
    """Calculate how likely two items are about the same story.

    This uses multiple signals:
    1. Entity overlap (key indicator of same story)
    2. Topic overlap (similar subject matter)
    3. Time proximity (published close together)
    4. Title similarity (less weight than entities)

    Args:
        item1: First item
        item2: Second item

    Returns:
        Similarity score 0.0-1.0 (higher = more likely same story)
    """
    # Extract story-defining entities
    entities1 = extract_story_entities(item1)
    entities2 = extract_story_entities(item2)

    # Strong entity overlap is the primary signal
    entity_sim = calculate_entity_similarity(entities1, entities2)

    # Topic overlap (tags)
    topics1 = {t.lower() for t in item1.topics}
    topics2 = {t.lower() for t in item2.topics}
    topic_overlap = len(topics1 & topics2) / max(len(topics1), len(topics2), 1)

    # Title similarity (less important, but still a signal)
    title_sim = SequenceMatcher(
        None, item1.original.title.lower(), item2.original.title.lower()
    ).ratio()

    # Time proximity (same day = more likely same story)
    time_diff = abs(
        (item1.original.collected_at - item2.original.collected_at).total_seconds()
    )
    time_proximity = 1.0 if time_diff < 86400 else 0.5  # 24 hours

    # Weighted combination (entity overlap is most important)
    score = (
        entity_sim * 0.50  # Strong entity match = likely same story
        + topic_overlap * 0.30  # Similar topics (increased from 0.25)
        + title_sim * 0.10  # Similar titles (decreased from 0.15)
        + time_proximity * 0.10  # Published close together
    )

    # Boost score if we have strong entity match AND good topic overlap
    # This catches cases like "Affinity Studio" + "Affinity Software"
    if entity_sim > 0.3 and topic_overlap > 0.5:
        score = min(1.0, score + 0.10)  # +10% bonus, cap at 100%

    return score


def find_story_clusters(
    items: list[EnrichedItem], min_similarity: float = 0.50
) -> list[StoryCluster]:
    """Group items into story clusters.

    Uses a greedy clustering approach:
    1. Sort items by quality (best first)
    2. For each item, check if it matches an existing cluster
    3. If not, create a new cluster

    Args:
        items: List of enriched items to cluster
        min_similarity: Minimum similarity to consider items as same story

    Returns:
        List of StoryCluster objects
    """
    if not items:
        return []

    # Sort by quality (best first)
    sorted_items = sorted(items, key=lambda x: x.quality_score, reverse=True)

    clusters: list[StoryCluster] = []

    for item in sorted_items:
        # Check if this item belongs to an existing cluster
        best_cluster = None
        best_similarity = 0.0

        for cluster in clusters:
            # Compare against the primary item in the cluster
            similarity = calculate_story_similarity(item, cluster.primary_item)
            if similarity > best_similarity and similarity >= min_similarity:
                best_similarity = similarity
                best_cluster = cluster

        if best_cluster:
            # Add to existing cluster
            best_cluster.items.append(item)
            best_cluster.consolidation_score = max(
                best_cluster.consolidation_score, best_similarity
            )
            # Update story signature with new entities
            new_entities = extract_story_entities(item)
            existing_sig = set(best_cluster.story_signature.split(", "))
            combined = existing_sig | new_entities
            best_cluster.story_signature = ", ".join(sorted(combined)[:5])
        else:
            # Create new cluster
            entities = extract_story_entities(item)
            clusters.append(
                StoryCluster(
                    items=[item],
                    primary_item=item,
                    story_signature=", ".join(sorted(entities)[:5]),  # Top 5 entities
                    consolidation_score=1.0,  # Single item = 100% confidence
                )
            )

    # Sort clusters by consolidation opportunity (multi-source first)
    clusters.sort(key=lambda c: (len(c.items), c.consolidation_score), reverse=True)

    return clusters


def filter_duplicate_stories(
    items: list[EnrichedItem], keep_best: bool = True, min_similarity: float = 0.50
) -> list[EnrichedItem]:
    """Filter out duplicate stories, keeping only the best item from each cluster.

    This is the automatic solution: before generating articles, detect and remove
    items that are about the same story from different sources.

    Args:
        items: List of enriched items
        keep_best: If True, keep the highest quality item from each cluster
        min_similarity: Minimum similarity to consider items as same story

    Returns:
        Filtered list with one item per story
    """
    clusters = find_story_clusters(items, min_similarity)

    if not clusters:
        return items

    # Report findings
    multi_source_clusters = [c for c in clusters if len(c.items) > 1]
    if multi_source_clusters:
        console.print(
            f"\n[yellow]📰 Found {len(multi_source_clusters)} stories covered by "
            f"multiple sources:[/yellow]"
        )
        for i, cluster in enumerate(multi_source_clusters, 1):
            console.print(f"\n  Story {i}: {cluster.story_signature}")
            console.print(f"  Confidence: {cluster.consolidation_score:.1%}")
            console.print(f"  {cluster.sources_summary}")
            for item in cluster.items:
                quality_badge = "⭐" if item == cluster.primary_item else "  "
                console.print(
                    f"    {quality_badge} [{item.original.source}] "
                    f"{item.original.title[:60]}..."
                )

    if keep_best:
        # Keep only the primary (best quality) item from each cluster
        filtered = [cluster.primary_item for cluster in clusters]
        removed_count = len(items) - len(filtered)
        if removed_count > 0:
            console.print(
                f"\n[green]✓ Filtered out {removed_count} duplicate stories "
                f"(keeping best source for each)[/green]"
            )
        return filtered
    else:
        # Keep all items (for manual review)
        return items


def consolidate_story_sources(cluster: StoryCluster) -> EnrichedItem:
    """Consolidate multiple items about the same story into a single enriched item.

    This creates a new EnrichedItem that combines perspectives from all sources,
    giving the article generator richer context to work with.

    Args:
        cluster: Story cluster to consolidate

    Returns:
        New EnrichedItem with consolidated information
    """
    # Use the primary (best quality) item as the base
    primary = cluster.primary_item

    # Combine research summaries from all sources
    combined_summary = f"{primary.research_summary}\n\n"

    for item in cluster.items:
        if item != primary:
            combined_summary += f"Additional perspective from {item.original.source}:\n"
            combined_summary += f"{item.research_summary}\n\n"

    # Merge topics (deduplicate)
    all_topics = set()
    for item in cluster.items:
        all_topics.update(item.topics)

    # Combine related sources
    all_related_sources = []
    for item in cluster.items:
        all_related_sources.extend(item.related_sources)

    # Calculate average quality score
    avg_quality = sum(item.quality_score for item in cluster.items) / len(cluster.items)

    # Create consolidated item (using primary's original as base)
    consolidated = EnrichedItem(
        original=primary.original,
        research_summary=combined_summary.strip(),
        related_sources=list(set(all_related_sources)),  # Deduplicate
        topics=sorted(all_topics),
        quality_score=max(
            avg_quality, primary.quality_score
        ),  # Use max to prefer consolidation
        enriched_at=primary.enriched_at,
    )

    return consolidated


def report_story_clusters(clusters: list[StoryCluster], verbose: bool = False) -> None:
    """Print a formatted report of story clusters.

    Args:
        clusters: List of story clusters
        verbose: If True, show detailed information
    """
    if not clusters:
        console.print("[green]✓ No story clusters found[/green]")
        return

    multi_source = [c for c in clusters if len(c.items) > 1]
    single_source = [c for c in clusters if len(c.items) == 1]

    console.print("\n[bold cyan]📊 Story Clustering Summary:[/bold cyan]")
    console.print(f"  Total stories: {len(clusters)}")
    console.print(f"  Multi-source stories: {len(multi_source)}")
    console.print(f"  Single-source stories: {len(single_source)}")

    if multi_source and verbose:
        console.print("\n[bold yellow]Multi-Source Stories:[/bold yellow]")
        for i, cluster in enumerate(multi_source, 1):
            console.print(f"\n  {i}. {cluster.story_signature}")
            console.print(f"     Confidence: {cluster.consolidation_score:.1%}")
            console.print(f"     {cluster.sources_summary}")
            console.print(
                f"     Should consolidate: {'✓ Yes' if cluster.should_consolidate else '✗ No'}"
            )
            if verbose:
                for item in cluster.items:
                    quality_badge = "⭐" if item == cluster.primary_item else "  "
                    console.print(
                        f"       {quality_badge} [{item.original.source}] "
                        f"{item.original.title[:50]}..."
                    )
