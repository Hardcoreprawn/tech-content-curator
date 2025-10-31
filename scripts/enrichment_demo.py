#!/usr/bin/env python3
"""
Enrichment pipeline demo (mocked OpenAI).

Shows the enrichment pipeline structure with deterministic mocked responses.
"""

from unittest.mock import Mock, patch
from rich.console import Console

from src.config import get_config, get_data_dir
from src.enrichment import enrich_single_item, load_collected_items

console = Console()


def _mock_openai_responses() -> Mock:
    """Create mock OpenAI responses for testing.

    Returns:
        Mock: A mocked OpenAI client with side-effected responses.
    """
    mock_client = Mock()

    quality_response = Mock()
    quality_response.choices = [Mock()]
    quality_response.choices[0].message.content = (
        '{"score": 0.8, "explanation": "Interesting technical content with good depth"}'
    )

    topics_response = Mock()
    topics_response.choices = [Mock()]
    topics_response.choices[0].message.content = (
        '["python", "web development", "api design"]'
    )

    research_response = Mock()
    research_response.choices = [Mock()]
    research_response.choices[0].message.content = (
        """
        This content discusses modern web development practices, particularly API design patterns.

        Current state: RESTful APIs remain the dominant architecture, though GraphQL and gRPC are gaining traction in specific use cases. The Python ecosystem offers excellent frameworks like FastAPI and Django Rest Framework for building robust APIs.

        Key questions readers might have include: What are the trade-offs between different API styles? How do you handle authentication and rate limiting? What are the best practices for API versioning and documentation?
        """
    )

    call_count = 0

    def side_effect(*_args, **_kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return quality_response
        if call_count == 2:
            return topics_response
        return research_response

    mock_client.chat.completions.create.side_effect = side_effect
    return mock_client


def run_demo() -> None:
    console.print("[bold]Enrichment Pipeline Demo (Mock Mode)[/bold]\n")

    data_dir = get_data_dir()
    collected_files = list(data_dir.glob("collected_*.json"))
    if not collected_files:
        console.print("[red]No collected data found. Run collection first![/red]")
        return

    latest_file = max(collected_files, key=lambda f: f.stat().st_mtime)
    console.print(f"[blue]Loading from {latest_file.name}...[/blue]")

    items = load_collected_items(latest_file)
    console.print(f"Loaded {len(items)} items")
    if not items:
        console.print("[red]No items to enrich![/red]")
        return

    test_item = items[0]
    console.print(f"\n[blue]Testing enrichment on:[/blue] {test_item.title[:60]}...")

    with patch("src.enrich.OpenAI") as mock_openai_class:
        mock_openai_class.return_value = _mock_openai_responses()

        # Set a fake API key for validation inside get_config()
        import os

        os.environ["OPENAI_API_KEY"] = "test-key-for-mock"
        config = get_config()
        enriched = enrich_single_item(test_item, config)

    if enriched:
        console.print("\n[green]✓ Enrichment successful![/green]")
        console.print(f"[dim]Quality Score:[/dim] {enriched.quality_score}")
        console.print(f"[dim]Topics:[/dim] {', '.join(enriched.topics)}")
        console.print(
            f"[dim]Research Summary:[/dim] {enriched.research_summary[:100]}..."
        )
        console.print(
            "\n[bold green]🎉 Enrichment pipeline is working correctly![/bold green]"
        )
        console.print(
            "[yellow]To run with real AI: Add your OpenAI API key to .env file[/yellow]"
        )
    else:
        console.print("[red]✗ Enrichment failed[/red]")


if __name__ == "__main__":
    run_demo()
