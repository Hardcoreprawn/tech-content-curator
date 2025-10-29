"""Article generation orchestration.

This module orchestrates the article generation process:
1. Selects high-quality items (score >= 0.5)
2. Routes items to appropriate specialized generators
3. Generates compelling titles and slugs
4. Saves articles with proper frontmatter

The actual content generation is delegated to specialized generators
in the generators/ package.

DESIGN DECISIONS:
- Generator routing based on priority and can_handle() checks
- Use GPT-4o-mini for article generation (better at long-form content)
- Generate markdown format (easy to publish anywhere)
- Include frontmatter for static site generators
- Batch processing to avoid rate limits
- Clear attribution to original sources
- Source URL-based deduplication to prevent duplicate articles
- Source cooldown: avoid same GitHub repo within configurable days
"""

import argparse
import hashlib
import json
import os
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

import frontmatter
from openai import OpenAI
from rich.console import Console

from .config import PipelineConfig, get_config, get_content_dir, get_data_dir
from .fact_check import validate_article
from .generators.base import BaseGenerator
from .generators.general import GeneralArticleGenerator
from .generators.integrative import IntegrativeListGenerator
from .generators.specialized.self_hosted import SelfHostedGenerator
from .images import generate_featured_image
from .models import EnrichedItem, GeneratedArticle
from .utils.url_tools import normalize_url

console = Console()

# OpenAI API Pricing (as of Oct 2024)
PRICING = {
    "gpt-4o-mini": {"input": 0.150 / 1_000_000, "output": 0.600 / 1_000_000},
    "gpt-3.5-turbo": {"input": 0.500 / 1_000_000, "output": 1.500 / 1_000_000},
    "dall-e-3-hd-1792x1024": 0.080,  # HD quality wide image
    "dall-e-3-standard-1024x1024": 0.040,  # Standard quality square
}


def calculate_text_cost(
    model: str, input_tokens: int, output_tokens: int
) -> float:
    """Calculate cost for a text generation API call.
    
    Args:
        model: Model name (e.g., "gpt-4o-mini")
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens
        
    Returns:
        Cost in USD
    """
    if model not in PRICING:
        return 0.0
    
    pricing = PRICING[model]
    return (input_tokens * pricing["input"]) + (output_tokens * pricing["output"])


def calculate_image_cost(model: str = "dall-e-3-hd-1792x1024") -> float:
    """Calculate cost for an image generation API call.
    
    Args:
        model: Image model specification
        
    Returns:
        Cost in USD
    """
    return PRICING.get(model, 0.0)


def get_available_generators(client: OpenAI) -> list[BaseGenerator]:
    """Get all available generators sorted by priority.

    Args:
        client: OpenAI client instance

    Returns:
        List of generators sorted by priority (highest first)
    """
    generators = [
        SelfHostedGenerator(client),
        IntegrativeListGenerator(client),
        GeneralArticleGenerator(client),  # Fallback - always last
    ]

    # Sort by priority (highest first)
    generators.sort(key=lambda g: g.priority, reverse=True)
    return generators


def select_generator(
    item: EnrichedItem, generators: list[BaseGenerator]
) -> BaseGenerator:
    """Select the appropriate generator for an item.

    Checks generators in priority order and returns the first one that can handle the item.

    Args:
        item: The enriched item to generate content for
        generators: List of available generators (sorted by priority)

    Returns:
        The generator that should handle this item
    """
    for generator in generators:
        if generator.can_handle(item):
            return generator

    # Should never reach here since GeneralArticleGenerator can handle anything
    return generators[-1]


