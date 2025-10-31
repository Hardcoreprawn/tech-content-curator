"""Run collection pipeline as a standalone module.

Usage:
    python -m src.collectors

This will collect content from all configured sources and save to data/.
"""

from rich.console import Console

from .orchestrator import collect_all_sources, save_collected_items

console = Console()


def main():
    """Run collection from all sources."""
    console.print("[bold blue]📥 Starting content collection...[/bold blue]")
    
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
