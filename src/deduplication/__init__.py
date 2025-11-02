"""Deduplication package.

This package provides comprehensive deduplication capabilities across multiple
stages of the content pipeline:

Pre-Generation Deduplication:
- Semantic similarity detection (embeddings-based)
- Story clustering (same news from different sources)
- Recent content cache (avoid repeating recent topics)
- Adaptive learning from user feedback

Post-Generation Deduplication:
- Article similarity detection
- Entity overlap analysis
- Title and content similarity
- Duplicate article reporting

Components:
- semantic_dedup: Embedding-based similarity detection
- story_clustering: Group related stories together
- adaptive_dedup: Learning-based deduplication
- post_gen_dedup: Post-generation duplicate detection
- recent_content_cache: Track recently published content
- dedup_feedback: User feedback processing

Usage:
    from src.deduplication import (
        deduplicate_semantic,
        find_story_clusters,
        filter_duplicate_stories
    )

    # Pre-generation dedup
    unique_items = deduplicate_semantic(items, threshold=0.85)
    clusters = find_story_clusters(items)
    filtered = filter_duplicate_stories(items, clusters)

    # Post-generation dedup
    duplicates = find_duplicate_articles(articles)

Design Principles:
- Multiple dedup strategies for different use cases
- Configurable thresholds for precision/recall trade-offs
- Learning from user feedback
- Clear reporting of dedup decisions
- Preserve best version when duplicates found

Deduplication Strategies:
1. URL-based: Exact source URL matching (100% precision)
2. Semantic: Embedding similarity (high recall)
3. Story clustering: Entity and text similarity (news stories)
4. Recent cache: Time-based content freshness
5. Adaptive: Learned patterns from feedback
"""

# Import all deduplication modules
from .adaptive_dedup import AdaptiveDedupFeedback
from .dedup_feedback import DeduplicationFeedback, DeduplicationFeedbackSystem
from .post_gen_dedup import (
    calculate_entity_similarity,
    extract_entities,
    find_duplicate_articles,
    report_duplicate_candidates,
)
from .recent_content_cache import RecentContentCache
from .semantic_dedup import DuplicationPattern, SemanticDeduplicator
from .story_clustering import (
    StoryCluster,
    filter_duplicate_stories,
    find_story_clusters,
    report_story_clusters,
)

__all__ = [
    # Semantic deduplication
    "SemanticDeduplicator",
    "DuplicationPattern",
    # Story clustering
    "find_story_clusters",
    "filter_duplicate_stories",
    "report_story_clusters",
    "StoryCluster",
    # Adaptive deduplication
    "AdaptiveDedupFeedback",
    # Post-generation deduplication
    "find_duplicate_articles",
    "report_duplicate_candidates",
    "calculate_entity_similarity",
    "extract_entities",
    # Recent content cache
    "RecentContentCache",
    # Feedback
    "DeduplicationFeedback",
    "DeduplicationFeedbackSystem",
]
