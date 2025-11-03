"""Article generation orchestration.

This module provides the CLI interface for article generation.
The actual implementation is in src.pipeline.orchestrator.

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
- Python 3.14+ free-threading: async generation with PYTHON_GIL=0 for 3-4x speedup
"""

import argparse
import asyncio
import os

from openai import OpenAI
from rich.console import Console

from .config import get_config, get_content_dir, get_data_dir
from .pipeline import (
    check_article_exists_for_source,
    generate_articles_from_enriched,
    get_available_generators,
    load_enriched_items,
    select_article_candidates,
    select_generator,
)
from .pipeline.diversity_selector import (
    select_diverse_candidates as _select_diverse_candidates,
)
from .pipeline.orchestrator import generate_articles_async

console = Console()


def _supports_async() -> bool:
    """Check if async generation is available and beneficial.

    Returns True only if:
    1. Python 3.14+
    2. PYTHON_GIL environment variable is set to '0'
    3. Python build actually supports --disable-gil (will fail at runtime if not)

    Note: If PYTHON_GIL=0 is set but Python wasn't compiled with --disable-gil,
    it will fail with "Fatal Python error: config_read_gil: Disabling the GIL is not supported"
    In that case, the environment variable should be removed and this will return False.
    """
    # Only enable if explicitly set to '0'
    # This is conservative - we check the env var but Python will validate at runtime
    # Note: Python 3.14+ is now required (version check removed as outdated)

    # Only enable if explicitly set to '0'
    # This is conservative - we check the env var but Python will validate at runtime
    return os.getenv("PYTHON_GIL") == "0"


async def _generate_with_async(
    items: list,
    max_articles: int,
    force_regenerate: bool,
    generate_images: bool,
    fact_check: bool,
    github_run_id: str | None,
) -> list:
    """Generate articles asynchronously using free-threading."""
    console.print(
        "[bold cyan]⚡ Python 3.14 free-threading enabled - generating in parallel![/bold cyan]"
    )
    return await generate_articles_async(
        items,
        max_articles,
        force_regenerate,
        generate_images,
        github_run_id,
    )


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
        help="Generate featured images using DALL-E 3 (costs ~.04 per image)",
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
        client = OpenAI(
            api_key=config.openai_api_key,
            timeout=120.0,  # 120 second timeout for API calls
            max_retries=2,  # Retry up to 2 times on transient errors
        )
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

    # Use async generation if available (Python 3.14+ with PYTHON_GIL=0)
    if _supports_async():
        articles = asyncio.run(
            _generate_with_async(
                items,
                args.max_articles,
                args.force_regenerate,
                args.generate_images,
                args.fact_check,
                os.getenv("GITHUB_RUN_ID"),
            )
        )
    else:
        articles = generate_articles_from_enriched(
            items,
            args.max_articles,
            args.force_regenerate,
            args.generate_images,
            args.fact_check,
            os.getenv("GITHUB_RUN_ID"),
        )

    if articles:
        # Calculate total costs
        total_cost = sum(sum(article.generation_costs.values()) for article in articles)

        console.print(
            f"\n[bold green]🎉 Success! Generated {len(articles)} blog articles.[/bold green]"
        )
        console.print("[dim]Total generation cost:  USD[/dim]")
        console.print("[dim]Articles saved to content/ directory[/dim]")
    else:
        console.print("[red]No articles were generated.[/red]")
