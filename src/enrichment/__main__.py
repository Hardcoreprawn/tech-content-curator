"""Run enrichment pipeline as a standalone module.

Usage:
    python -m src.enrichment

This will find the most recent collected data file and enrich all items.
With PYTHON_GIL=0, uses parallel enrichment for faster results.
"""

import asyncio
import logging

from rich.console import Console

from ..config import get_data_dir
from ..utils.free_threading import supports_free_threading
from .file_io import load_collected_items, save_enriched_items
from .orchestrator import enrich_collected_items, enrich_collected_items_async

console = Console()
logger = logging.getLogger(__name__)


def main() -> int:
    """Run enrichment on the most recent collected data."""
    data_dir = get_data_dir()

    # Find the most recent collected file
    collected_files = list(data_dir.glob("collected_*.json"))
    if not collected_files:
        console.print("[red]No collected data files found. Run collection first.[/red]")
        logger.error("No collected data files found")
        return 1

    latest_file = max(collected_files, key=lambda f: f.stat().st_mtime)
    console.print(f"[blue]Loading items from {latest_file.name}...[/blue]")
    logger.info(f"Loading collected items from: {latest_file.name}")

    # Load and enrich items
    items = load_collected_items(latest_file)

    # Use parallel enrichment if free-threading is available
    if supports_free_threading():
        console.print(
            "[bold green]⚡ Python 3.14 free-threading enabled - enriching in parallel![/bold green]"
        )
        enriched = asyncio.run(enrich_collected_items_async(items))
    else:
        enriched = enrich_collected_items(items)

    # Save results - always save enriched items, even if count is low
    if enriched:
        filepath = save_enriched_items(enriched)
        console.print(
            f"\n[bold green]🎉 Enrichment complete! {len(enriched)} items saved to {filepath.name}[/bold green]"
        )
        logger.info(f"Successfully saved {len(enriched)} enriched items")

        # Show threshold statistics
        above_threshold = sum(1 for e in enriched if e.quality_score >= 0.5)
        if above_threshold > 0:
            console.print(
                f"[green]✓ {above_threshold} items ready for article generation (score >= 0.5)[/green]"
            )
            logger.info(
                f"Items ready for generation: {above_threshold}/{len(enriched)}"
            )
        else:
            console.print(
                "[yellow]⚠ No items met article generation threshold (>= 0.5)[/yellow]"
            )
            console.print(
                f"[dim]  Best quality scores: {sorted([e.quality_score for e in enriched], reverse=True)[:5]}[/dim]"
            )
            logger.warning(
                f"No items met threshold. Top scores: {sorted([e.quality_score for e in enriched], reverse=True)[:5]}"
            )

        return 0
    else:
        console.print("[red]No items were successfully enriched.[/red]")
        logger.error("Enrichment produced no items")
        return 1


if __name__ == "__main__":
    exit(main())