def select_article_candidates(
    items: list[EnrichedItem], min_quality: float = 0.5
) -> list[EnrichedItem]:
    """Select items suitable for article generation.

    This filters items based on quality score and other criteria.
    We only want to spend API credits on content that will make good articles.

    Args:
        items: List of enriched items
        min_quality: Minimum quality score (0.0-1.0)

    Returns:
        List of items suitable for article generation
    """
    candidates = []
    # Preload content directory once for existing-source checks
    content_dir = get_content_dir()

    for item in items:
        # Primary filter: quality score
        if item.quality_score < min_quality:
            continue

        # Secondary filters: content substance (allow short if it's clearly technical)
        content_len = len(item.original.content)
        content_lower = item.original.content.lower()

        # If it's a curated list/listicle, allow even if short (handled by specialized generator)
        # Use the IntegrativeListGenerator to check
        temp_gen = IntegrativeListGenerator(None)  # No client needed for can_handle
        if temp_gen.can_handle(item):
            if item.topics:
                candidates.append(item)
            continue

        # Allow shorter content if it has strong technical signals (acronyms/links)
        has_link = "http" in content_lower
        has_acronym = bool(re.search(r"\b[A-Z0-9-]{2,10}\b", item.original.content))
        if content_len < 200 and not (
            has_link or has_acronym
        ):  # Too short without signals
            continue

        if not item.topics:  # No topics identified
            continue

        # Skip if we've already published an article for this source URL
        try:
            if check_article_exists_for_source(str(item.original.url), content_dir):
                console.print(
                    f"[dim]⏭ Skipping known source:[/dim] {item.original.title[:60]}..."
                )
                continue
        except Exception:
            # If the existence check fails for any reason, fall back to allowing the item
            pass
        
        # Skip if source is in cooldown period (avoid republishing same sources too frequently)
        cooldown_days = int(os.getenv("SOURCE_COOLDOWN_DAYS", "7"))
        if is_source_in_cooldown(str(item.original.url), content_dir, cooldown_days):
            console.print(
                f"[dim]⏸ In cooldown ({cooldown_days}d):[/dim] {item.original.title[:60]}..."
            )
            continue

        candidates.append(item)

    # Sort by quality score (best first)
    candidates.sort(key=lambda x: x.quality_score, reverse=True)

    console.print(
        f"[green]✓[/green] Selected {len(candidates)} candidates from {len(items)} enriched items"
    )
    return candidates


def generate_slug_with_ai(title: str, client: OpenAI) -> str:
    """Generate SEO-friendly slug using AI.

    Uses GPT-3.5-turbo (cheap, fast) to create a good URL slug.

    Args:
        title: Article title
        client: OpenAI client

    Returns:
        URL-safe slug (lowercase, hyphens, no special chars)
    """
    try:
        prompt = f"""Generate a short, SEO-friendly URL slug for this article title.
Rules:
- Lowercase only
- Use hyphens to separate words
- Max 6 words
- No special characters
- Capture the key topic

Title: {title}

Respond with ONLY the slug, nothing else."""

        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=30,
        )

        slug = response.choices[0].message.content
        if not slug:
            raise ValueError("Empty response from AI")
        slug = slug.strip()
        # Clean up any quotes or extra characters
        slug = slug.strip("\"'").lower()
        # Ensure it's safe
        slug = "".join(c if c.isalnum() or c == "-" else "-" for c in slug)
        # Remove multiple hyphens
        while "--" in slug:
            slug = slug.replace("--", "-")
        return slug.strip("-")[:60]

    except Exception as e:
        console.print(
            f"[yellow]⚠[/yellow] AI slug generation failed, using fallback: {e}"
        )
        # Fallback: simple title-based slug
        slug = title.lower().replace(" ", "-")
        slug = "".join(c for c in slug if c.isalnum() or c == "-")
        return slug[:60]


def check_article_exists_for_source(source_url: str, content_dir: Path) -> Path | None:
    """Check if an article for this source URL already exists.

    Args:
        source_url: Original source URL to check
        content_dir: Directory containing articles

    Returns:
        Path to existing article if found, None otherwise
    """
    # Normalize incoming URL once
    normalized_input = normalize_url(source_url)

    # Check all existing markdown files for this source URL
    for filepath in content_dir.glob("*.md"):
        try:
            post = frontmatter.load(str(filepath))
            meta = post.metadata or {}
            # New format: list of sources
            sources = meta.get("sources")
            if isinstance(sources, list):
                for s in sources:
                    url = s.get("url") if isinstance(s, dict) else None
                    if url and normalize_url(str(url)) == normalized_input:
                        return filepath
            # Legacy format: single source dict
            source_meta = meta.get("source")
            if isinstance(source_meta, dict):
                url = source_meta.get("url")
                if url and normalize_url(str(url)) == normalized_input:
                    return filepath
        except Exception:
            continue
    return None


