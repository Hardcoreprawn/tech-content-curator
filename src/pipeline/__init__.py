"""Pipeline orchestration package.

This package contains the main pipeline stages that orchestrate the content
curation workflow:

- Collection: Gathering content from various sources
- Enrichment: AI-powered analysis and scoring
- Generation: Creating articles from enriched content

Each stage is designed to be run independently or as part of the full pipeline,
enabling flexible workflows and easier testing.

Example:
    from src.pipeline import collect, enrich, generate
    
    # Run full pipeline
    items = collect.run()
    enriched = enrich.run(items)
    articles = generate.run(enriched)
    
    # Or run individual stages
    items = collect.run()

Design Principles:
- Each stage is independent and testable
- Clear data flow between stages (CollectedItem -> EnrichedItem -> GeneratedArticle)
- Graceful error handling with detailed logging
- Progress tracking and cost reporting
"""

# Pipeline stages will be imported here once refactored
# from .collect import run as run_collection
# from .enrich import run as run_enrichment
# from .generate import run as run_generation

__all__ = []
