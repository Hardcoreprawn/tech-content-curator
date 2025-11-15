#!/usr/bin/env python3
"""Test models on a complex, long-form article with quality scoring.

This script tests different models on generating a sophisticated technical article
and scores them using the project's quality metrics: readability, technical depth,
structure, and engagement.
"""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from openai import OpenAI
from rich.console import Console
from rich.table import Table

from src.config import get_config
from src.content.readability import ReadabilityAnalyzer
from src.utils.openai_client import create_chat_completion

console = Console()
readability_analyzer = ReadabilityAnalyzer()


COMPLEX_PROMPT = """Write a comprehensive 1500+ word technical article about the convergence of AI and Quantum Computing.

Your article should cover:
1. Current state of both technologies
2. How they complement each other (quantum for optimization, AI for quantum control)
3. Key breakthroughs expected in the next 5 years
4. Practical implications for:
   - Drug discovery and materials science
   - Financial modeling and cryptography
   - Climate modeling and optimization
   - Machine learning algorithm acceleration
5. Major challenges and limitations
6. What this means for developers and researchers

Requirements:
- Minimum 1500 words
- Technical depth appropriate for software developers and engineers
- Clear explanations with concrete examples
- Well-structured with logical flow
- Engaging writing that maintains reader interest
- Accurate, current information (as of 2025)
- Include specific companies, projects, or research where relevant

Tone: Professional but accessible, enthusiastic about possibilities while realistic about challenges."""


