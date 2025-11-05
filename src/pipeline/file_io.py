"""File operations for article generation pipeline.

Handles saving and loading of generated articles:
- Save articles with frontmatter to markdown files
- Load enriched items from JSON
- Handle filename conflicts
- Attach cover images and metadata
"""

import json
from pathlib import Path

import frontmatter
from openai import OpenAI
from rich.console import Console

from ..citations import CitationExtractor, CitationFormatter, CitationResolver
from ..citations.cache import CitationCache
from ..citations.resolver import ResolvedCitation
from ..config import PipelineConfig, get_content_dir
from ..images import CoverImageSelector, select_or_create_cover_image
from ..models import EnrichedItem, GeneratedArticle
from ..utils.file_io import (
    atomic_write_text,
    format_generation_costs,
)
from ..utils.logging import get_logger
from ..utils.sanitization import safe_filename, validate_path
from ..utils.url_tools import normalize_url

logger = get_logger(__name__)
console = Console()


def save_article_to_file(
    article: GeneratedArticle,
    config: PipelineConfig,
    generate_image: bool = False,
    client: OpenAI | None = None,
) -> Path:
    """Save a generated article to markdown file with frontmatter.

    Logs file creation, metadata setup, and citation processing.
    Validates and sanitizes filenames to prevent directory traversal.

    Args:
        article: The generated article to save
        config: Pipeline configuration for API keys
        generate_image: If True, generate a featured image using DALL-E 3
        client: OpenAI client for image selection (required if generate_image is True)

    Returns:
        Path to the saved file

    Raises:
        ValueError: If filename is invalid or attempts directory traversal
    """
    logger.debug(f"Saving article: {article.title} (filename: {article.filename})")
    content_dir = get_content_dir()

    # Validate and sanitize filename
    try:
        safe_name = safe_filename(article.filename, max_length=100)
        filepath = content_dir / safe_name
        # Validate that path stays within content directory
        validate_path(filepath, base_dir=content_dir)
    except ValueError as e:
        logger.error(f"Invalid filename '{article.filename}': {e}")
        raise ValueError(f"Invalid filename for article: {e}") from e

    # Ensure filename uniqueness
    if filepath.exists():
        stem = filepath.stem
        suffix_num = 2
        while True:
            candidate = content_dir / f"{stem}-{suffix_num}.md"
            try:
                validate_path(candidate, base_dir=content_dir)
            except ValueError as e:
                logger.error(f"Generated candidate path escapes content dir: {e}")
                raise ValueError(f"Cannot create unique filename: {e}") from e

            if not candidate.exists():
                console.print(
                    f"[yellow]⚠ Filename exists, saving as {candidate.name}[/yellow]"
                )
                article.filename = candidate.name
                filepath = candidate
                break
            suffix_num += 1

    # Create frontmatter metadata
    metadata = {
        "title": article.title,
        "date": article.generated_at.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "tags": article.tags,
        "summary": article.summary,
        "word_count": article.word_count,
        "reading_time": f"{max(1, round(article.word_count / 200))} min read",
        "sources": [
            {
                "platform": source.original.source,
                "author": source.original.author,
                "url": normalize_url(str(source.original.url)),
                "quality_score": source.quality_score,
            }
            for source in article.sources
        ],
        "cover": {"image": "", "alt": ""},
        "generation_costs": format_generation_costs(article.generation_costs),
        "action_run_id": article.action_run_id,
        "generator": article.generator_name,
        "illustrations_count": article.illustrations_count,
    }

    # Optional: Attach cover image
    if generate_image:
        slug = filepath.stem
        hero_path = icon_path = None
        try:
            # Try multi-source image selection first
            if client and (config.unsplash_api_key or config.pexels_api_key):
                try:
                    selector = CoverImageSelector(client, config)
                    cover_image = selector.select(article.title, article.tags)
                    hero_path = cover_image.url
                    icon_path = cover_image.url
                    article.generation_costs["image_generation"] = cover_image.cost
                    console.print(
                        f"[green]✓[/green] Selected {cover_image.source} image "
                        f"(cost: ${cover_image.cost:.4f})"
                    )
                except (ValueError, KeyError, AttributeError) as e:
                    logger.warning(
                        f"Multi-source image selection failed for article '{article.title}': {e}",
                        exc_info=True,
                    )
                    console.print(
                        f"[yellow]⚠ Multi-source image selection failed: {e}[/yellow]"
                    )

            # Fallback: Reuse from library
            if not hero_path and config.image_strategy in (
                "reuse",
                "reuse_then_generate",
            ):
                hero_path, icon_path = select_or_create_cover_image(
                    article.tags, slug, config.hugo_base_url
                )
                article.generation_costs["image_generation"] = 0.0
        except (OSError, ValueError, KeyError) as ie:
            logger.error(
                f"Image attachment failed for article '{article.title}': {ie}",
                exc_info=True,
            )
            console.print(f"[yellow]⚠[/yellow] Image attach failed: {ie}")

        if hero_path:
            metadata["cover"]["image"] = hero_path
            metadata["cover"]["alt"] = article.title
            metadata["icon"] = icon_path or ""

    # Build content with attribution and references
    primary = article.sources[0].original if article.sources else None
    attribution_block = ""
    if primary is not None:
        url_str = str(primary.url).lower()
        actual_source = primary.source
        if "github.com" in url_str:
            actual_source = "GitHub"
        elif "arxiv.org" in url_str:
            actual_source = "arXiv"

        attribution_block = (
            f"> **Attribution:** This article was based on content by "
            f"**@{primary.author}** on **{actual_source}**.  \n"
            f"> Original: {normalize_url(str(primary.url))}\n\n"
        )

    # Apply citation resolution if enabled (must happen BEFORE building references)
    article_content = article.content
    citation_bibliography: list[str] = []
    if config.enable_citations:
        try:
            extractor = CitationExtractor()
            resolver = CitationResolver()
            formatter = CitationFormatter()
            cache = CitationCache()

            citations = extractor.extract(article_content)
            if citations:
                # Resolve each citation individually with cache checking
                formatted_citations = []
                for citation in citations:
                    # Check cache first
                    cached_entry = cache.get(citation.authors, citation.year)
                    if cached_entry:
                        # Convert cached dict to ResolvedCitation
                        cached = ResolvedCitation(
                            doi=cached_entry.get("doi"),
                            arxiv_id=cached_entry.get("arxiv_id"),
                            pmid=cached_entry.get("pmid"),
                            url=cached_entry.get("url"),
                            confidence=cached_entry.get("confidence", 0.0),
                            source_uri=cached_entry.get("url"),  # Use URL as source_uri
                        )
                        formatted = formatter.format(citation, cached)
                    else:
                        # Resolve and cache
                        result = resolver.resolve(citation.authors, citation.year)
                        cache.put(
                            citation.authors,
                            citation.year,
                            doi=result.doi,
                            url=result.url,
                        )
                        formatted = formatter.format(citation, result)
                    formatted_citations.append(formatted)

                # Apply all formatted citations to the article content
                article_content = formatter.apply_to_text(
                    article_content, formatted_citations
                )

                # Build bibliography from resolved citations
                citation_bibliography = formatter.build_bibliography(
                    formatted_citations
                )
        except Exception as e:
            logger.warning(
                f"Citation processing failed for article '{article.title}': {e}",
                exc_info=True,
            )
            console.print(f"[yellow]⚠ Citation processing failed: {e}[/yellow]")

    # Append references (now citation_bibliography is defined)
    references_block = ""
    if article.sources or citation_bibliography:
        lines = ["\n\n## References\n"]

        # Add source references first
        for src in article.sources:
            o = src.original
            url_str = str(o.url).lower()
            actual_source = o.source
            if "github.com" in url_str:
                actual_source = "GitHub"
            elif "arxiv.org" in url_str:
                actual_source = "arXiv"
            lines.append(
                f"- [{o.title}]({normalize_url(str(o.url))}) — @{o.author} on {actual_source}"
            )

        # Add resolved citations bibliography
        if citation_bibliography:
            if article.sources:
                # Add spacing before citations section if we already have sources
                lines.append("")
            lines.extend(citation_bibliography)

        references_block = "\n".join(lines) + "\n"

    # Combine everything
    full_content = attribution_block + article_content + references_block

    # Write file atomically to prevent corruption
    post = frontmatter.Post(full_content, **metadata)
    article_text = frontmatter.dumps(post)
    atomic_write_text(filepath, article_text)

    logger.info(
        f"Successfully saved article: {article.filename} ({len(full_content)} bytes)"
    )
    console.print(f"[green]✓[/green] Saved article to {article.filename}")
    return filepath


def load_enriched_items(filepath: Path) -> list[EnrichedItem]:
    """Load enriched items from JSON file.

    Args:
        filepath: Path to enriched items file

    Returns:
        List of EnrichedItem objects
    """
    logger.debug(f"Loading enriched items from: {filepath}")
    with open(filepath, encoding="utf-8") as f:
        data = json.load(f)

    items = []
    for item_data in data["items"]:
        try:
            item = EnrichedItem(**item_data)
            items.append(item)
        except (ValueError, TypeError, KeyError) as e:
            logger.warning(
                f"Failed to load enriched item: {e}, item data: {item_data}",
                exc_info=True,
            )
            console.print(f"[yellow]⚠[/yellow] Failed to load enriched item: {e}")
            continue

    console.print(
        f"[green]✓[/green] Loaded {len(items)} enriched items from {filepath.name}"
    )
    return items
