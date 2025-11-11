"""Run collection pipeline as a standalone module.

Usage:
    python -m src.collectors

This will collect content from all configured sources and save to data/.
With PYTHON_GIL=0, uses parallel collection for faster results.
"""

import asyncio

from rich.console import Console

from ..utils.free_threading import supports_free_threading
from .orchestrator import (
    collect_all_sources,
    collect_all_sources_async,
    save_collected_items,
)

console = Console()


def main() -> int:
    """Run collection from all sources."""
    console.print("[bold blue]📥 Starting content collection...[/bold blue]")

    # Use parallel collection if free-threading is available
    if supports_free_threading():
        console.print(
            "[bold green]⚡ Python 3.14 free-threading enabled - collecting in parallel![/bold green]"
        )
        items = asyncio.run(collect_all_sources_async())
    else:
        items = collect_all_sources()

    if items:
        save_collected_items(items)
        console.print(
            f"\n[bold green]✅ Collection complete: {len(items)} items collected[/bold green]"
        )
        return 0
    else:
        console.print("[yellow]⚠️  No items collected[/yellow]")
        return 1


if __name__ == "__main__":
    exit(main())
