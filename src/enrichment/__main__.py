"""Run enrichment pipeline as a standalone module.

Usage:
    python -m src.enrichment

This will find the most recent collected data file and enrich all items.
"""

from pathlib import Path

from rich.console import Console

from ..config import get_data_dir
from .file_io import load_collected_items, save_enriched_items
from .orchestrator import enrich_collected_items

console = Console()


def main():
    """Run enrichment on the most recent collected data."""
    data_dir = get_data_dir()

    # Find the most recent collected file
    collected_files = list(data_dir.glob("collected_*.json"))
    if not collected_files:
        console.print("[red]No collected data files found. Run collection first.[/red]")
        return 1

    latest_file = max(collected_files, key=lambda f: f.stat().st_mtime)
    console.print(f"[blue]Loading items from {latest_file.name}...[/blue]")

    # Load and enrich items
    items = load_collected_items(latest_file)
    enriched = enrich_collected_items(items)

    # Save results
    if enriched:
        save_enriched_items(enriched)
        console.print(
            f"\n[bold green]🎉 Enrichment complete! {len(enriched)} items ready for article generation.[/bold green]"
        )
        return 0
    else:
        console.print("[red]No items were successfully enriched.[/red]")
        return 1


if __name__ == "__main__":
    exit(main())
