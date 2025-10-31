"""Content enrichment package.

This package handles AI-powered analysis and enhancement of collected content.
It transforms raw CollectedItem objects into EnrichedItem objects with:

- Quality scores (0.0 to 1.0)
- Extracted topics and themes
- AI-generated research and context
- Entity extraction
- Source quality assessment

Components:
- scorer: Quality assessment and ranking
- researcher: AI-powered research and context gathering
- analyzer: Topic and entity extraction
- adaptive_scoring: Learning-based scoring improvements
- fact_check: Validation and fact-checking

Usage:
    from src.enrichment import enrich_item, enrich_items_parallel
    
    enriched = await enrich_item(collected_item, config)
    all_enriched = await enrich_items_parallel(items, config)

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

# Enrichment functions will be imported here once refactored
# from .scorer import score_item, calculate_quality_score
# from .researcher import research_item, gather_context
# from .analyzer import extract_topics, extract_entities
# from .adaptive_scoring import ScoringAdapter
# from .fact_check import validate_article

__all__ = []
