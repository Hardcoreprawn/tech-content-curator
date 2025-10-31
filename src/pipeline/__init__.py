"""Pipeline orchestration package.

This package contains the main pipeline stages that orchestrate the content
curation workflow:

- Collection: Gathering content from various sources
- Enrichment: AI-powered analysis and scoring
- Generation: Creating articles from enriched content

Each stage is designed to be run independently or as part of the full pipeline,
enabling flexible workflows and easier testing.

Example:
    from src.pipeline import generate_articles_from_enriched, load_enriched_items
    
    # Load and generate articles
    items = load_enriched_items(Path("data/enriched_latest.json"))
    articles = generate_articles_from_enriched(items, max_articles=5)

Design Principles:
- Each stage is independent and testable
- Clear data flow between stages (CollectedItem -> EnrichedItem -> GeneratedArticle)
- Graceful error handling with detailed logging
- Progress tracking and cost reporting
"""

# Article generation pipeline
from .orchestrator import generate_articles_from_enriched, generate_single_article
from .file_io import load_enriched_items, save_article_to_file
from .candidate_selector import (
    get_available_generators,
    select_article_candidates,
    select_generator,
)
from .deduplication import (
    check_article_exists_for_source,
    collect_existing_source_urls,
    is_source_in_cooldown,
)
from .article_builder import (
    calculate_image_cost,
    calculate_text_cost,
    create_article_metadata,
    generate_article_slug,
    generate_article_title,
)

__all__ = [
    # Main orchestration
    "generate_articles_from_enriched",
    "generate_single_article",
    # File I/O
    "load_enriched_items",
    "save_article_to_file",
    # Candidate selection
    "get_available_generators",
    "select_article_candidates",
    "select_generator",
    # Deduplication
    "check_article_exists_for_source",
    "collect_existing_source_urls",
    "is_source_in_cooldown",
    # Article building
    "calculate_image_cost",
    "calculate_text_cost",
    "create_article_metadata",
    "generate_article_slug",
    "generate_article_title",
]