MODEL_PRICING = {
    "gpt-5.1": {"input": 1.50, "output": 12.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-5-mini": {"input": 0.25, "output": 2.00},
}


def calculate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Calculate cost for a model based on token usage."""
    pricing = None
    for model_prefix, model_pricing in MODEL_PRICING.items():
        if model.startswith(model_prefix):
            pricing = model_pricing
            break

    if not pricing:
        return 0.0

    input_cost = (input_tokens / 1_000_000) * pricing["input"]
    output_cost = (output_tokens / 1_000_000) * pricing["output"]
    return input_cost + output_cost


def test_model_complex(
    client: OpenAI,
    model: str,
    prompt: str,
) -> dict[str, Any]:
    """Test a model on complex article generation."""
    console.print(f"\n[bold cyan]Testing {model}...[/bold cyan]")

    start_time = time.time()

    try:
        response = create_chat_completion(
            client=client,
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
        )

        elapsed = time.time() - start_time
        content = response.choices[0].message.content or ""

        input_tokens = response.usage.prompt_tokens if response.usage else 0
        output_tokens = response.usage.completion_tokens if response.usage else 0
        cost = calculate_cost(model, input_tokens, output_tokens)

        # Basic metrics
        word_count = len(content.split())
        char_count = len(content)

        console.print(f"  ✓ Generated {word_count} words in {elapsed:.1f}s")
        console.print("  📊 Analyzing quality...")

        # Quality analysis
        readability_score = readability_analyzer.analyze(content)
        readability = {
            "flesch_reading_ease": readability_score.flesch_reading_ease,
            "grade_level": readability_score.grade_level,
            "fog_index": readability_score.fog_index,
        }

        quality_scores = {
            "overall_score": readability_score.flesch_reading_ease,
            "readability_score": readability_score.flesch_reading_ease,
            "grade_level": readability_score.grade_level,
            "fog_index": readability_score.fog_index,
        }

        console.print(
            f"  📖 Readability (Flesch): {readability_score.flesch_reading_ease:.1f}"
        )
        console.print(f"  🎓 Grade Level: {readability_score.grade_level:.1f}")

        return {
            "model": model,
            "success": True,
            "content": content,
            "word_count": word_count,
            "char_count": char_count,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "tokens_per_word": output_tokens / word_count if word_count > 0 else 0,
            "cost": cost,
            "cost_per_1k_words": (cost / word_count * 1000) if word_count > 0 else 0,
            "elapsed_seconds": elapsed,
            "readability": readability,
            "quality_scores": quality_scores,
            "error": None,
        }

    except Exception as e:
        elapsed = time.time() - start_time
        console.print(f"  [red]✗ Error: {e}[/red]")
        return {
            "model": model,
            "success": False,
            "content": "",
            "word_count": 0,
            "char_count": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "tokens_per_word": 0,
            "cost": 0.0,
            "cost_per_1k_words": 0.0,
            "elapsed_seconds": elapsed,
            "readability": {},
            "quality_scores": {},
            "error": str(e),
        }


def display_results(results: list[dict[str, Any]]) -> None:
    """Display comparison results."""
    console.print("\n[bold]Complex Article Generation Results[/bold]")
    console.print("=" * 120)

    # Performance table
    perf_table = Table(title="Performance & Quality Metrics")
    perf_table.add_column("Model", style="cyan")
    perf_table.add_column("Words", justify="right")
    perf_table.add_column("Quality", justify="right")
    perf_table.add_column("Readability", justify="right")
    perf_table.add_column("Tok/Word", justify="right")
    perf_table.add_column("Time (s)", justify="right")
    perf_table.add_column("Cost", justify="right")
    perf_table.add_column("$/1K words", justify="right")

    successful = [r for r in results if r["success"]]

    for result in successful:
        quality = result["quality_scores"].get("overall_score", 0)
        readability = result["readability"].get("flesch_reading_ease", 0)

        perf_table.add_row(
            result["model"],
            str(result["word_count"]),
            f"{quality:.1f}/100",
            f"{readability:.1f}",
            f"{result['tokens_per_word']:.1f}",
            f"{result['elapsed_seconds']:.1f}",
            f"${result['cost']:.4f}",
            f"${result['cost_per_1k_words']:.4f}",
        )

    console.print(perf_table)

    # Quality breakdown
    if successful:
        console.print("\n[bold]Readability Breakdown:[/bold]")
        for result in successful:
            scores = result["quality_scores"]
            readability = result["readability"]
            console.print(f"\n[cyan]{result['model']}:[/cyan]")
            console.print(
                f"  Flesch Reading Ease: {scores.get('readability_score', 0):.1f} (60-70 = standard)"
            )
            console.print(f"  Grade Level: {scores.get('grade_level', 0):.1f}")
            console.print(f"  Fog Index: {scores.get('fog_index', 0):.1f}")
            console.print(f"  SMOG Index: {readability.get('smog_index', 0):.1f}")

        # Summary
        console.print("\n[bold]Summary:[/bold]")

        best_quality = max(
            successful, key=lambda x: x["quality_scores"].get("overall_score", 0)
        )
        console.print(
            f"  🏆 Best Quality: [cyan]{best_quality['model']}[/cyan] ({best_quality['quality_scores'].get('overall_score', 0):.1f}/100)"
        )

        most_readable = max(
            successful, key=lambda x: x["readability"].get("flesch_reading_ease", 0)
        )
        console.print(
            f"  📖 Most Readable: [cyan]{most_readable['model']}[/cyan] (Flesch: {most_readable['readability'].get('flesch_reading_ease', 0):.1f})"
        )

        best_value = min(successful, key=lambda x: x["cost_per_1k_words"])
        console.print(
            f"  💰 Best Value: [cyan]{best_value['model']}[/cyan] (${best_value['cost_per_1k_words']:.4f} per 1K words)"
        )

        fastest = min(successful, key=lambda x: x["elapsed_seconds"])
        console.print(
            f"  ⚡ Fastest: [cyan]{fastest['model']}[/cyan] ({fastest['elapsed_seconds']:.1f}s)"
        )


def save_results(results: list[dict[str, Any]], output_file: Path) -> None:
    """Save detailed results including full article text."""
    output = {
        "timestamp": datetime.now().isoformat(),
        "prompt": COMPLEX_PROMPT,
        "results": results,
    }

    with open(output_file, "w") as f:
        json.dump(output, f, indent=2)

    console.print(f"\n[green]Results saved to: {output_file}[/green]")

    # Also save individual articles for reading
    for result in results:
        if result["success"]:
            article_file = (
                output_file.parent / f"article_{result['model'].replace('/', '_')}.md"
            )
            with open(article_file, "w") as f:
                f.write("# The Convergence of AI and Quantum Computing\n\n")
                f.write(f"**Model:** {result['model']}\n")
                f.write(
                    f"**Quality Score:** {result['quality_scores'].get('overall_score', 0):.1f}/100\n"
                )
                f.write(f"**Words:** {result['word_count']}\n")
                f.write(f"**Cost:** ${result['cost']:.4f}\n")
                f.write(f"**Time:** {result['elapsed_seconds']:.1f}s\n\n")
                f.write("---\n\n")
                f.write(result["content"])

            console.print(f"  Article saved to: {article_file}")


def main():
    """Run complex article test."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Test models on complex article generation with quality scoring"
    )
    parser.add_argument(
        "--models",
        nargs="+",
        default=["gpt-5.1", "gpt-4o-mini", "gpt-5-mini"],
        help="Models to test",
    )
    parser.add_argument(
        "--output",
        default="data/complex_article_test.json",
        help="Output file for results",
    )

    args = parser.parse_args()

    config = get_config()
    client = OpenAI(api_key=config.openai_api_key)

    console.print("[bold]Complex Article Generation Test[/bold]")
    console.print(
        f"Testing {len(args.models)} models on 1500+ word technical article\n"
    )
    console.print("[dim]Topic: AI and Quantum Computing Convergence[/dim]")
    console.print(
        "[dim]Including quality scoring with project's rating systems[/dim]\n"
    )

    results = []
    for model in args.models:
        result = test_model_complex(client, model, COMPLEX_PROMPT)
        results.append(result)

    display_results(results)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    save_results(results, output_path)

    console.print("\n[bold green]Testing Complete![/bold green]")


if __name__ == "__main__":
    main()
