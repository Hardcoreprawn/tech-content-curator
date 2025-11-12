#!/usr/bin/env python3
"""Generate quality tracking reports.

This script analyzes the quality history data and generates reports
to help track model performance and quality trends.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from rich.console import Console
from rich.table import Table

from src.content.quality_tracker import QualityTracker

console = Console()


def main():
    """Generate and display quality tracking reports."""
    tracker = QualityTracker()

    if not tracker.history:
        console.print("[yellow]No quality data recorded yet.[/yellow]")
        console.print("\nQuality tracking will begin with the next article generation.")
        console.print(
            "Run the pipeline with quality tracking enabled to start collecting data."
        )
        return

    console.print("\n[bold cyan]Quality Tracking Report[/bold cyan]")
    console.print(f"Total articles tracked: {len(tracker.history)}\n")

    # Overall statistics
    console.print("[bold]Overall Statistics[/bold]")
    stats = tracker.get_statistics()

    if stats.get("insufficient_data"):
        console.print(f"[yellow]{stats['message']}[/yellow]")
        return

    console.print(
        f"Average Quality Score: [bold]{stats['avg_overall_score']:.1f}/100[/bold]"
    )
    console.print(f"Pass Rate: [bold]{stats['pass_rate']:.1f}%[/bold]")
    console.print(
        f"Average Word Count: [bold]{stats['avg_word_count']:.0f}[/bold] words\n"
    )

    # Dimension scores table
    console.print("[bold]Quality Dimensions[/bold]")
    dim_table = Table(show_header=True, header_style="bold magenta")
    dim_table.add_column("Dimension", style="cyan")
    dim_table.add_column("Average Score", justify="right")
    dim_table.add_column("Rating", justify="center")

    for dim, score in stats["avg_dimension_scores"].items():
        rating = "✅" if score >= 80 else "⚠️" if score >= 70 else "❌"
        dim_table.add_row(dim.replace("_", " ").title(), f"{score:.1f}/100", rating)

    console.print(dim_table)
    console.print()

    # Model comparison table
    if len(stats["models_used"]) > 0:
        console.print("[bold]Models Performance[/bold]")
        model_table = Table(show_header=True, header_style="bold magenta")
        model_table.add_column("Model", style="cyan")
        model_table.add_column("Articles", justify="right")
        model_table.add_column("Avg Score", justify="right")
        model_table.add_column("Rating", justify="center")

        for model, data in sorted(
            stats["models_used"].items(), key=lambda x: x[1]["avg_score"], reverse=True
        ):
            rating = (
                "✅"
                if data["avg_score"] >= 80
                else "⚠️"
                if data["avg_score"] >= 70
                else "❌"
            )
            model_table.add_row(
                model, str(data["count"]), f"{data['avg_score']:.1f}", rating
            )

        console.print(model_table)
        console.print()

    # Score distribution
    console.print("[bold]Score Distribution[/bold]")
    console.print(f"Min: {stats['score_distribution']['min']:.1f}")
    console.print(f"Median: {stats['score_distribution']['median']:.1f}")
    console.print(f"Max: {stats['score_distribution']['max']:.1f}\n")

    # Trend analysis (if enough data)
    if len(tracker.history) >= 10:
        console.print("[bold]Trend Analysis (Last 10 Articles)[/bold]")
        trend = tracker.get_trend_analysis(window_size=10)

        if not trend.get("insufficient_data"):
            console.print(
                f"Recent Average: [bold]{trend['recent_avg_score']:.1f}/100[/bold]"
            )
            console.print(
                f"Historical Average: {trend['historical_avg_score']:.1f}/100"
            )

            trend_status = trend["trend"]
            if trend_status == "improving":
                console.print(
                    f"Trend: [bold green]↑ Improving[/bold green] (+{trend['improvement']:.1f})"
                )
            elif trend_status == "declining":
                console.print(
                    f"Trend: [bold red]↓ Declining[/bold red] ({trend['improvement']:.1f})"
                )
            else:
                console.print("Trend: [bold yellow]→ Stable[/bold yellow]")

            console.print(f"Recent Pass Rate: {trend['recent_pass_rate']:.1f}%\n")

    # Model comparison (if multiple models)
    models = list(stats["models_used"].keys())
    if len(models) >= 2:
        console.print("[bold]Model Comparison[/bold]")
        model_a, model_b = models[0], models[1]
        comparison = tracker.compare_models(model_a, model_b)

        if not comparison.get("insufficient_data"):
            diff = comparison["differences"]
            console.print(f"\nComparing {model_a} vs {model_b}:")
            console.print(
                f"Score Difference: {diff['score_diff']:+.1f} ({diff['score_diff_pct']:+.1f}%)"
            )
            console.print(f"Pass Rate Difference: {diff['pass_rate_diff']:+.1f}%")
            console.print(f"Better Model: [bold]{diff['better_model']}[/bold]\n")

    # Export summary
    summary_path = Path("data/quality_summary.txt")
    tracker.export_summary(summary_path)
    console.print(f"[dim]Full summary exported to: {summary_path}[/dim]")


if __name__ == "__main__":
    main()
