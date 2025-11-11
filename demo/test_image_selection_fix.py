#!/usr/bin/env python3
"""Test improved image selection for vintage/historical tech articles."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from openai import OpenAI
from rich.console import Console

from src.config import get_config
from src.images.selector import CoverImageSelector

console = Console()


def test_unix_article_selection():
    """Test image selection for the Unix v4 article."""
    console.print("\n[bold]Testing Image Selection for Unix v4 Article[/bold]\n")

    # Load config
    config = get_config()
    client = OpenAI(api_key=config.openai_api_key)

    # Create selector
    selector = CoverImageSelector(client, config)

    # Unix v4 article data
    title = "Rediscovering Unix v4: A Treasure Trove of Tech History"
    topics = [
        "unix v4",
        "tape recovery",
        "operating systems",
        "historical technology",
        "computer history",
    ]

    console.print(f"[cyan]Title:[/cyan] {title}")
    console.print(f"[cyan]Topics:[/cyan] {', '.join(topics)}\n")

    # Check vintage detection
    is_vintage = selector._detect_vintage_tech_context(title, topics)
    console.print(f"[yellow]Vintage context detected:[/yellow] {is_vintage}\n")

    # Generate queries
    console.print("[blue]Generating search queries...[/blue]")
    queries = selector._generate_search_queries(title, topics)

    console.print("\n[green]Generated queries:[/green]")
    for source, query in queries.items():
        console.print(f"  [bold]{source}:[/bold] {query}")

    console.print(
        "\n[dim]These queries should use generic vintage computing terms[/dim]"
    )
    console.print(
        "[dim]instead of specific 'unix v4 tape recovery' which matches modern PSUs![/dim]"
    )


def test_modern_article_selection():
    """Test that modern tech articles still get specific queries."""
    console.print("\n[bold]Testing Image Selection for Modern Tech Article[/bold]\n")

    # Load config
    config = get_config()
    client = OpenAI(api_key=config.openai_api_key)

    # Create selector
    selector = CoverImageSelector(client, config)

    # Modern article data
    title = "Breakthrough in Quantum Computing: New Qubit Design"
    topics = ["quantum computing", "qubits", "semiconductor technology", "research"]

    console.print(f"[cyan]Title:[/cyan] {title}")
    console.print(f"[cyan]Topics:[/cyan] {', '.join(topics)}\n")

    # Check vintage detection
    is_vintage = selector._detect_vintage_tech_context(title, topics)
    console.print(f"[yellow]Vintage context detected:[/yellow] {is_vintage}\n")

    # Generate queries
    console.print("[blue]Generating search queries...[/blue]")
    queries = selector._generate_search_queries(title, topics)

    console.print("\n[green]Generated queries:[/green]")
    for source, query in queries.items():
        console.print(f"  [bold]{source}:[/bold] {query}")

    console.print("\n[dim]Modern tech should still get specific queries![/dim]")


if __name__ == "__main__":
    test_unix_article_selection()
    test_modern_article_selection()
