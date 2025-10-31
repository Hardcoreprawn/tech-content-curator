"""Pipeline orchestration for article generation.

This module coordinates the full article generation pipeline, from candidate
selection through content generation, title creation, and file saving.
"""

import os
from datetime import UTC, datetime
from pathlib import Path

from openai import OpenAI
from rich.console import Console

from ..config import PipelineConfig, get_config
from ..costs import CostTracker
from ..enrichment.fact_check import validate_article
from ..models import EnrichedItem, GeneratedArticle
from ..deduplication.adaptive_dedup import AdaptiveDedupFeedback
from ..generators.base import BaseGenerator
from .article_builder import (
    calculate_text_cost,
    create_article_metadata,
    generate_article_slug,
    generate_article_title,
)
from .candidate_selector import get_available_generators, select_generator
from .deduplication import check_article_exists_for_source
from .file_io import save_article_to_file

console = Console()


def generate_single_article(
    item: EnrichedItem,
    config: PipelineConfig,
    generators: list[BaseGenerator],
    client: OpenAI,
    force_regenerate: bool = False,
    action_run_id: str | None = None,
) -> GeneratedArticle | None:
    """Generate a complete article from an enriched item.

    This orchestrates the full article generation process using the appropriate generator.

    Args:
        item: The enriched item to turn into an article
        config: Pipeline configuration
        generators: List of available generators
        client: OpenAI client for API calls
        force_regenerate: If True, delete and regenerate existing articles
        action_run_id: GitHub Actions run ID that triggered this generation

    Returns:
        GeneratedArticle if successful, None if generation fails
    """
    console.print(f"[blue]Generating article:[/blue] {item.original.title[:50]}...")

    try:
        # Step 1: Check if article for this source already exists
        existing_file = check_article_exists_for_source(
            str(item.original.url), config.content_dir
        )
        if existing_file:
            if force_regenerate:
                console.print(
                    "[yellow]♻ Regenerating - deleting existing article[/yellow]"
                )
                existing_file.unlink()
            else:
                console.print(
                    "[yellow]⚠ Skipping - article already exists for this source[/yellow]"
                )
                return None

        # Step 2: Select appropriate generator and generate content
        generator = select_generator(item, generators)
        console.print(f"  Using: {generator.name}")
        console.print(f"  [dim]Calling OpenAI API for content generation...[/dim]")
        content, content_input_tokens, content_output_tokens = generator.generate_content(item)
        word_count = len(content.split())
        console.print(f"  Content: {word_count} words")

        # Initialize cost tracking
        costs = {}
        
        # Calculate actual content generation cost from token usage
        costs["content_generation"] = calculate_text_cost(
            "gpt-4o-mini", content_input_tokens, content_output_tokens
        )

        # Step 3: Generate title FROM the article content
        title, title_cost = generate_article_title(item, content, client)
        costs["title_generation"] = title_cost
        console.print(f"  Title: {title}")

        # Step 4: Create metadata
        metadata = create_article_metadata(item, title, content)

        # Step 5: Generate SEO-friendly slug from the title
        slug, slug_cost = generate_article_slug(title, client)
        costs["slug_generation"] = slug_cost
        console.print(f"  Slug: {slug}")

        # Step 6: Create filename (date + slug)
        filename = f"{datetime.now().strftime('%Y-%m-%d')}-{slug}.md"

        # Step 7: Create GeneratedArticle with cost tracking
        article = GeneratedArticle(
            title=title,
            content=content,
            summary=metadata["summary"],
            sources=[item],
            tags=item.topics[:5],
            word_count=word_count,
            generated_at=datetime.now(UTC),
            filename=filename,
            generation_costs=costs,
            action_run_id=action_run_id,
        )

        console.print(f"[green]✓[/green] Generated: {title}")
        return article

    except Exception as e:
        console.print(f"[red]✗[/red] Article generation failed: {e}")
        return None


def _select_diverse_candidates(
    candidates: list[EnrichedItem], max_articles: int, generators: list[BaseGenerator]
) -> list[EnrichedItem]:
    """Pick a diverse set of candidates within the limit.

    Heuristic: Prefer including at least one from each specialized generator when available,
    then fill the rest by quality.

    Args:
        candidates: Already quality-sorted candidates (best first)
        max_articles: Upper bound to return
        generators: List of available generators

    Returns:
        Ordered list of selected items (length <= max_articles)
    """
    if max_articles <= 0 or not candidates:
        return []

    selected: list[EnrichedItem] = []

    # Partition buckets by generator (skip general generator)
    specialized_gens = [g for g in generators if g.priority > 0]
    buckets = {gen.name: [] for gen in specialized_gens}

    for item in candidates:
        for gen in specialized_gens:
            if gen.can_handle(item):
                buckets[gen.name].append(item)
                break

    # Helper to append if capacity remains
    def try_add(item: EnrichedItem):
        if len(selected) < max_articles and item not in selected:
            selected.append(item)

    # Ensure coverage: pick one from each specialized generator when available
    for _gen_name, items in buckets.items():
        if items:
            try_add(items[0])

    # Fill remaining slots by overall quality order
    for c in candidates:
        if len(selected) >= max_articles:
            break
        try_add(c)

    return selected


