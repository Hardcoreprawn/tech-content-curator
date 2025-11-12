#!/usr/bin/env python3
"""Analyze quality metrics from existing article frontmatter.

This script reads published articles and analyzes their quality metrics
to help track model performance and quality trends over time.
"""

import sys
from pathlib import Path
from typing import cast

import frontmatter
from rich.console import Console
from rich.table import Table

console = Console()


def load_article_metrics(content_dir: Path) -> list[dict]:
    """Load quality metrics from all published articles.

    Args:
        content_dir: Path to content directory

    Returns:
        List of article metrics dictionaries
    """
    metrics = []

    for article_path in content_dir.glob("**/*.md"):
        try:
            post = frontmatter.load(str(article_path))

            # Extract relevant metrics
            article_metrics = {
                "title": post.get("title", "Unknown"),
                "date": post.get("date", "Unknown"),
                "filename": article_path.name,
                "word_count": post.get("word_count", 0),
                "enrichment_quality": post.get("quality_score", 0),
                "content_type": post.get("content_type", "general"),
                "difficulty": post.get("difficulty", "intermediate"),
                "generator": post.get("generator", "Unknown"),
            }

            # Add readability if available
            readability = post.get("readability")
            if readability and isinstance(readability, dict):
                article_metrics["flesch_score"] = readability.get("flesch_score")
                article_metrics["grade_level"] = readability.get("grade_level")
                article_metrics["rating"] = readability.get("rating")

            # Add new article quality metrics if available
            article_quality = post.get("article_quality")
            if article_quality and isinstance(article_quality, dict):
                article_metrics["article_quality_score"] = article_quality.get(
                    "overall_score"
                )
                article_metrics["quality_passed"] = article_quality.get(
                    "passed_threshold"
                )
                article_metrics["quality_dimensions"] = article_quality.get(
                    "dimensions", {}
                )

            # Add model info if available
            models_used = post.get("models_used")
            if models_used and isinstance(models_used, dict):
                article_metrics["content_model"] = models_used.get("content")
                article_metrics["title_model"] = models_used.get("title")
                article_metrics["enrichment_model"] = models_used.get("enrichment")

            metrics.append(article_metrics)

        except Exception as e:
            console.print(
                f"[yellow]Warning: Failed to load {article_path.name}: {e}[/yellow]"
            )

    return metrics


def generate_statistics(metrics: list[dict]) -> dict:
    """Generate statistics from article metrics.

    Args:
        metrics: List of article metrics

    Returns:
        Dictionary of statistics
    """
    if not metrics:
        return {"count": 0}

    # Basic stats
    stats = {
        "total_articles": len(metrics),
        "avg_word_count": sum(m["word_count"] for m in metrics) / len(metrics),
        "avg_enrichment_quality": sum(m["enrichment_quality"] for m in metrics)
        / len(metrics),
    }

    # Readability stats (if available)
    flesch_scores = cast(
        list[float],
        [m.get("flesch_score") for m in metrics if m.get("flesch_score") is not None],
    )
    if flesch_scores:
        stats["avg_flesch_score"] = sum(flesch_scores) / len(flesch_scores)
        stats["readability_count"] = len(flesch_scores)

    # New quality metrics (if available)
    quality_scores = cast(
        list[float],
        [
            m.get("article_quality_score")
            for m in metrics
            if m.get("article_quality_score") is not None
        ],
    )
    if quality_scores:
        stats["avg_article_quality"] = sum(quality_scores) / len(quality_scores)
        stats["quality_tracked_count"] = len(quality_scores)

        # Pass rate
        passed = [m for m in metrics if m.get("quality_passed") is True]
        stats["quality_pass_rate"] = (len(passed) / len(quality_scores)) * 100

    # Model breakdown
    models = {}
    for m in metrics:
        content_model = m.get("content_model", "unknown")
        if content_model != "unknown":
            if content_model not in models:
                models[content_model] = {"count": 0, "scores": []}
            models[content_model]["count"] += 1
            if m.get("article_quality_score"):
                models[content_model]["scores"].append(m["article_quality_score"])

    # Calculate averages
    for model in models:
        if models[model]["scores"]:
            models[model]["avg_score"] = sum(models[model]["scores"]) / len(
                models[model]["scores"]
            )

    stats["models"] = models

    # Content type breakdown
    content_types = {}
    for m in metrics:
        ct = m.get("content_type", "general")
        if ct not in content_types:
            content_types[ct] = 0
        content_types[ct] += 1
    stats["content_types"] = content_types

    return stats


