"""Content enrichment package.

This package handles AI-powered analysis and enhancement of collected content.
It transforms raw CollectedItem objects into EnrichedItem objects with:

- Quality scores (0.0 to 1.0)
- Extracted topics and themes
- AI-generated research and context
- Entity extraction
- Source quality assessment

Components:
- scorer: Fast heuristic quality assessment
- ai_analyzer: OpenAI-powered content analysis
- orchestrator: Pipeline coordination and parallel processing
- file_io: Load/save operations for enriched content
- adaptive_scoring: Learning-based scoring improvements
- fact_check: Validation and fact-checking

Usage:
    from src.enrichment import (
        enrich_single_item,
        enrich_collected_items,
        calculate_heuristic_score,
        load_collected_items,
        save_enriched_items,
    )

    # Enrich a single item
    enriched = enrich_single_item(item, config)

    # Enrich all items in parallel
    all_enriched = enrich_collected_items(items, max_workers=5)

Design Principles:
- Fail gracefully: Return basic enrichment if AI fails
- Parallel processing with rate limiting
- Structured output for debugging
- Cost tracking for API calls
- Retry logic for transient failures

Enrichment Pipeline:
1. Initial quality check (quick filter)
2. Topic extraction (classify content)
3. Deep research (gather context)
4. Final scoring (rank for generation)
5. Adaptive learning (improve over time)
"""

# Import enrichment modules
from .adaptive_scoring import ScoringAdapter
from .ai_analyzer import (
    analyze_content_quality,
    extract_topics_and_themes,
    research_additional_context,
)
from .fact_check import validate_article
from .file_io import load_collected_items, load_enriched_items, save_enriched_items
from .orchestrator import enrich_collected_items, enrich_single_item
from .scorer import calculate_heuristic_score

__all__ = [
    # Core orchestration
    "enrich_single_item",
    "enrich_collected_items",
    # Scoring
    "calculate_heuristic_score",
    "ScoringAdapter",
    # AI analysis
    "analyze_content_quality",
    "extract_topics_and_themes",
    "research_additional_context",
    # File I/O
    "load_collected_items",
    "load_enriched_items",
    "save_enriched_items",
    # Validation
    "validate_article",
]
