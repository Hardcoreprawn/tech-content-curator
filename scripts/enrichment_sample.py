#!/usr/bin/env python3
"""
Run a small enrichment sample using real OpenAI (requires API key).
"""

from rich.console import Console

from src.config import get_config, get_data_dir
from src.enrich import enrich_single_item, load_collected_items

console = Console()


def run_sample() -> None:
    console.print("[bold]AI Enrichment (Real OpenAI)[/bold]\n")

    data_dir = get_data_dir()
    collected_files = list(data_dir.glob("collected_*.json"))
    if not collected_files:
        console.print("[red]No collected data found![/red]")
        return

    latest_file = max(collected_files, key=lambda f: f.stat().st_mtime)
    console.print(f"[blue]Loading from {latest_file.name}...[/blue]")

    items = load_collected_items(latest_file)
    if not items:
        console.print("[red]No items to enrich![/red]")
        return

    test_items = items[:2]
    config = get_config()

    console.print(f"[blue]Testing enrichment on {len(test_items)} items...[/blue]\n")
    for i, item in enumerate(test_items, 1):
        console.print(f"[bold]--- Item {i}/{len(test_items)} ---[/bold]")
        console.print(f"[dim]Original:[/dim] {item.title}")
        console.print(f"[dim]Content preview:[/dim] {item.content[:100]}...")

        enriched = enrich_single_item(item, config)
        if enriched:
            console.print("[green]✓ Success![/green]")
            console.print(f"[dim]Final Quality Score:[/dim] {enriched.quality_score:.2f}")
            console.print(f"[dim]Topics:[/dim] {', '.join(enriched.topics)}")
            console.print(
                f"[dim]Research Preview:[/dim] {enriched.research_summary[:150]}...\n"
            )
        else:
            console.print("[red]✗ Failed[/red]\n")


if __name__ == "__main__":
    run_sample()
