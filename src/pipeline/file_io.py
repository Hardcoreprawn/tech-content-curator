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
from ..config import PipelineConfig, get_content_dir
from ..images import CoverImageSelector, select_or_create_cover_image
from ..models import EnrichedItem, GeneratedArticle
from ..utils.url_tools import normalize_url

console = Console()


def save_article_to_file(
    article: GeneratedArticle,
    config: PipelineConfig,
    generate_image: bool = False,
    client: OpenAI | None = None,
) -> Path:
    """Save a generated article to markdown file with frontmatter.

    Args:
        article: The generated article to save
        config: Pipeline configuration for API keys
        generate_image: If True, generate a featured image using DALL-E 3
        client: OpenAI client for image selection (required if generate_image is True)

    Returns:
        Path to the saved file
    """
    content_dir = get_content_dir()
    filepath = content_dir / article.filename

    # Ensure filename uniqueness
    if filepath.exists():
        stem = filepath.stem
        suffix_num = 2
        while True:
            candidate = content_dir / f"{stem}-{suffix_num}.md"
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
        "date": article.generated_at.strftime("%Y-%m-%d"),
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
        "generation_costs": article.generation_costs,
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
                except Exception as e:
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
        except Exception as ie:
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

    # Append references
    references_block = ""
    if article.sources:
        lines = ["\n\n## References\n"]
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
        references_block = "\n".join(lines) + "\n"

    # Apply citation resolution if enabled
    article_content = article.content
    if config.enable_citations:
        try:
            extractor = CitationExtractor()
            resolver = CitationResolver()
            formatter = CitationFormatter()
            cache = CitationCache()

            citations = extractor.extract(article_content)
            if citations:
                # Resolve each citation individually with cache checking
                resolved = []
                for citation in citations:
                    # Check cache first
                    cached = cache.get(citation.authors, citation.year)
                    if cached:
                        resolved.append(cached)
                    else:
                        # Resolve and cache
                        result = resolver.resolve(citation.authors, citation.year)
                        cache.put(citation.authors, citation.year, result)
                        resolved.append(result)
                
                article_content = formatter.format_inline(article_content, resolved)
                refs_section = formatter.format_references(resolved)
                if refs_section:
                    references_block = refs_section + "\n" + references_block
        except Exception as e:
            console.print(f"[yellow]⚠ Citation processing failed: {e}[/yellow]")

    # Combine everything
    full_content = attribution_block + article_content + references_block

    # Write file
    post = frontmatter.Post(full_content, **metadata)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(frontmatter.dumps(post))

    console.print(f"[green]✓[/green] Saved article to {article.filename}")
    return filepath


def load_enriched_items(filepath: Path) -> list[EnrichedItem]:
    """Load enriched items from JSON file.

    Args:
        filepath: Path to enriched items file

    Returns:
        List of EnrichedItem objects
    """
    with open(filepath, encoding="utf-8") as f:
        data = json.load(f)

    items = []
    for item_data in data["items"]:
        try:
            item = EnrichedItem(**item_data)
            items.append(item)
        except Exception as e:
            console.print(f"[yellow]⚠[/yellow] Failed to load enriched item: {e}")
            continue

    console.print(
        f"[green]✓[/green] Loaded {len(items)} enriched items from {filepath.name}"
    )
    return items