def collect_existing_source_urls(content_dir: Path) -> set[str]:
    """Collect normalized source URLs present in existing articles' frontmatter.

    Supports both legacy 'source' dict and current 'sources' list formats.
    """
    urls: set[str] = set()
    for filepath in content_dir.glob("*.md"):
        try:
            post = frontmatter.load(str(filepath))
            meta = post.metadata or {}
            # New format: list of sources
            sources = meta.get("sources")
            if isinstance(sources, list):
                for s in sources:
                    url = s.get("url") if isinstance(s, dict) else None
                    if url:
                        urls.add(normalize_url(str(url)))
            # Legacy format: single source dict
            legacy = meta.get("source")
            if isinstance(legacy, dict):
                url = legacy.get("url")
                if url:
                    urls.add(normalize_url(str(url)))
        except Exception:
            continue
    return urls


def is_source_in_cooldown(source_url: str, content_dir: Path, cooldown_days: int = 7) -> bool:
    """Check if a source URL was used recently (within cooldown period).
    
    This prevents generating multiple articles from the same source (e.g., GitHub repo)
    too frequently, ensuring content diversity.
    
    Args:
        source_url: Source URL to check
        content_dir: Directory containing articles
        cooldown_days: Number of days to wait before reusing a source
        
    Returns:
        True if source is in cooldown period (was used recently)
    """
    normalized_url = normalize_url(source_url)
    cutoff_date = datetime.now(UTC) - timedelta(days=cooldown_days)
    
    for filepath in content_dir.glob("*.md"):
        try:
            post = frontmatter.load(str(filepath))
            meta = post.metadata or {}
            
            # Check article date
            article_date_str = meta.get("date")
            if not article_date_str or not isinstance(article_date_str, str):
                continue
                
            # Parse date (format: YYYY-MM-DD)
            article_date = datetime.fromisoformat(article_date_str).replace(tzinfo=UTC)
            
            # If article is older than cooldown, skip it
            if article_date < cutoff_date:
                continue
            
            # Check if this article used our source URL
            sources = meta.get("sources", [])
            if isinstance(sources, list):
                for s in sources:
                    url = s.get("url") if isinstance(s, dict) else None
                    if url and normalize_url(str(url)) == normalized_url:
                        return True  # Found recent article with this source
                        
        except Exception:
            continue
            
    return False  # Source not used recently




def generate_article_slug(title: str, openai_api_key: str) -> tuple[str, float]:
    """Generate SEO-friendly slug from article title using gpt-4o-mini.

    Uses a cheap AI model to create readable, unique slugs.

    Args:
        title: The article title
        openai_api_key: OpenAI API key

    Returns:
        Tuple of (URL-safe slug string, cost in USD)
    """
    client = OpenAI(api_key=openai_api_key)
    
    prompt = f"""Convert this title to a short, SEO-friendly URL slug:

Rules:
- 3-6 words maximum
- Use hyphens between words
- Lowercase only
- No special characters
- Capture the key topic

Title: {title}

Respond with ONLY the slug, nothing else."""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=30,
        )

        slug = response.choices[0].message.content
        if not slug:
            raise ValueError("Empty response from AI")
        slug = slug.strip()
        # Clean up any quotes or extra characters
        slug = slug.strip("\"'").lower()
        # Ensure it's safe
        slug = "".join(c if c.isalnum() or c == "-" else "-" for c in slug)
        # Remove multiple hyphens
        while "--" in slug:
            slug = slug.replace("--", "-")
        
        # Calculate cost
        usage = response.usage
        cost = calculate_text_cost(
            "gpt-4o-mini",
            usage.prompt_tokens if usage else 0,
            usage.completion_tokens if usage else 0,
        )
        return slug.strip("-")[:60], cost

    except Exception as e:
        console.print(
            f"[yellow]⚠[/yellow] AI slug generation failed, using fallback: {e}"
        )
        # Fallback: simple title-based slug
        slug = title.lower().replace(" ", "-")
        slug = "".join(c for c in slug if c.isalnum() or c == "-")
        return slug[:60], 0.0


