#!/usr/bin/env python3
"""Compare different AI models for article generation quality and cost.

This script tests multiple models on the same content to help determine:
- Which models provide the best quality for your use case
- Cost differences between models
- Speed/performance implications
- Whether newer models (like GPT-5.1) are worth the upgrade

Usage:
    python scripts/compare_models.py [--model MODEL1 MODEL2 ...] [--prompt-file FILE]
"""

import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any

from openai import OpenAI
from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
)
from rich.table import Table

from src.config import get_config
from src.utils.openai_client import create_chat_completion

console = Console()


# Pricing per 1M tokens (as of Nov 2025)
MODEL_PRICING = {
    # GPT-5 Series
    "gpt-5-nano": {"input": 0.05, "output": 0.40},
    "gpt-5-mini": {"input": 0.25, "output": 2.00},
    "gpt-5": {"input": 1.25, "output": 10.00},
    "gpt-5-pro": {"input": 15.00, "output": 120.00},
    # GPT-5.1 Series (assumed similar or slightly higher)
    "gpt-5.1": {"input": 1.50, "output": 12.00},
    "gpt-5.1-codex": {"input": 1.75, "output": 14.00},
    # GPT-4 Series
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4": {"input": 30.00, "output": 60.00},
    "gpt-4-turbo": {"input": 10.00, "output": 30.00},
    # GPT-4.1 Series
    "gpt-4.1": {"input": 2.75, "output": 11.00},
    "gpt-4.1-mini": {"input": 0.20, "output": 0.80},
    "gpt-4.1-nano": {"input": 0.08, "output": 0.50},
}