def main():
    """Main entry point."""
    # Get content directory
    project_root = Path(__file__).parent.parent
    content_dir = project_root / "content" / "posts"

    if not content_dir.exists():
        console.print(f"[red]Error: Content directory not found: {content_dir}[/red]")
        sys.exit(1)

    console.print("[bold cyan]Analyzing Published Articles[/bold cyan]\n")
    console.print(f"Loading articles from: {content_dir}\n")

    # Load metrics
    metrics = load_article_metrics(content_dir)

    if not metrics:
        console.print("[yellow]No articles found[/yellow]")
        return

    # Generate statistics
    stats = generate_statistics(metrics)

    console.print(f"[bold]Found {stats['total_articles']} articles[/bold]\n")

    # Basic stats
    console.print("[bold]Content Statistics[/bold]")
    console.print(f"Average Word Count: {stats['avg_word_count']:.0f}")
    console.print(
        f"Average Enrichment Quality: {stats['avg_enrichment_quality']:.2f}/1.0\n"
    )

    # Readability stats
    if "avg_flesch_score" in stats:
        console.print("[bold]Readability Metrics[/bold]")
        console.print(
            f"Articles with readability data: {stats['readability_count']}/{stats['total_articles']}"
        )
        console.print(f"Average Flesch Score: {stats['avg_flesch_score']:.1f}/100")
        console.print("  (60-70 = Plain English, 50-60 = Fairly Difficult)\n")

    # New quality metrics
    if "avg_article_quality" in stats:
        console.print("[bold]Article Quality Metrics (New System)[/bold]")
        console.print(
            f"Articles with quality tracking: {stats['quality_tracked_count']}/{stats['total_articles']}"
        )
        console.print(
            f"Average Article Quality: {stats['avg_article_quality']:.1f}/100"
        )
        console.print(f"Quality Pass Rate: {stats['quality_pass_rate']:.1f}%\n")
    else:
        console.print("[yellow]No articles with new quality tracking yet.[/yellow]")
        console.print(
            "[dim]Quality tracking will begin with the next article generation.[/dim]\n"
        )

    # Model comparison
    if stats["models"]:
        console.print("[bold]Model Performance Comparison[/bold]")
        model_table = Table(show_header=True, header_style="bold magenta")
        model_table.add_column("Model", style="cyan")
        model_table.add_column("Articles", justify="right")
        model_table.add_column("Avg Quality", justify="right")
        model_table.add_column("Status", justify="center")

        for model, data in sorted(
            stats["models"].items(),
            key=lambda x: x[1].get("avg_score", 0),
            reverse=True,
        ):
            avg_score = data.get("avg_score")
            if avg_score:
                rating = "✅" if avg_score >= 80 else "⚠️" if avg_score >= 70 else "❌"
                model_table.add_row(
                    model, str(data["count"]), f"{avg_score:.1f}", rating
                )
            else:
                model_table.add_row(model, str(data["count"]), "N/A", "📊")

        console.print(model_table)
        console.print()

    # Content type breakdown
    if stats["content_types"]:
        console.print("[bold]Content Types[/bold]")
        ct_table = Table(show_header=True, header_style="bold magenta")
        ct_table.add_column("Type", style="cyan")
        ct_table.add_column("Count", justify="right")
        ct_table.add_column("Percentage", justify="right")

        for ct, count in sorted(
            stats["content_types"].items(), key=lambda x: x[1], reverse=True
        ):
            pct = (count / stats["total_articles"]) * 100
            ct_table.add_row(ct, str(count), f"{pct:.1f}%")

        console.print(ct_table)

    console.print(
        "\n[dim]💡 Tip: Run article generation to see new quality metrics with model tracking[/dim]"
    )


if __name__ == "__main__":
    main()