def generate_article_title(
    item: EnrichedItem, content: str, openai_api_key: str
) -> tuple[str, float]:
    """Generate a compelling article title using gpt-4o-mini.

    Uses gpt-4o-mini (cheap, fast, high quality) to create a catchy title.

    Args:
        item: The enriched item
        content: Generated article content
        openai_api_key: OpenAI API key

    Returns:
        Tuple of (title, cost)
    """
    client = OpenAI(api_key=openai_api_key)

    # Get first 800 chars of article for context
    article_preview = content[:800]

    prompt = f"""Create a compelling, snappy blog article title for this article.

ARTICLE PREVIEW:
{article_preview}

TOPICS: {", ".join(item.topics)}

Requirements:
- Under 60 characters (for SEO)
- Snappy and eye-catching - make people WANT to click
- Clear and descriptive - readers should know what they're getting
- NOT clickbait - be honest and direct
- Tech/professional audience appropriate
- Should accurately reflect the actual article content

Examples of good titles:
- "Why Your Database Migrations Keep Breaking"
- "The Docker Security Flaw Nobody Talks About"
- "I Built a Compiler in Rust and Here's What I Learned"
- "Stop Using Environment Variables for Secrets"

Return ONLY the title, no quotes or explanation."""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
            max_tokens=50,
        )

        response_content = response.choices[0].message.content
        if response_content is None or not response_content.strip():
            raise ValueError("Empty response from OpenAI")

        title = response_content.strip().strip("\"'")

        # Fallback if too long
        if len(title) > 60:
            # Try to truncate at word boundary
            words = title.split()
            truncated = ""
            for word in words:
                if len(truncated + " " + word) <= 57:  # Leave room for "..."
                    truncated += " " + word if truncated else word
                else:
                    break
            title = truncated + "..." if truncated != title else title[:57] + "..."

        # Calculate cost
        usage = response.usage
        cost = calculate_text_cost(
            "gpt-4o-mini",
            usage.prompt_tokens if usage else 0,
            usage.completion_tokens if usage else 0,
        )
        return title, cost

    except Exception as e:
        console.print(f"[yellow]⚠[/yellow] Title generation failed: {e}")
        # Create fallback title from topics
        if item.topics:
            return f"Understanding {item.topics[0].title()}: A Deep Dive", 0.0
        else:
            return "Tech Insights: What You Need to Know", 0.0


def create_article_metadata(item: EnrichedItem, title: str, content: str) -> dict:
    """Create frontmatter metadata for the article.

    This creates the YAML frontmatter that static site generators use.

    Args:
        item: The enriched item
        title: Article title
        content: Article content

    Returns:
        Dictionary of metadata
    """
    word_count = len(content.split())

    return {
        "title": title,
        "date": datetime.now(UTC).strftime("%Y-%m-%d"),
        "tags": item.topics[:5],  # Limit to 5 tags
        "summary": f"An in-depth look at {', '.join(item.topics[:2])} based on insights from the tech community.",
        "source": {
            "platform": item.original.source,
            "author": item.original.author,
            "url": normalize_url(str(item.original.url)),
            "collected_at": item.original.collected_at.isoformat(),
        },
        "quality_score": item.quality_score,
        "word_count": word_count,
        "reading_time": f"{max(1, round(word_count / 200))} min read",
        "cover": {
            "image": "",
            "alt": "",
        },
        "generated_at": datetime.now(UTC).isoformat(),
    }