def calculate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Calculate cost for a model based on token usage."""
    # Try exact match first
    if model in MODEL_PRICING:
        pricing = MODEL_PRICING[model]
    else:
        # Try to match by prefix
        pricing = None
        for model_prefix, model_pricing in MODEL_PRICING.items():
            if model.startswith(model_prefix):
                pricing = model_pricing
                break

        if not pricing:
            console.print(
                f"[yellow]Warning: No pricing info for {model}, using $0[/yellow]"
            )
            return 0.0

    input_cost = (input_tokens / 1_000_000) * pricing["input"]
    output_cost = (output_tokens / 1_000_000) * pricing["output"]
    return input_cost + output_cost


def test_model(
    client: OpenAI,
    model: str,
    prompt: str,
    temperature: float = 0.7,
) -> dict[str, Any]:
    """Test a single model and return results."""
    console.print(f"Testing [cyan]{model}[/cyan]...")

    start_time = time.time()

    try:
        response = create_chat_completion(
            client=client,
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
        )

        elapsed = time.time() - start_time
        content = response.choices[0].message.content or ""

        input_tokens = response.usage.prompt_tokens if response.usage else 0
        output_tokens = response.usage.completion_tokens if response.usage else 0
        cost = calculate_cost(model, input_tokens, output_tokens)

        return {
            "model": model,
            "success": True,
            "content": content,
            "content_length": len(content),
            "word_count": len(content.split()),
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "cost": cost,
            "elapsed_seconds": elapsed,
            "finish_reason": response.choices[0].finish_reason,
            "error": None,
        }

    except Exception as e:
        elapsed = time.time() - start_time
        console.print(f"  [red]Error: {e}[/red]")
        return {
            "model": model,
            "success": False,
            "content": "",
            "content_length": 0,
            "word_count": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "cost": 0.0,
            "elapsed_seconds": elapsed,
            "finish_reason": None,
            "error": str(e),
        }


def display_results(results: list[dict[str, Any]]) -> None:
    """Display comparison results in a nice table."""
    console.print("\n[bold]Model Comparison Results[/bold]")
    console.print("=" * 100)

    # Create performance table
    perf_table = Table(title="Performance Metrics (Averaged)")
    perf_table.add_column("Model", style="cyan")
    perf_table.add_column("Status", style="green")
    perf_table.add_column("Iterations", justify="right")
    perf_table.add_column("Words", justify="right")
    perf_table.add_column("Tokens (in/out)", justify="right")
    perf_table.add_column("Tok/Word", justify="right")
    perf_table.add_column("Time (s)", justify="right")
    perf_table.add_column("Cost ($)", justify="right")
    perf_table.add_column("$/1K words", justify="right")

    for result in results:
        if not result["success"]:
            perf_table.add_row(
                result["model"],
                "[red]✗ FAIL[/red]",
                f"{result.get('iterations', 0)}",
                "-",
                "-",
                "-",
                "-",
                "-",
            )
            continue

        status = f"✓ {result['successful_iterations']}/{result['iterations']}"
        status_style = (
            "green"
            if result["successful_iterations"] == result["iterations"]
            else "yellow"
        )

        cost_per_1k = (
            (result["avg_cost"] / result["avg_word_count"]) * 1000
            if result["avg_word_count"] > 0
            else 0.0
        )

        tokens_per_word = (
            result["avg_output_tokens"] / result["avg_word_count"]
            if result["avg_word_count"] > 0
            else 0.0
        )

        time_range = (
            f"{result['min_elapsed_seconds']:.1f}-{result['max_elapsed_seconds']:.1f}"
        )

        perf_table.add_row(
            result["model"],
            f"[{status_style}]{status}[/{status_style}]",
            str(result["iterations"]),
            f"{result['avg_word_count']:.0f}",
            f"{result['avg_input_tokens']:.0f}/{result['avg_output_tokens']:.0f}",
            f"{tokens_per_word:.1f}",
            f"{result['avg_elapsed_seconds']:.1f} ({time_range})",
            f"${result['avg_cost']:.6f}",
            f"${cost_per_1k:.6f}",
        )

    console.print(perf_table)

    # Summary statistics
    successful = [r for r in results if r["success"]]
    if successful:
        console.print("\n[bold]Summary:[/bold]")

        # Best value (cost per word)
        best_value = min(
            successful,
            key=lambda x: (x["avg_cost"] / x["avg_word_count"])
            if x["avg_word_count"] > 0
            else float("inf"),
        )
        console.print(
            f"  Best Value: [cyan]{best_value['model']}[/cyan] (${(best_value['avg_cost'] / best_value['avg_word_count']) * 1000:.6f} per 1K words)"
        )

        # Fastest
        fastest = min(successful, key=lambda x: x["avg_elapsed_seconds"])
        console.print(
            f"  Fastest: [cyan]{fastest['model']}[/cyan] ({fastest['avg_elapsed_seconds']:.2f}s avg, {fastest['min_elapsed_seconds']:.2f}s min)"
        )

        # Most token efficient (lowest tokens per word)
        token_efficiencies = [
            (r, r["avg_output_tokens"] / r["avg_word_count"]) for r in successful
        ]
        most_efficient = min(token_efficiencies, key=lambda x: x[1])
        least_efficient = max(token_efficiencies, key=lambda x: x[1])
        console.print(
            f"  Most Token Efficient: [cyan]{most_efficient[0]['model']}[/cyan] ({most_efficient[1]:.1f} tokens/word)"
        )
        console.print(
            f"  Least Token Efficient: [cyan]{least_efficient[0]['model']}[/cyan] ({least_efficient[1]:.1f} tokens/word, {least_efficient[1] / most_efficient[1]:.1f}x overhead)"
        )

        # Most verbose
        most_words = max(successful, key=lambda x: x["avg_word_count"])
        console.print(
            f"  Most Verbose: [cyan]{most_words['model']}[/cyan] ({most_words['avg_word_count']:.0f} words avg)"
        )

        # Cheapest
        cheapest = min(successful, key=lambda x: x["avg_cost"])
        console.print(
            f"  Cheapest: [cyan]{cheapest['model']}[/cyan] (${cheapest['avg_cost']:.6f} avg)"
        )

        # Most consistent (smallest time variance)
        time_variances = [
            (r, r["max_elapsed_seconds"] - r["min_elapsed_seconds"]) for r in successful
        ]
        most_consistent = min(time_variances, key=lambda x: x[1])
        console.print(
            f"  Most Consistent: [cyan]{most_consistent[0]['model']}[/cyan] (±{most_consistent[1]:.2f}s variance)"
        )


def save_results(results: list[dict[str, Any]], output_file: Path) -> None:
    """Save detailed results to JSON file."""
    output = {
        "timestamp": datetime.now().isoformat(),
        "results": results,
    }

    with open(output_file, "w") as f:
        json.dump(output, f, indent=2)

    console.print(f"\n[green]Detailed results saved to: {output_file}[/green]")


def main():
    """Run model comparison."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Compare AI models for article generation"
    )
    parser.add_argument(
        "--models",
        nargs="+",
        default=["gpt-5-nano", "gpt-5-mini", "gpt-5.1", "gpt-4o-mini", "gpt-4o"],
        help="Models to compare (viable models only, excluding codex variants)",
    )
    parser.add_argument(
        "--prompt",
        default="Write a 200-word technical article about Python type hints. Include practical examples and explain why they're useful.",
        help="Prompt to use for testing",
    )
    parser.add_argument(
        "--output",
        default="data/model_comparison.json",
        help="Output file for detailed results",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.7,
        help="Temperature for generation",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=10,
        help="Number of test iterations per model (default: 10)",
    )
    parser.add_argument(
        "--parallel",
        type=int,
        default=8,
        help="Number of parallel workers (default: 8, max: 16 for your 16-core CPU)",
    )

    args = parser.parse_args()

    config = get_config()
    client = OpenAI(api_key=config.openai_api_key)

    console.print("[bold]Model Comparison Tool[/bold]")
    console.print(
        f"Testing {len(args.models)} models with {args.iterations} iterations each..."
    )
    console.print(f"Parallel execution: {args.parallel} workers")
    console.print(f"[dim]Prompt: {args.prompt[:100]}...[/dim]\n")

    all_results = {model: [] for model in args.models}

    # Calculate total tests
    total_tests = len(args.models) * args.iterations

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        main_task = progress.add_task(
            f"Running {total_tests} tests...", total=total_tests
        )

        # Create all test jobs
        test_jobs = []
        for iteration in range(args.iterations):
            for model in args.models:
                test_jobs.append((model, iteration))

        # Run tests in parallel
        with ThreadPoolExecutor(max_workers=args.parallel) as executor:
            # Submit all jobs
            future_to_job = {
                executor.submit(
                    test_model, client, model, args.prompt, args.temperature
                ): (model, iteration)
                for model, iteration in test_jobs
            }

            # Collect results as they complete
            for future in as_completed(future_to_job):
                model, iteration = future_to_job[future]
                try:
                    result = future.result()
                    all_results[model].append(result)
                    progress.advance(main_task)
                except Exception as e:
                    console.print(
                        f"[red]Error testing {model} iteration {iteration}: {e}[/red]"
                    )
                    progress.advance(main_task)

    # Aggregate results
    console.print("\n[bold]Aggregating results...[/bold]")
    aggregated_results = []

    for model in args.models:
        model_runs = all_results[model]
        successful_runs = [r for r in model_runs if r["success"]]

        if not successful_runs:
            # All failed
            aggregated_results.append(
                {
                    "model": model,
                    "success": False,
                    "iterations": args.iterations,
                    "error": "All iterations failed",
                }
            )
            continue

        # Calculate statistics
        aggregated = {
            "model": model,
            "success": True,
            "iterations": args.iterations,
            "successful_iterations": len(successful_runs),
            "avg_content_length": sum(r["content_length"] for r in successful_runs)
            / len(successful_runs),
            "avg_word_count": sum(r["word_count"] for r in successful_runs)
            / len(successful_runs),
            "avg_input_tokens": sum(r["input_tokens"] for r in successful_runs)
            / len(successful_runs),
            "avg_output_tokens": sum(r["output_tokens"] for r in successful_runs)
            / len(successful_runs),
            "avg_total_tokens": sum(r["total_tokens"] for r in successful_runs)
            / len(successful_runs),
            "avg_cost": sum(r["cost"] for r in successful_runs) / len(successful_runs),
            "avg_elapsed_seconds": sum(r["elapsed_seconds"] for r in successful_runs)
            / len(successful_runs),
            "min_elapsed_seconds": min(r["elapsed_seconds"] for r in successful_runs),
            "max_elapsed_seconds": max(r["elapsed_seconds"] for r in successful_runs),
            "min_cost": min(r["cost"] for r in successful_runs),
            "max_cost": max(r["cost"] for r in successful_runs),
            "min_word_count": min(r["word_count"] for r in successful_runs),
            "max_word_count": max(r["word_count"] for r in successful_runs),
            "sample_content": successful_runs[0]["content"],  # Save one example
            "all_runs": model_runs,  # Keep detailed data
        }
        aggregated_results.append(aggregated)

    results = aggregated_results  # For display function compatibility

    # Show preview of content
    # if result["success"] and result["content"]:
    #     preview = result["content"][:150].replace("\n", " ")
    #     console.print(f"  Preview: {preview}...\n")

    display_results(results)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    save_results(results, output_path)

    # Print content samples if requested
    console.print(
        "\n[bold]Would you like to see full content samples? (Saved in JSON)[/bold]"
    )


if __name__ == "__main__":
    main()
