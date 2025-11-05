"""Streamlined pipeline orchestration for article generation.

This module coordinates the article generation pipeline with a clean,
modular design. Thread-safe and optimized for Python 3.14 free-threading.
"""

from __future__ import annotations

import asyncio
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

from openai import OpenAI
from rich.console import Console

from ..api.openai_error_handler import handle_openai_error, is_fatal
from ..config import PipelineConfig, get_config, get_content_dir
from ..costs import CostTracker
from ..deduplication.adaptive_dedup import AdaptiveDedupFeedback
from ..enrichment.fact_check import FactCheckResult, validate_article
from ..generators.base import BaseGenerator
from ..models import EnrichedItem, GeneratedArticle
from .article_builder import (
    calculate_text_cost,
    create_article_metadata,
    generate_article_slug,
    generate_article_title,
)
from .candidate_selector import (
    get_available_generators,
    select_article_candidates,
    select_generator,
)
from .deduplication import check_article_exists_for_source
from .diversity_selector import select_diverse_candidates
from .file_io import save_article_to_file
from .illustration_service import IllustrationService
from .tracking import PipelineTracker

# Optional mdformat support
try:
    from mdformat import text as format_markdown
except ImportError:
    format_markdown = None

console = Console()
logger = logging.getLogger(__name__)