def generate_single_article(
    item: EnrichedItem,
    config: PipelineConfig,
    generators: list[BaseGenerator],
    force_regenerate: bool = False,
) -> GeneratedArticle | None:
    """Generate a complete article from an enriched item.

    This orchestrates the full article generation process using the appropriate generator.

    Args:
        item: The enriched item to turn into an article
        config: Pipeline configuration
        generators: List of available generators
        force_regenerate: If True, delete and regenerate existing articles

    Returns:
        GeneratedArticle if successful, None if generation fails
    """
    console.print(f"[blue]Generating article:[/blue] {item.original.title[:50]}...")

    try:
        client = OpenAI(api_key=config.openai_api_key)

        # Step 1: Check if article for this source already exists
        existing_file = check_article_exists_for_source(
            str(item.original.url), get_content_dir()
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
        title, title_cost = generate_article_title(item, content, config.openai_api_key)
        costs["title_generation"] = title_cost
        console.print(f"  Title: {title}")

        # Step 4: Create metadata
        metadata = create_article_metadata(item, title, content)

        # Step 5: Generate SEO-friendly slug from the title
        slug, slug_cost = generate_article_slug(title, config.openai_api_key)
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
        )

        console.print(f"[green]✓[/green] Generated: {title}")
        return article

    except Exception as e:
        console.print(f"[red]✗[/red] Article generation failed: {e}")
        return None


def save_article_to_file(
    article: GeneratedArticle, config: PipelineConfig, generate_image: bool = False
) -> Path:
    """Save a generated article to markdown file with frontmatter.

    Args:
        article: The generated article to save
        config: Pipeline configuration for API keys
        generate_image: If True, generate a featured image using DALL-E 3

    Returns:
        Path to the saved file
    """
    content_dir = get_content_dir()
    filepath = content_dir / article.filename

    # Ensure filename uniqueness without hashes by appending a numeric suffix on collision
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
        # Simple reading time estimate (200 wpm)
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
        # Placeholder for future images; PaperMod can use this if set later
        "cover": {
            "image": "",
            "alt": "",
        },
        # Cost tracking for transparency
        "generation_costs": article.generation_costs,
    }

    # Optional: Generate featured image with DALL-E 3
    if generate_image:
        slug = filepath.stem  # Use filename stem as slug
        image_result = generate_featured_image(
            article.title, article.summary, slug, config.openai_api_key
        )
        if image_result:
            hero_path, icon_path = image_result
            metadata["cover"]["image"] = hero_path
            metadata["cover"]["alt"] = article.title
            # Store icon separately for potential use in custom layouts
            metadata["icon"] = icon_path if icon_path else ""
            # Track image generation cost
            article.generation_costs["image_generation"] = calculate_image_cost()
            article.generation_costs["icon_generation"] = 0.0  # Free (local Pillow processing)
            metadata["generation_costs"] = article.generation_costs

    # Build content with clear attribution at the top and references at the end
    primary = article.sources[0].original if article.sources else None
    attribution_block = ""
    if primary is not None:
        # Detect actual source from URL for more accurate attribution
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

    # Append references section listing all sources
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

    full_content = f"{attribution_block}{article.content}{references_block}"

    # Create frontmatter post
    post = frontmatter.Post(full_content, **metadata)

    # Save to file
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(frontmatter.dumps(post))

    console.print(f"[green]✓[/green] Saved article to {article.filename}")
    return filepath


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
) -> list[GeneratedArticle]:
    """Generate blog articles from enriched items.

    This is the main entry point for article generation.

    Args:
        items: List of enriched items
        max_articles: Maximum number of articles to generate
        force_regenerate: If True, regenerate existing articles

    Returns:
        List of successfully generated articles
    """
    config = get_config()
    client = OpenAI(api_key=config.openai_api_key)

    # Get available generators
    generators = get_available_generators(client)

    # Select candidates
    candidates = select_article_candidates(items)

    # Filter out items whose sources are already covered (unless force_regenerate)
    if not force_regenerate:
        existing_urls = collect_existing_source_urls(get_content_dir())
        before = len(candidates)
        candidates = [
            it for it in candidates if normalize_url(str(it.original.url)) not in existing_urls
        ]
        if before != len(candidates):
            console.print(
                f"[dim]Filtered {before - len(candidates)} already-covered sources before generation[/dim]"
            )

    if not candidates:
        console.print(
            "[yellow]No suitable candidates found for article generation[/yellow]"
        )
        return []

    # Choose a diverse set up to max_articles
    candidates = _select_diverse_candidates(candidates, max_articles, generators)

    console.print(f"[bold blue]Generating {len(candidates)} articles...[/bold blue]")
    if force_regenerate:
        console.print(
            "[yellow]⚠ Force regenerate mode: existing articles will be replaced[/yellow]"
        )

    articles = []
    fact_check_results = []
    for i, item in enumerate(candidates, 1):
        console.print(f"\n[dim]Progress: {i}/{len(candidates)}[/dim]")

        article = generate_single_article(item, config, generators, force_regenerate)
        if article:
            # Save to file immediately
            save_article_to_file(article, config, generate_images)
            articles.append(article)
            
            # Optional fact-checking
            if fact_check:
                result = validate_article(article, [item])
                fact_check_results.append((article, result))

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
    
    return articles


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


