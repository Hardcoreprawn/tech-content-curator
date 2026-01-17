"""File operations for article generation pipeline.

Handles saving and loading of generated articles:
- Save articles with frontmatter to markdown files
- Load enriched items from JSON
- Handle filename conflicts
- Attach cover images and metadata
"""

import json
import re
from pathlib import Path
from urllib.parse import urlparse

import frontmatter
from openai import OpenAI
from rich.console import Console

from ..citations import CitationExtractor, CitationFormatter, CitationResolver
from ..citations.cache import CitationCache
from ..citations.resolver import ResolvedCitation
from ..config import PipelineConfig, get_content_dir
from ..images import CoverImageSelector, select_or_create_cover_image
from ..images.downloader import download_and_persist
from ..models import EnrichedItem, GeneratedArticle
from ..utils.costs import append_generation_cost
from ..utils.file_io import (
    atomic_write_text,
    format_generation_costs,
)
from ..utils.logging import get_logger
from ..utils.sanitization import safe_filename, validate_path
from ..utils.url_tools import normalize_url
from .deduplication import find_article_by_slug

logger = get_logger(__name__)
console = Console()


def save_article_to_file(
    article: GeneratedArticle,
    config: PipelineConfig,
    generate_image: bool = False,
    client: OpenAI | None = None,
    update_existing: bool = True,
) -> Path:
    """Save a generated article to markdown file with frontmatter.

    Logs file creation, metadata setup, and citation processing.
    Validates and sanitizes filenames to prevent directory traversal.

    If update_existing=True (default), checks if an article with the same slug
    already exists and updates it instead of creating a new file. This preserves
    URLs and prevents 404s.

    Args:
        article: The generated article to save
        config: Pipeline configuration for API keys
        generate_image: If True, generate a featured image using DALL-E 3
        client: OpenAI client for image selection (required if generate_image is True)
        update_existing: If True, update existing article with same slug instead of creating new file

    Returns:
        Path to the saved file

    Raises:
        ValueError: If filename is invalid or attempts directory traversal
    """
    logger.debug(f"Saving article: {article.title} (filename: {article.filename})")
    content_dir = get_content_dir()

    # Extract slug from filename (remove date prefix and .md extension)
    # Expected format: YYYY-MM-DD-slug.md
    filename_parts = article.filename.rsplit(".", 1)[0]  # Remove .md
    parts = filename_parts.split("-", 3)  # Split on first 3 hyphens
    if len(parts) == 4:  # Has date prefix
        slug = parts[3]  # Everything after YYYY-MM-DD-
    else:
        slug = filename_parts  # No date prefix, use as-is

    # Check if article with this slug already exists
    existing_article = None
    if update_existing:
        existing_article = find_article_by_slug(slug, content_dir)

    if existing_article:
        logger.info(f"Updating existing article: {existing_article.name}")
        console.print(
            f"[cyan]🔄 Updating existing article:[/cyan] {existing_article.name}"
        )
        filepath = existing_article

        # Load existing metadata to preserve some fields
        try:
            existing_post = frontmatter.load(str(existing_article))
            original_date = existing_post.metadata.get("date")
            if original_date:
                logger.debug(f"Preserving original publish date: {original_date}")
        except (OSError, ValueError) as e:
            logger.warning(
                f"Could not load existing article metadata: {e}", exc_info=True
            )
            original_date = None
    else:
        logger.debug(f"Creating new article: {article.filename}")
        original_date = None

        # Validate and sanitize filename for NEW articles only
        try:
            safe_name = safe_filename(article.filename, max_length=100)
            filepath = content_dir / safe_name
            # Validate that path stays within content directory
            validate_path(filepath, base_dir=content_dir)
        except ValueError as e:
            logger.error(f"Invalid filename '{article.filename}': {e}")
            raise ValueError(f"Invalid filename for article: {e}") from e

        # Ensure filename uniqueness for NEW articles only
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
        "date": original_date or article.generated_at.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "tags": article.tags,
        "summary": article.summary,
        "word_count": article.word_count,
        "reading_time": f"{max(1, round(article.word_count / 200))} min read",
    }

    # Add last_updated timestamp if updating existing article
    if existing_article:
        metadata["last_updated"] = article.generated_at.strftime("%Y-%m-%dT%H:%M:%S%z")
        logger.debug("Added last_updated timestamp for article update")

    metadata.update(
        {
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
            "generation_costs": format_generation_costs(dict(article.generation_costs)),
            "action_run_id": article.action_run_id,
            "generator": article.generator_name,
            "illustrations_count": article.illustrations_count,
        }
    )

    artifact_failures: list[str] = []

    # Add quality metrics if available (Phase 2 - Model comparison)
    if article.quality_score is not None:
        metadata["article_quality"] = {
            "overall_score": round(article.quality_score, 1),
            "passed_threshold": article.quality_passed,
        }

        # Add dimension scores if available
        if article.quality_dimensions:
            dimensions = {}
            for k, v in article.quality_dimensions.items():
                if isinstance(v, (int, float)):
                    dimensions[k] = round(v, 1)
            if dimensions:
                metadata["article_quality"]["dimensions"] = dimensions

    # Add model configuration for tracking (Phase 2)
    if config:
        metadata["models_used"] = {
            "content": config.content_model,
            "title": config.title_model,
            "enrichment": config.enrichment_model,
        }

    # Optional: Attach cover image
    if generate_image:
        slug = filepath.stem
        hero_path = icon_path = None
        image_attribution = None  # Store attribution info
        try:
            # Try multi-source image selection first
            if client and (config.unsplash_api_key or config.pexels_api_key):
                try:
                    selector = CoverImageSelector(client, config)
                    cover_image = selector.select(
                        article.title,
                        article.tags,
                        article.content,
                        article_id=slug,
                        generation_costs=article.generation_costs,
                    )
                    hero_path = cover_image.url
                    icon_path = cover_image.url
                    image_attribution = cover_image  # Store for attribution
                    # Append image cost for itemized billing
                    append_generation_cost(
                        article.generation_costs, "image_generation", cover_image.cost
                    )
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
                    artifact_failures.append("image_selection_failed")

                    # If the selected cover_image is an external URL, download and persist locally
                    if hero_path and hero_path.startswith("http"):
                        try:
                            meta = {
                                "photographer": getattr(
                                    image_attribution, "photographer_name", None
                                ),
                                "photographer_url": getattr(
                                    image_attribution, "photographer_url", None
                                ),
                                "source": getattr(image_attribution, "source", None),
                            }
                            hero_path_local, icon_path_local = download_and_persist(
                                hero_path, slug, meta=meta, base_url=""
                            )
                            hero_path = hero_path_local
                            icon_path = icon_path_local
                            console.print(
                                f"[dim]Downloaded image and saved as {hero_path}[/dim]"
                            )
                        except (OSError, ValueError, KeyError, AttributeError) as e:
                            logger.warning(
                                f"Failed to persist external image: {type(e).__name__}: {e}",
                                exc_info=True,
                            )
                            console.print(
                                f"[yellow]⚠ Failed to persist image: {e}[/yellow]"
                            )
                            artifact_failures.append("image_persist_failed")
                            hero_path = None
                            icon_path = None

            # Fallback: Reuse from library
            if not hero_path and config.image_strategy in (
                "reuse",
                "reuse_then_generate",
            ):
                hero_path, icon_path = select_or_create_cover_image(
                    article.tags, slug, config.hugo_base_url
                )
                # Append zero cost for reused image
                append_generation_cost(
                    article.generation_costs, "image_generation", 0.0
                )

            # Normalize: persist any external URL so frontmatter stores local Hugo paths.
            if hero_path and str(hero_path).startswith("http"):
                try:
                    meta = {}
                    if image_attribution is not None:
                        meta = {
                            "photographer": getattr(
                                image_attribution, "photographer_name", None
                            ),
                            "photographer_url": getattr(
                                image_attribution, "photographer_url", None
                            ),
                            "source": getattr(image_attribution, "source", None),
                        }
                    hero_path_local, icon_path_local = download_and_persist(
                        str(hero_path), slug, meta=meta, base_url=""
                    )
                    hero_path = hero_path_local
                    icon_path = icon_path_local
                    console.print(
                        f"[dim]Downloaded image and saved as {hero_path}[/dim]"
                    )
                except (OSError, ValueError, KeyError, AttributeError) as e:
                    logger.warning(
                        f"Failed to persist external cover image: {type(e).__name__}: {e}",
                        exc_info=True,
                    )
                    console.print(
                        f"[yellow]⚠ Failed to persist cover image: {e}[/yellow]"
                    )
                    artifact_failures.append("image_persist_failed")
                    hero_path = None
                    icon_path = None
        except (OSError, ValueError, KeyError) as ie:
            logger.error(
                f"Image attachment failed for article '{article.title}': {ie}",
                exc_info=True,
            )
            console.print(f"[yellow]⚠[/yellow] Image attach failed: {ie}")
            artifact_failures.append("image_attach_failed")

        if hero_path:
            metadata["cover"]["image"] = hero_path
            metadata["cover"]["alt"] = article.title
            metadata["icon"] = icon_path or ""
            # Add image attribution if available
            if image_attribution and image_attribution.photographer_name:
                metadata["cover"]["photographer"] = image_attribution.photographer_name
                if image_attribution.photographer_url:
                    metadata["cover"]["photographer_url"] = (
                        image_attribution.photographer_url
                    )
                metadata["cover"]["image_source"] = image_attribution.source

    # Non-blocking fallback: ensure a local cover image exists for sustainability.
    if not metadata["cover"]["image"]:
        if config.image_strategy in ("reuse", "reuse_then_generate"):
            slug = filepath.stem
            hero_path, icon_path = select_or_create_cover_image(
                article.tags, slug, config.hugo_base_url
            )
            metadata["cover"]["image"] = hero_path
            metadata["cover"]["alt"] = article.title
            metadata["icon"] = icon_path or ""
            append_generation_cost(article.generation_costs, "image_generation", 0.0)
            artifact_failures.append("image_missing")
            console.print(
                "[yellow]⚠ Cover image missing; applied reusable fallback[/yellow]"
            )

    # Social preview images: mirror cover image when available.
    if metadata["cover"]["image"]:
        metadata["images"] = [metadata["cover"]["image"]]

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
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as e:
            logger.warning(
                f"Citation processing failed for article '{article.title}': {e}",
                exc_info=True,
            )
            console.print(f"[yellow]⚠ Citation processing failed: {e}[/yellow]")

    # Append references (now citation_bibliography is defined)
    references_block = ""
    if article.sources or citation_bibliography:
        # Collect inline URL citations from the article body
        inline_url_pattern = r"\[[^\]]+\]\((https?://[^)]+)\)"
        inline_urls: list[str] = []
        seen_inline: set[str] = set()
        for match in re.finditer(inline_url_pattern, article_content):
            url = match.group(1)
            if url not in seen_inline:
                inline_urls.append(url)
                seen_inline.add(url)

        ref_entries: list[str] = []
        source_urls: set[str] = set()
        for src in article.sources:
            o = src.original
            url_str = str(o.url).lower()
            normalized = normalize_url(str(o.url))
            source_urls.add(normalized)
            actual_source = o.source
            if "github.com" in url_str:
                actual_source = "GitHub"
            elif "arxiv.org" in url_str:
                actual_source = "arXiv"
            ref_entries.append(
                f"- [{o.title}]({normalized}) — @{o.author} on {actual_source}"
            )

        bibliography_urls: set[str] = set()
        if citation_bibliography:
            bibliography_urls = set(
                re.findall(r"https?://[^)\s]+", "\n".join(citation_bibliography))
            )

        for url in inline_urls:
            normalized = normalize_url(url)
            if normalized in source_urls or normalized in bibliography_urls:
                continue
            domain = urlparse(normalized).netloc or normalized
            ref_entries.append(f"- [{domain}]({normalized})")

        if citation_bibliography:
            ref_entries.extend(citation_bibliography)

        # Non-blocking audit: detect references without URLs
        if any("http" not in line for line in ref_entries):
            artifact_failures.append("references_missing_links")
            logger.warning(
                "References contain items without URLs",
                extra={
                    "phase": "publish",
                    "event": "references_missing_links",
                    "article": article.title,
                },
            )

        # Enforce: keep only URL-bearing references, drop section if none remain
        url_entries = [line for line in ref_entries if "http" in line]
        if url_entries:
            references_block = "\n".join(["\n\n## References\n", *url_entries]) + "\n"

    if artifact_failures:
        metadata["artifact_failures"] = sorted(set(artifact_failures))

    # Combine everything
    full_content = attribution_block + article_content + references_block

    # Update generation_costs in metadata after all costs have been added
    # (image costs are added during image selection above)
    # Ensure we pass a plain dict to formatting util (Pydantic field may be a model-backed mapping)
    metadata["generation_costs"] = format_generation_costs(
        dict(article.generation_costs)
    )

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
                f"Failed to load enriched item: {type(e).__name__} - {e}, item data: {item_data}",
                exc_info=True,
            )
            console.print(f"[yellow]⚠[/yellow] Failed to load enriched item: {e}")
            continue

    console.print(
        f"[green]✓[/green] Loaded {len(items)} enriched items from {filepath.name}"
    )
    return items
