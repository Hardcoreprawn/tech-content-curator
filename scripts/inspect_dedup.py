#!/usr/bin/env python3
"""
CLI tool to inspect deduplication patterns and feedback.
"""
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.dedup_feedback import DeduplicationFeedbackSystem
from src.semantic_dedup import SemanticDeduplicator


def main():
    """Show deduplication insights."""
    console = Console()

    # Load deduplicator and feedback system
    deduplicator = SemanticDeduplicator()
    feedback_system = DeduplicationFeedbackSystem()

    console.print("[bold blue]🔍 Deduplication Insights[/bold blue]\n")

    # Show pattern stats
    stats = deduplicator.get_pattern_stats()
    if stats.get('total_patterns', 0) > 0:
        console.print(Panel(
            f"[green]Learned Patterns: {stats['total_patterns']}[/green]\n"
            f"[cyan]Average Confidence: {stats.get('avg_confidence', 0):.2f}[/cyan]\n"
            f"[yellow]Most Frequent Pattern: {stats.get('most_frequent', 0)} occurrences[/yellow]\n"
            f"[magenta]Entity Categories: {stats.get('entity_categories', 0)}[/magenta]\n"
            f"[blue]Keyword Vocabulary: {stats.get('keyword_vocabulary', 0)}[/blue]",
            title="📊 Pattern Statistics"
        ))
    else:
        console.print("[yellow]No learned patterns yet. Run collection to start learning.[/yellow]")

    # Show recent patterns
    if deduplicator.patterns:
        console.print("\n[bold]🎯 Recent Learned Patterns:[/bold]")

        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Entities", style="cyan", width=30)
        table.add_column("Keywords", style="green", width=30)
        table.add_column("Confidence", style="yellow", width=10)
        table.add_column("Frequency", style="red", width=10)
        table.add_column("Examples", style="dim", width=40)

        # Show last 5 patterns
        for pattern in sorted(deduplicator.patterns, key=lambda p: p.last_seen, reverse=True)[:5]:
            entities_str = ", ".join(list(pattern.entities)[:3])
            if len(pattern.entities) > 3:
                entities_str += f" (+{len(pattern.entities)-3} more)"

            keywords_str = ", ".join(list(pattern.keywords)[:3])
            if len(pattern.keywords) > 3:
                keywords_str += f" (+{len(pattern.keywords)-3} more)"

            examples_str = pattern.examples[0] if pattern.examples else "No examples"

            table.add_row(
                entities_str,
                keywords_str,
                f"{pattern.confidence:.2f}",
                str(pattern.frequency),
                examples_str
            )

        console.print(table)

    # Show feedback metrics
    metrics = feedback_system.get_quality_metrics()
    if metrics:
        console.print("\n")
        console.print(Panel(
            f"[green]Total Sessions: {metrics.get('total_sessions', 0)}[/green]\n"
            f"[cyan]Avg Items/Session: {metrics.get('avg_items_per_session', 0):.1f}[/cyan]\n"
            f"[yellow]Avg Duplicates Found: {metrics.get('avg_duplicates_found', 0):.1f}[/yellow]\n"
            f"[magenta]Duplicate Rate: {metrics.get('duplicate_rate', 0):.1%}[/magenta]\n"
            f"[blue]Pattern Growth: +{metrics.get('patterns_growth', 0)} patterns[/blue]",
            title="📈 Performance Metrics"
        ))

        # Show suggestions
        suggestions = feedback_system.suggest_improvements()
        if suggestions:
            console.print("\n[bold]💡 Suggestions:[/bold]")
            for i, suggestion in enumerate(suggestions[:3], 1):
                console.print(f"{i}. {suggestion}")


if __name__ == "__main__":
    main()