if __name__ == "__main__":
    """Generate articles from the most recent enriched data."""
    # Load config early so CLI defaults reflect environment (.env)
    config = get_config()

    parser = argparse.ArgumentParser(
        description="Generate blog articles from enriched content",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate new articles only (skip existing sources)
  python -m src.generate

  # Force regenerate existing articles with new generator logic
  python -m src.generate --force-regenerate

  # Generate more articles
  python -m src.generate --max-articles 5
        """,
    )
    parser.add_argument(
        "--force-regenerate",
        action="store_true",
        help="Delete and regenerate existing articles (useful for testing new generator logic)",
    )
    parser.add_argument(
        "--max-articles",
        type=int,
        default=config.articles_per_run,
        help=f"Maximum number of articles to generate (default: {config.articles_per_run})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be generated without actually generating",
    )
    parser.add_argument(
        "--generate-images",
        action="store_true",
        help="Generate featured images using DALL-E 3 (costs ~$0.04 per image)",
    )
    parser.add_argument(
        "--fact-check",
        action="store_true",
        help="Validate articles after generation (check links, sources, structure)",
    )

    args = parser.parse_args()

    data_dir = get_data_dir()

    # Find the most recent enriched file
    enriched_files = list(data_dir.glob("enriched_*.json"))
    if not enriched_files:
        console.print("[red]No enriched data files found. Run enrichment first.[/red]")
        exit(1)

    latest_file = max(enriched_files, key=lambda f: f.stat().st_mtime)
    console.print(f"[blue]Loading enriched items from {latest_file.name}...[/blue]")

    # Load and generate articles
    items = load_enriched_items(latest_file)

    if args.dry_run:
        console.print("\n[yellow]DRY RUN MODE - No articles will be generated[/yellow]")
        candidates = select_article_candidates(items)
        client = OpenAI(api_key=config.openai_api_key)
        generators = get_available_generators(client)
        selected = _select_diverse_candidates(candidates, args.max_articles, generators)

        console.print(f"\nWould generate {len(selected)} articles:")
        for i, item in enumerate(selected, 1):
            gen = select_generator(item, generators)
            existing = check_article_exists_for_source(
                str(item.original.url), get_content_dir()
            )
            status = (
                "♻ REGENERATE"
                if (existing and args.force_regenerate)
                else ("⚠ SKIP" if existing else "✓ NEW")
            )
            console.print(
                f"  {i}. [{status}] {item.original.title[:60]}... ({gen.name})"
            )
        exit(0)

    articles = generate_articles_from_enriched(
        items, args.max_articles, args.force_regenerate, args.generate_images, args.fact_check
    )

    if articles:
        # Calculate total costs
        total_cost = sum(
            sum(article.generation_costs.values()) for article in articles
        )
        
        console.print(
            f"\n[bold green]🎉 Success! Generated {len(articles)} blog articles.[/bold green]"
        )
        console.print(f"[dim]Total generation cost: ${total_cost:.4f} USD[/dim]")
        console.print("[dim]Articles saved to content/ directory[/dim]")
    else:
        console.print("[red]No articles were generated.[/red]")
