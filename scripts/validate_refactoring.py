"""Quick validation that refactored modules work correctly.

This tests basic functionality without making real API calls:
- Collectors: Can create collectors and filter content
- Enrichment: Heuristic scoring works, modules load correctly
- Models: Data structures work as expected
"""

from datetime import UTC, datetime

from rich.console import Console

from src.collectors.base import (
    clean_html_content,
    is_political_content,
)
from src.enrichment import calculate_heuristic_score
from src.models import CollectedItem

console = Console()


def test_collectors_filtering():
    """Test that collector filtering functions work."""
    console.print("[blue]Testing collectors filtering...[/blue]")

    # Test political content detection
    political_text = "Democrats and Republicans debate the election results in congress."
    assert is_political_content(political_text), "Should detect political content"

    tech_policy_text = "New GDPR regulations affect data privacy and encryption policies."
    assert not is_political_content(tech_policy_text), "Should allow tech policy content"

    # Test HTML cleaning
    html_text = "<p>This is <strong>bold</strong> text.</p>"
    clean_text = clean_html_content(html_text)
    assert "<" not in clean_text, "Should strip HTML tags"
    assert "bold" in clean_text, "Should preserve text content"

    console.print("  [green]✓ Collector filtering works[/green]")


def test_enrichment_scoring():
    """Test that enrichment scoring works."""
    console.print("[blue]Testing enrichment scoring...[/blue]")

    # High quality tech content
    high_quality_item = CollectedItem(
        id="test-1",
        title="Understanding Kubernetes Internals",
        content="""
        Deep dive into how Kubernetes schedules pods across nodes.

        ```python
        def schedule_pod(pod, nodes):
            # Select best node based on resources
            return max(nodes, key=lambda n: n.available_memory)
        ```

        This covers architecture, implementation details, and performance considerations.
        """,
        url="https://example.com/k8s",
        source="mastodon",
        collected_at=datetime.now(UTC),
        author="tech_expert",
        metadata={
            "favourites_count": 150,
            "reblogs_count": 45,
            "replies_count": 30,
        },
    )

    score, explanation = calculate_heuristic_score(high_quality_item)
    console.print(f"  High quality score: {score:.2f} - {explanation[:80]}...")
    assert score > 0.5, f"High quality item should score >0.5, got {score}"

    # Low quality personal content
    low_quality_item = CollectedItem(
        id="test-2",
        title="My thoughts",
        content="I feel like today was a good day. Just me tho.",
        url="https://example.com/personal",
        source="mastodon",
        collected_at=datetime.now(UTC),
        author="random_user",
        metadata={},
    )

    score, explanation = calculate_heuristic_score(low_quality_item)
    console.print(f"  Low quality score: {score:.2f} - {explanation[:80]}...")
    assert score < 0.3, f"Low quality item should score <0.3, got {score}"

    console.print("  [green]✓ Enrichment scoring works[/green]")


def test_models():
    """Test that data models work correctly."""
    console.print("[blue]Testing data models...[/blue]")

    # Create a collected item
    item = CollectedItem(
        id="test-model",
        title="Test Article",
        content="Test content",
        url="https://example.com/test",
        source="mastodon",
        collected_at=datetime.now(UTC),
        author="tester",
        metadata={"key": "value"},
    )

    # Verify serialization works
    item_dict = item.model_dump()
    assert item_dict["id"] == "test-model"
    assert item_dict["title"] == "Test Article"

    # Verify deserialization works
    restored_item = CollectedItem(**item_dict)
    assert restored_item.id == item.id
    assert restored_item.title == item.title

    console.print("  [green]✓ Data models work[/green]")


def main():
    """Run all validation tests."""
    console.print("\n[bold cyan]Validating Refactored Modules[/bold cyan]\n")

    try:
        test_models()
        test_collectors_filtering()
        test_enrichment_scoring()

        console.print("\n[bold green]✅ All validation tests passed![/bold green]")
        console.print(
            "[dim]The refactored modules work correctly. Ready to continue with Phase 5.[/dim]\n"
        )
        return 0

    except AssertionError as e:
        console.print(f"\n[bold red]❌ Validation failed: {e}[/bold red]\n")
        return 1
    except Exception as e:
        console.print(f"\n[bold red]❌ Unexpected error: {e}[/bold red]\n")
        return 1


if __name__ == "__main__":
    exit(main())