def generate_articles_from_enriched(
    items: list[EnrichedItem],
    max_articles: int = 3,
    force_regenerate: bool = False,
    generate_images: bool = False,
    fact_check: bool = False,
    action_run_id: str | None = None,
) -> list[GeneratedArticle]:
    """Generate blog articles from enriched items.

    This is the main entry point for article generation.

    Args:
        items: List of enriched items
        max_articles: Maximum number of articles to generate
        force_regenerate: If True, regenerate existing articles
        generate_images: If True, generate cover images
        fact_check: If True, validate articles
        action_run_id: GitHub Actions run ID for tracking

    Returns:
        List of successfully generated articles
    """
    config = get_config()
    client = OpenAI(
        api_key=config.openai_api_key,
        timeout=120.0,  # 120 second timeout for API calls
        max_retries=2,  # Retry up to 2 times on transient errors
    )
    
    # Get action_run_id from environment if not provided
    if not action_run_id:
        action_run_id = os.getenv("GITHUB_RUN_ID")

    # Get available generators
    from .candidate_selector import select_article_candidates
    generators = get_available_generators(client)

    # Select high-quality candidates
    console.print("\n[bold blue]📋 Selecting article candidates...[/bold blue]")
    candidates = select_article_candidates(items)
    
    if not candidates:
        console.print("[yellow]No suitable article candidates found.[/yellow]")
        return []

    # Apply diversity selection
    selected = _select_diverse_candidates(candidates, max_articles, generators)
    
    console.print(f"[green]✓[/green] Selected {len(selected)} diverse candidates")

    # Generate articles
    console.print(f"\n[bold blue]📝 Generating {len(selected)} articles...[/bold blue]")
    
    articles: list[GeneratedArticle] = []
    fact_check_results = []
    cost_tracker = CostTracker()
    adaptive_feedback = AdaptiveDedupFeedback()
    
    for i, item in enumerate(selected, 1):
        console.print(f"\n[bold cyan]Article {i}/{len(selected)}[/bold cyan]")
        
        article = generate_single_article(
            item, config, generators, client, force_regenerate, action_run_id
        )
        
        if article:
            # Save article to file
            try:
                save_article_to_file(article, config, generate_images, client)
                articles.append(article)
                
                # Record costs
                cost_tracker.record_successful_generation(
                    article.title, article.filename, article.generation_costs
                )
                
                # Optional fact-checking
                if fact_check:
                    result = validate_article(article, [item])
                    fact_check_results.append((article, result))

            except Exception as e:
                console.print(f"[red]✗[/red] Failed to save article: {e}")
                continue

    console.print(
        f"\n[bold green]✓ Article generation complete: {len(articles)} articles created[/bold green]"
    )
    
    # Print fact-check summary if enabled
    if fact_check and fact_check_results:
        console.print("\n[bold cyan]📋 Fact-Check Summary:[/bold cyan]")
        passed = sum(1 for _, r in fact_check_results if r.passed)
        console.print(f"  Passed: {passed}/{len(fact_check_results)}")
        
        failed = [(a, r) for a, r in fact_check_results if not r.passed]
        if failed:
            console.print("\n[yellow]⚠ Failed Articles:[/yellow]")
            for article, result in failed:
                console.print(f"  • {article.title[:60]}")
                console.print(f"    Confidence: {result.confidence_score:.2f}")
                if result.unreachable_sources:
                    console.print(f"    Unreachable sources: {len(result.unreachable_sources)}")
                if result.broken_links:
                    console.print(f"    Broken links: {len(result.broken_links)}")
    
    # Print compact summary of new files
    if articles:
        console.print("\n[bold cyan]📝 New Articles:[/bold cyan]")
        for article in articles:
            console.print(f"  • {article.filename}")
            console.print(f"    Title: {article.title}")
            console.print(f"    Words: {article.word_count}, Score: {article.sources[0].quality_score:.2f}")
    
    # Print cost summary and adaptive dedup stats
    cost_tracker.print_summary(days=7)  # Last 7 days
    adaptive_feedback.print_stats()
    
    return articles