def generate_single_article(
    item: EnrichedItem,
    generators: list[BaseGenerator],
    client: OpenAI,
    illustration_service: IllustrationService | None = None,
    force_regenerate: bool = False,
    action_run_id: str | None = None,
    config: PipelineConfig | None = None,  # Backwards compatibility
) -> GeneratedArticle | None:
    """Generate a complete article from an enriched item.

    Args:
        item: The enriched item to turn into an article
        generators: List of available generators
        client: OpenAI client for API calls
        illustration_service: Optional pre-configured illustration service
        force_regenerate: If True, delete and regenerate existing articles
        action_run_id: GitHub Actions run ID that triggered this generation
        config: Optional pipeline config (for backwards compatibility, auto-detected if not provided)

    Returns:
        GeneratedArticle if successful, None if generation fails
    """
    if config is None:
        config = illustration_service.config if illustration_service else get_config()
    console.print(f"[blue]Generating article:[/blue] {item.original.title[:50]}...")

    try:
        # Check if article already exists
        content_dir = get_content_dir()
        existing_file = check_article_exists_for_source(
            str(item.original.url), content_dir
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

        # Generate content
        generator = select_generator(item, generators)
        console.print(f"  Using: {generator.name}")

        # Select voice for this article (Phase 1 feature)
        voice_id = "default"
        try:
            from ..generators.voices.selector import VoiceSelector
            voice_selector = VoiceSelector()
            voice_profile = voice_selector.select_voice(
                content_type=getattr(item, "content_type", "general"),
                complexity_score=item.quality_score,
            )
            voice_id = voice_profile.voice_id
            console.print(f"  Voice: {voice_profile.name}")
            voice_selector.add_to_history(
                generate_article_slug(item.original.title), voice_id
            )
        except (ImportError, ModuleNotFoundError):
            # Voice system not available (backwards compatibility)
            console.print("  Voice: default (module not available)")

        console.print("  [dim]Calling OpenAI API for content generation...[/dim]")
        content, content_input_tokens, content_output_tokens = (
            generator.generate_content(item)
        )
        word_count = len(content.split())
        console.print(f"  Content: {word_count} words")

        # Initialize cost tracking
        costs: dict[str, float] = {
            "content_generation": calculate_text_cost(
                "gpt-4o-mini", content_input_tokens, content_output_tokens
            )
        }

        # Generate title and slug
        title, title_cost = generate_article_title(item, content, client)
        costs["title_generation"] = title_cost
        console.print(f"  Title: {title}")

        metadata = create_article_metadata(item, title, content)

        slug = generate_article_slug(title)
        console.print(f"  Slug: {slug}")

        filename = f"{datetime.now().strftime('%Y-%m-%d')}-{slug}.md"

        # Generate illustrations if enabled
        illustrations_count = 0
        final_content = content

        if config.enable_illustrations:
            if illustration_service is None:
                illustration_service = IllustrationService(client, config)

            result = illustration_service.generate_illustrations(
                generator.name, content
            )

            final_content = result.content
            illustrations_count = result.count
            costs.update(result.costs)

        # Format markdown
        if format_markdown is not None:
            try:
                final_content = format_markdown(final_content)
            except Exception as e:
                logger.warning(f"Markdown formatting failed: {e}")
                console.print(
                    f"  [dim]Note: markdown formatting skipped ({str(e)[:30]})[/dim]"
                )
        else:
            console.print(
                "  [dim]Note: mdformat not available, skipping markdown formatting[/dim]"
            )

        # Create article
        article = GeneratedArticle(
            title=title,
            content=final_content,
            summary=metadata["summary"],
            sources=[item],
            tags=item.topics[:5],
            word_count=word_count,
            generated_at=datetime.now(UTC),
            filename=filename,
            generation_costs=costs,
            action_run_id=action_run_id,
            generator_name=generator.name,
            illustrations_count=illustrations_count,
            voice_profile=voice_id,
            voice_metadata={"complexity_score": item.quality_score},
        )

        console.print(f"[green]✓[/green] Generated: {title}")
        return article

    except Exception as e:
        # Classify error - OpenAI errors are critical, other errors are warnings
        error_type = handle_openai_error(e, context="article generation", should_raise=False)
        if is_fatal(error_type):
            raise
        logger.error(f"Article generation failed: {e}", exc_info=True)
        console.print("[red]✗[/red] Article generation failed")
        return None


def generate_articles_from_enriched(
    items: list[EnrichedItem],
    max_articles: int = 3,
    force_regenerate: bool = False,
    generate_images: bool = False,
    fact_check: bool = False,
    action_run_id: str | None = None,
) -> list[GeneratedArticle]:
    """Generate blog articles from enriched items.

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
    logger.info(f"Starting article generation from {len(items)} enriched items")
    config = get_config()
    client = OpenAI(
        api_key=config.openai_api_key,
        timeout=120.0,
        max_retries=2,
    )

    if not action_run_id:
        action_run_id = os.getenv("GITHUB_RUN_ID")

    generators = get_available_generators(client)

    # Select candidates
    console.print("\n[bold blue]📋 Selecting article candidates...[/bold blue]")
    candidates = select_article_candidates(items)

    if not candidates:
        console.print("[yellow]No suitable article candidates found.[/yellow]")
        logger.warning(f"No candidates found from {len(items)} enriched items")
        return []

    logger.info(f"Found {len(candidates)} candidates after filtering")

    selected = select_diverse_candidates(candidates, max_articles, generators)
    console.print(f"[green]✓[/green] Selected {len(selected)} diverse candidates")
    logger.info(
        f"Selected {len(selected)} diverse candidates for generation (requested max: {max_articles})"
    )

    # Generate articles
    console.print(f"\n[bold blue]📝 Generating {len(selected)} articles...[/bold blue]")

    illustration_service = IllustrationService(client, config)
    articles: list[GeneratedArticle] = []
    fact_check_results: list[tuple[GeneratedArticle, FactCheckResult]] = []
    cost_tracker = CostTracker()
    adaptive_feedback = AdaptiveDedupFeedback()
    generation_errors = []
    tracker = PipelineTracker()  # Track pipeline progress

    for i, item in enumerate(selected, 1):
        console.print(f"\n[bold cyan]Article {i}/{len(selected)}[/bold cyan]")
        logger.debug(
            f"Generating article {i}/{len(selected)}: {item.original.title[:60]}"
        )

        article = generate_single_article(
            item,
            generators,
            client,
            illustration_service,
            force_regenerate,
            action_run_id,
        )

        if article:
            try:
                save_article_to_file(article, config, generate_images, client)
                articles.append(article)
                logger.info(f"Successfully generated article: {article.filename}")
                tracker.track_generation(item, article.generator_name, success=True)

                cost_tracker.record_successful_generation(
                    article.title, article.filename, article.generation_costs
                )

                if fact_check:
                    result = validate_article(article, [item])
                    fact_check_results.append((article, result))

            except Exception as e:
                logger.error(f"Failed to save article: {e}", exc_info=True)
                console.print(f"[red]✗[/red] Failed to save article: {e}")
                tracker.track_generation(
                    item, "unknown", success=False, reason=str(e)[:60]
                )
                generation_errors.append((item.original.title[:50], str(e)[:60]))
                continue
        else:
            logger.warning(
                f"Article generation returned None for: {item.original.title[:60]}"
            )
            tracker.track_generation(
                item, "unknown", success=False, reason="generation_returned_none"
            )
            generation_errors.append(
                (item.original.title[:50], "generation_returned_none")
            )

    console.print(
        f"\n[bold green]✓ Article generation complete: {len(articles)} articles created[/bold green]"
    )
    logger.info(
        f"Generation complete: {len(articles)}/{len(selected)} articles created successfully"
    )

    # Save pipeline tracking
    tracker.print_summary()
    tracker.save()

    # Print errors if any
    if generation_errors:
        console.print(
            f"\n[yellow]⚠ Generation Errors ({len(generation_errors)}):[/yellow]"
        )
        for title, error in generation_errors:
            console.print(f"  • {title}: {error}")
            logger.warning(f"Generation error for '{title}': {error}")

    # Print fact-check summary
    if fact_check and fact_check_results:
        console.print("\n[bold cyan]📋 Fact-Check Summary:[/bold cyan]")
        passed = sum(1 for _, r in fact_check_results if r.passed)
        console.print(f"  Passed: {passed}/{len(fact_check_results)}")
        logger.info(f"Fact-check: {passed}/{len(fact_check_results)} articles passed")

        failed = [(a, r) for a, r in fact_check_results if not r.passed]
        if failed:
            console.print("\n[yellow]⚠ Failed Articles:[/yellow]")
            for article, result in failed:
                console.print(f"  • {article.title[:60]}")
                console.print(f"    Confidence: {result.confidence_score:.2f}")
                if result.unreachable_sources:
                    console.print(
                        f"    Unreachable sources: {len(result.unreachable_sources)}"
                    )
                if result.broken_links:
                    console.print(f"    Broken links: {len(result.broken_links)}")

    # Print summary
    if articles:
        console.print("\n[bold cyan]📝 New Articles:[/bold cyan]")
        for article in articles:
            console.print(f"  • {article.filename}")
            console.print(f"    Title: {article.title}")
            console.print(
                f"    Words: {article.word_count}, Score: {article.sources[0].quality_score:.2f}"
            )

    cost_tracker.print_summary(days=7)
    adaptive_feedback.print_stats()

    return articles


# Python 3.14 free-threading: async variant
async def generate_articles_async(
    items: list[EnrichedItem],
    max_articles: int = 3,
    force_regenerate: bool = False,
    generate_images: bool = False,
    action_run_id: str | None = None,
) -> list[GeneratedArticle]:
    """Async article generation leveraging Python 3.14 free-threading.

    Uses ThreadPoolExecutor for true parallel execution without GIL limitations.

    Requires: Python 3.14+ with PYTHON_GIL=0 environment variable.

    Args:
        items: List of enriched items
        max_articles: Maximum number of articles to generate
        force_regenerate: If True, regenerate existing articles
        generate_images: If True, generate cover images
        action_run_id: GitHub Actions run ID for tracking

    Returns:
        List of successfully generated articles
    """
    config = get_config()
    client = OpenAI(
        api_key=config.openai_api_key,
        timeout=120.0,
        max_retries=2,
    )

    if not action_run_id:
        action_run_id = os.getenv("GITHUB_RUN_ID")

    generators = get_available_generators(client)

    console.print("\n[bold blue]📋 Selecting article candidates...[/bold blue]")
    candidates = select_article_candidates(items)

    if not candidates:
        console.print("[yellow]No suitable article candidates found.[/yellow]")
        return []

    selected = select_diverse_candidates(candidates, max_articles, generators)
    console.print(f"[green]✓[/green] Selected {len(selected)} diverse candidates")

    console.print(
        f"\n[bold blue]📝 Generating {len(selected)} articles (async)...[/bold blue]"
    )

    # Shared services (thread-safe)
    illustration_service = IllustrationService(client, config)
    cost_tracker = CostTracker()

    articles: list[GeneratedArticle] = []

    def generate_wrapper(item: EnrichedItem, index: int) -> GeneratedArticle | None:
        """Wrapper for thread execution."""
        console.print(f"\n[bold cyan]Article {index + 1}/{len(selected)}[/bold cyan]")
        return generate_single_article(
            item,
            generators,
            client,
            illustration_service,
            force_regenerate,
            action_run_id,
        )

    # Execute in thread pool (true parallelism in Python 3.14)
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor(max_workers=min(4, len(selected))) as executor:
        futures = [
            loop.run_in_executor(executor, generate_wrapper, item, i)
            for i, item in enumerate(selected)
        ]

        results = await asyncio.gather(*futures, return_exceptions=True)

    # Process results
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.error(f"Article {i + 1} generation failed: {result}")
            console.print(f"[red]✗[/red] Article {i + 1} failed: {result}")
            continue

        if result and isinstance(result, GeneratedArticle):
            articles.append(result)

            try:
                save_article_to_file(result, config, generate_images, client)
                cost_tracker.record_successful_generation(
                    result.title, result.filename, result.generation_costs
                )
            except Exception as e:
                logger.error(f"Failed to save article: {e}", exc_info=True)
                console.print(f"[red]✗[/red] Failed to save article: {e}")

    console.print(
        f"\n[bold green]✓ Article generation complete: {len(articles)} articles created[/bold green]"
    )

    if articles:
        console.print("\n[bold cyan]📝 New Articles:[/bold cyan]")
        for article in articles:
            console.print(f"  • {article.filename}")
            console.print(f"    Title: {article.title}")

    cost_tracker.print_summary(days=7)

    return articles
