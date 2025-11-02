"""Pipeline orchestration for article generation.

This module coordinates the full article generation pipeline, from candidate
selection through content generation, title creation, and file saving.
"""

import os
from datetime import UTC, datetime
from pathlib import Path

from openai import OpenAI
from rich.console import Console

from ..config import PipelineConfig, get_config, get_content_dir
from ..costs import CostTracker
from ..deduplication.adaptive_dedup import AdaptiveDedupFeedback
from ..enrichment.fact_check import validate_article
from ..generators.base import BaseGenerator
from ..models import EnrichedItem, GeneratedArticle
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

        # Step 2: Select appropriate generator and generate content
        generator = select_generator(item, generators)
        console.print(f"  Using: {generator.name}")
        console.print(f"  [dim]Calling OpenAI API for content generation...[/dim]")
        content, content_input_tokens, content_output_tokens = (
            generator.generate_content(item)
        )
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

        # Step 6.5: Generate and inject illustrations (Phase 4 - Multi-Format AI Generation)
        from ..illustrations.accessibility import AccessibilityChecker
        from ..illustrations.ai_ascii_generator import AIAsciiGenerator
        from ..illustrations.ai_mermaid_generator import AIMermaidGenerator
        from ..illustrations.ai_svg_generator import AISvgGenerator
        from ..illustrations.detector import detect_concepts
        from ..illustrations.generator_analyzer import should_add_illustrations
        from ..illustrations.placement import PlacementAnalyzer

        # Format selection mapping: routes concepts to best format(s)
        CONCEPT_TO_FORMAT = {
            "network_topology": [
                "ascii",
                "mermaid",
            ],  # ASCII for clarity, Mermaid for flow
            "system_architecture": ["svg", "mermaid"],  # SVG for visual complexity
            "data_flow": [
                "mermaid",
                "ascii",
            ],  # Mermaid primary, ASCII tables as fallback
            "scientific_process": [
                "svg",
                "mermaid",
            ],  # SVG for methodology, Mermaid for sequence
            "comparison": ["ascii"],  # ASCII tables are perfect for comparisons
            "algorithm": ["mermaid"],  # Mermaid flowcharts ideal for algorithms
        }

        illustrations_count = 0
        injected_content = content
        if config.enable_illustrations:
            if should_add_illustrations(generator.name, content):
                try:
                    # Step 6.5a: Detect illustration concepts in content
                    concepts_detected = detect_concepts(content)
                    concept_names = (
                        [c.name for c in concepts_detected] if concepts_detected else []
                    )

                    if concept_names:
                        # Step 6.5b: Parse sections
                        parser = PlacementAnalyzer()
                        sections = parser.parse_structure(content)

                        # Filter suitable sections (>75 words, no existing visuals)
                        suitable_sections = [
                            (idx, sec)
                            for idx, sec in enumerate(sections)
                            if sec.word_count >= 75 and not sec.has_visuals
                        ]

                        console.print(
                            f"  [dim]Concepts: {concept_names}, Sections: {len(suitable_sections)}/{len(sections)}[/dim]"
                        )

                        if suitable_sections:
                            # Step 6.5c: AI-score concept-section pairs
                            scores = []
                            for concept in concept_names:
                                for sec_idx, (_, section) in enumerate(
                                    suitable_sections
                                ):
                                    try:
                                        # Rate relevance: 0-1
                                        prompt = f'Rate "{concept}" in "{section.title}" ({section.content[:150]}...). Reply: single number 0-1'
                                        resp = client.chat.completions.create(
                                            model="gpt-3.5-turbo",
                                            messages=[
                                                {"role": "user", "content": prompt}
                                            ],
                                            temperature=0.1,
                                            max_tokens=5,
                                        )
                                        score = float(
                                            resp.choices[0].message.content.strip()
                                        )
                                        if score > 0.3:
                                            scores.append(
                                                {
                                                    "concept": concept,
                                                    "section": section,
                                                    "score": score,
                                                }
                                            )
                                    except:
                                        pass

                            # Top 3 by score
                            scores.sort(key=lambda x: x["score"], reverse=True)
                            top_matches = scores[:3]

                            console.print(
                                f"  [dim]Selected top {len(top_matches)} concept-section pairs[/dim]"
                            )

                            # Step 6.5d: Generate diagrams
                            injected_content = content
                            illustrations_added = 0
                            illustration_costs = {}
                            format_distribution = {}

                            for match in top_matches:
                                try:
                                    concept = match["concept"]
                                    section = match["section"]

                                    # Select format
                                    available_formats = CONCEPT_TO_FORMAT.get(
                                        concept, ["mermaid"]
                                    )
                                    selected_format = available_formats[0]

                                    # Instantiate generator
                                    if selected_format == "ascii":
                                        ai_generator = AIAsciiGenerator(client)
                                    elif selected_format == "svg":
                                        ai_generator = AISvgGenerator(client)
                                    else:
                                        ai_generator = AIMermaidGenerator(client)

                                    # Generate diagram
                                    diagram = ai_generator.generate_for_section(
                                        section_title=section.title,
                                        section_content=section.content,
                                        concept_type=concept,
                                    )

                                    if diagram:
                                        # Format
                                        if selected_format == "ascii":
                                            diagram_markdown = (
                                                f"```\n{diagram.content}\n```"
                                            )
                                        elif selected_format == "svg":
                                            diagram_markdown = f"<figure>\n{diagram.content}\n<figcaption>{diagram.alt_text}</figcaption>\n</figure>"
                                        else:
                                            diagram_markdown = (
                                                f"```mermaid\n{diagram.content}\n```"
                                            )

                                        # Inject
                                        accessible_block = f"<!-- {selected_format.upper()}: {diagram.alt_text} -->\n{diagram_markdown}"
                                        injected_content = injected_content.replace(
                                            f"## {section.title}",
                                            f"## {section.title}\n\n{accessible_block}",
                                            1,
                                        )

                                        illustrations_added += 1
                                        illustration_costs[
                                            f"diagram_{illustrations_added}"
                                        ] = diagram.total_cost
                                        format_distribution[selected_format] = (
                                            format_distribution.get(selected_format, 0)
                                            + 1
                                        )
                                except Exception as e:
                                    console.print(
                                        f"  [yellow]⚠ Diagram skipped: {str(e)[:50]}[/yellow]"
                                    )

                            illustrations_count = illustrations_added
                            if illustrations_count > 0:
                                console.print(
                                    f"  [cyan]✓ {illustrations_count} diagram(s) generated[/cyan]"
                                )
                                if format_distribution:
                                    fmt_str = ", ".join(
                                        [
                                            f"{k}:{v}"
                                            for k, v in sorted(
                                                format_distribution.items()
                                            )
                                        ]
                                    )
                                    console.print(f"  [dim]  Formats: {fmt_str}[/dim]")
                                if illustration_costs:
                                    total = sum(illustration_costs.values())
                                    costs["illustrations"] = total
                                    console.print(f"  [dim]  Cost: ${total:.6f}[/dim]")

                except Exception as e:
                    console.print(f"  [yellow]⚠ Illustration error: {e}[/yellow]")
            else:
                console.print(
                    f"  [dim]Skipping illustrations - no benefit for this content[/dim]"
                )

        # Step 7: Create GeneratedArticle with cost tracking and generator info
        article = GeneratedArticle(
            title=title,
            content=injected_content,
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
                    console.print(
                        f"    Unreachable sources: {len(result.unreachable_sources)}"
                    )
                if result.broken_links:
                    console.print(f"    Broken links: {len(result.broken_links)}")

    # Print compact summary of new files
    if articles:
        console.print("\n[bold cyan]📝 New Articles:[/bold cyan]")
        for article in articles:
            console.print(f"  • {article.filename}")
            console.print(f"    Title: {article.title}")
            console.print(
                f"    Words: {article.word_count}, Score: {article.sources[0].quality_score:.2f}"
            )

    # Print cost summary and adaptive dedup stats
    cost_tracker.print_summary(days=7)  # Last 7 days
    adaptive_feedback.print_stats()

    return articles
