#!/usr/bin/env python3
"""A/B testing framework for comparing model combinations across pipeline roles.

This script tests different model combinations to find the optimal balance of:
- Quality (readability, accuracy, engagement)
- Cost (per article and monthly budget)
- Speed (generation time)

The system can adaptively prune poor-performing combinations and focus testing
on the most promising configurations.

Usage:
    # Test predefined model combinations
    python scripts/ab_test_models.py --iterations 5

    # Test specific combinations
    python scripts/ab_test_models.py --custom-config config.json

    # Adaptive mode: prune poor performers after N iterations
    python scripts/ab_test_models.py --adaptive --prune-after 3 --keep-top 3
"""

import json
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
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


@dataclass
class ModelConfig:
    """Configuration for a model combination."""
    name: str
    content_model: str
    title_model: str
    enrichment_model: str
    review_model: str


# Predefined configurations to test
CONFIGS = [
    # Budget-optimized: All GPT-4o-mini
    ModelConfig(
        name="Budget (All 4o-mini)",
        content_model="gpt-4o-mini",
        title_model="gpt-4o-mini",
        enrichment_model="gpt-4o-mini",
        review_model="gpt-4o-mini",
    ),
    # Mixed: GPT-5 for content, GPT-4 for everything else
    ModelConfig(
        name="Mixed (5.1 content, 4o-mini other)",
        content_model="gpt-5.1",
        title_model="gpt-4o-mini",
        enrichment_model="gpt-4o-mini",
        review_model="gpt-4o-mini",
    ),
    # GPT-5 mini everywhere
    ModelConfig(
        name="GPT-5 Mini (all roles)",
        content_model="gpt-5-mini",
        title_model="gpt-5-mini",
        enrichment_model="gpt-5-mini",
        review_model="gpt-5-mini",
    ),
    # GPT-5.1 for high-value tasks
    ModelConfig(
        name="Selective 5.1 (content & review)",
        content_model="gpt-5.1",
        title_model="gpt-4o-mini",
        enrichment_model="gpt-4o-mini",
        review_model="gpt-5.1",
    ),
    # All GPT-5.1
    ModelConfig(
        name="Premium (All 5.1)",
        content_model="gpt-5.1",
        title_model="gpt-5.1",
        enrichment_model="gpt-5.1",
        review_model="gpt-5.1",
    ),
]


# Simple test prompts for each role
TEST_PROMPTS = {
    "content": """Write a 200-word technical article about Python async/await.
Explain the concept clearly with a practical example.
Target audience: intermediate Python developers.""",

    "title": """Generate a compelling, SEO-friendly title for this article:
[Article about Python async/await covering event loops, coroutines, and practical use cases]
Requirements: 6-10 words, engaging, technical but accessible.""",

    "enrichment": """Add a meta description (150-160 chars) for this article:
Title: "Understanding Python's Async/Await: A Practical Guide"
Content: Technical tutorial covering event loops, coroutines, and real-world examples.""",

    "review": """Review this article for quality issues:
- Technical accuracy
- Clarity and readability
- Code example quality
- Target audience appropriateness

Article: [200-word piece about Python async/await with code examples]
Provide a brief quality score (1-10) and 2-3 key observations.""",
}


# Pricing per 1M tokens (from compare_models.py)
MODEL_PRICING = {
    "gpt-5-nano": {"input": 0.05, "output": 0.40},
    "gpt-5-mini": {"input": 0.25, "output": 2.00},
    "gpt-5": {"input": 1.25, "output": 10.00},
    "gpt-5.1": {"input": 1.50, "output": 12.00},
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
}


def calculate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Calculate cost for a model based on token usage."""
    pricing = None
    for model_prefix, model_pricing in MODEL_PRICING.items():
        if model.startswith(model_prefix):
            pricing = model_pricing
            break

    if not pricing:
        console.print(f"[yellow]Warning: No pricing info for {model}[/yellow]")
        return 0.0

    input_cost = (input_tokens / 1_000_000) * pricing["input"]
    output_cost = (output_tokens / 1_000_000) * pricing["output"]
    return input_cost + output_cost


def test_role(client: OpenAI, model: str, role: str) -> dict[str, Any]:
    """Test a single model in a specific role."""
    prompt = TEST_PROMPTS[role]

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

        return {
            "success": True,
            "model": model,
            "role": role,
            "content": content,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost": cost,
            "elapsed_seconds": elapsed,
            "error": None,
        }

    except Exception as e:
        elapsed = time.time() - start_time
        return {
            "success": False,
            "model": model,
            "role": role,
            "content": "",
            "input_tokens": 0,
            "output_tokens": 0,
            "cost": 0.0,
            "elapsed_seconds": elapsed,
            "error": str(e),
        }


def test_config(client: OpenAI, config: ModelConfig) -> dict[str, Any]:
    """Test a complete model configuration across all roles."""
    results = {
        "config_name": config.name,
        "roles": {},
        "total_cost": 0.0,
        "total_time": 0.0,
        "success": True,
    }

    # Test each role
    for role, model in [
        ("content", config.content_model),
        ("title", config.title_model),
        ("enrichment", config.enrichment_model),
        ("review", config.review_model),
    ]:
        result = test_role(client, model, role)
        results["roles"][role] = result
        results["total_cost"] += result["cost"]
        results["total_time"] += result["elapsed_seconds"]

        if not result["success"]:
            results["success"] = False

    return results


def run_ab_tests(
    client: OpenAI,
    configs: list[ModelConfig],
    iterations: int = 5,
    adaptive: bool = False,
    prune_after: int = 3,
    keep_top: int = 3,
    parallel: int = 8,
) -> dict[str, Any]:
    """Run A/B tests on model configurations.

    Args:
        client: OpenAI client
        configs: List of model configurations to test
        iterations: Number of test iterations per config
        adaptive: Whether to prune poor performers
        prune_after: After how many iterations to prune
        keep_top: How many top performers to keep when pruning
        parallel: Number of parallel workers

    Returns:
        Dictionary with all test results and analysis
    """
    console.print("\n[bold cyan]Starting A/B Test Campaign[/bold cyan]")
    console.print(f"Configurations: {len(configs)}")
    console.print(f"Iterations: {iterations}")
    console.print(f"Parallel workers: {parallel}")
    console.print(f"Adaptive: {'Yes' if adaptive else 'No'}")
    if adaptive:
        console.print(f"Pruning: Keep top {keep_top} after {prune_after} iterations")
    console.print()

    all_results = defaultdict(list)
    active_configs = configs.copy()

    for iteration in range(iterations):
        console.rule(f"[bold]Iteration {iteration + 1}/{iterations}[/bold]")

        # Check if we should prune
        if adaptive and iteration == prune_after and len(active_configs) > keep_top:
            console.print("\n[yellow]Adaptive pruning enabled - analyzing performance...[/yellow]")

            # Calculate average cost for each config
            avg_costs = {}
            for config in active_configs:
                results = all_results[config.name]
                if results:
                    avg_cost = sum(r["total_cost"] for r in results) / len(results)
                    avg_costs[config.name] = avg_cost

            # Keep only top performers
            sorted_configs = sorted(
                active_configs,
                key=lambda c: avg_costs.get(c.name, float("inf"))
            )
            active_configs = sorted_configs[:keep_top]

            console.print(f"[green]Keeping top {keep_top} configurations:[/green]")
            for config in active_configs:
                cost = avg_costs.get(config.name, 0)
                console.print(f"  ✓ {config.name} (${cost:.6f} avg)")

            pruned = {c.name for c in configs} - {c.name for c in active_configs}
            if pruned:
                console.print(f"\n[dim]Pruned: {', '.join(pruned)}[/dim]\n")

        # Test active configs in parallel
        total_roles = len(active_configs) * 4  # 4 roles per config

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
        ) as progress:
            iteration_task = progress.add_task(
                f"Iteration {iteration + 1}/{iterations}",
                total=total_roles
            )

            # Run all configs in parallel
            with ThreadPoolExecutor(max_workers=parallel) as executor:
                future_to_config = {
                    executor.submit(test_config, client, config): config
                    for config in active_configs
                }

                for future in as_completed(future_to_config):
                    config = future_to_config[future]
                    try:
                        result = future.result()
                        all_results[config.name].append(result)

                        # Show brief result
                        status = "✓" if result["success"] else "✗"
                        console.print(
                            f"  {status} {config.name}: "
                            f"${result['total_cost']:.6f}, "
                            f"{result['total_time']:.1f}s"
                        )

                        progress.advance(iteration_task, 4)  # 4 roles completed
                    except Exception as e:
                        console.print(f"[red]Error testing {config.name}: {e}[/red]")
                        progress.advance(iteration_task, 4)

        console.print()

    return aggregate_results(all_results, configs)


def aggregate_results(
    all_results: dict[str, list[dict]],
    configs: list[ModelConfig],
) -> dict[str, Any]:
    """Aggregate test results across iterations."""
    aggregated = {
        "timestamp": datetime.now().isoformat(),
        "configs": {},
    }

    for config in configs:
        results = all_results.get(config.name, [])
        if not results:
            continue

        successful = [r for r in results if r["success"]]

        if not successful:
            aggregated["configs"][config.name] = {
                "success": False,
                "error": "All iterations failed",
            }
            continue

        # Calculate per-role statistics
        role_stats = {}
        for role in ["content", "title", "enrichment", "review"]:
            role_results = [r["roles"][role] for r in successful if role in r["roles"]]
            if role_results:
                role_stats[role] = {
                    "model": role_results[0]["model"],
                    "avg_cost": sum(r["cost"] for r in role_results) / len(role_results),
                    "avg_time": sum(r["elapsed_seconds"] for r in role_results) / len(role_results),
                    "avg_output_tokens": sum(r["output_tokens"] for r in role_results) / len(role_results),
                }

        aggregated["configs"][config.name] = {
            "success": True,
            "iterations": len(results),
            "successful_iterations": len(successful),
            "config": {
                "content_model": config.content_model,
                "title_model": config.title_model,
                "enrichment_model": config.enrichment_model,
                "review_model": config.review_model,
            },
            "avg_total_cost": sum(r["total_cost"] for r in successful) / len(successful),
            "avg_total_time": sum(r["total_time"] for r in successful) / len(successful),
            "min_total_cost": min(r["total_cost"] for r in successful),
            "max_total_cost": max(r["total_cost"] for r in successful),
            "role_breakdown": role_stats,
            "monthly_cost_estimate_270_articles": (
                sum(r["total_cost"] for r in successful) / len(successful) * 270
            ),
        }

    return aggregated


def display_comparison(results: dict[str, Any]) -> None:
    """Display comparison results in a formatted table."""
    console.print("\n[bold]A/B Test Results Summary[/bold]")
    console.print("=" * 120)

    # Main comparison table
    table = Table(title="Model Configuration Comparison")
    table.add_column("Configuration", style="cyan", width=30)
    table.add_column("Success", justify="center")
    table.add_column("Cost/Article", justify="right")
    table.add_column("Time/Article", justify="right")
    table.add_column("Monthly Cost\n(270 articles)", justify="right")
    table.add_column("Content Model", style="dim", width=15)
    table.add_column("Other Models", style="dim", width=15)

    configs = results.get("configs", {})
    successful_configs = {
        name: data for name, data in configs.items() if data.get("success")
    }

    # Sort by cost
    sorted_configs = sorted(
        successful_configs.items(),
        key=lambda x: x[1]["avg_total_cost"],
    )

    for name, data in sorted_configs:
        config = data["config"]

        # Determine if models are uniform
        models = {
            config["content_model"],
            config["title_model"],
            config["enrichment_model"],
            config["review_model"],
        }

        if len(models) == 1:
            other_models = "Same"
        else:
            # Show the most common "other" model
            other_model = config["title_model"]
            other_models = other_model

        table.add_row(
            name,
            f"✓ {data['successful_iterations']}/{data['iterations']}",
            f"${data['avg_total_cost']:.6f}",
            f"{data['avg_total_time']:.1f}s",
            f"${data['monthly_cost_estimate_270_articles']:.2f}",
            config["content_model"],
            other_models,
        )

    console.print(table)

    # Winner analysis
    if sorted_configs:
        console.print("\n[bold]Recommendations:[/bold]")

        # Best value
        best_value = sorted_configs[0]
        console.print(f"  💰 Best Value: [cyan]{best_value[0]}[/cyan]")
        console.print(f"     ${best_value[1]['avg_total_cost']:.6f}/article, "
                     f"${best_value[1]['monthly_cost_estimate_270_articles']:.2f}/month")

        # Fastest
        fastest = min(sorted_configs, key=lambda x: x[1]["avg_total_time"])
        console.print(f"\n  ⚡ Fastest: [cyan]{fastest[0]}[/cyan]")
        console.print(f"     {fastest[1]['avg_total_time']:.1f}s per article")

        # Cost comparison to baseline
        baseline = sorted_configs[0][1]
        console.print("\n[bold]Cost vs Best Value:[/bold]")
        for name, data in sorted_configs[1:]:
            cost_increase = data['avg_total_cost'] / baseline['avg_total_cost']
            monthly_diff = data['monthly_cost_estimate_270_articles'] - baseline['monthly_cost_estimate_270_articles']
            console.print(f"  {name}: {cost_increase:.1f}x more (+${monthly_diff:.2f}/month)")


def save_results(results: dict[str, Any], output_file: Path) -> None:
    """Save detailed results to JSON."""
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)

    console.print(f"\n[green]Results saved to: {output_file}[/green]")


def main():
    """Run A/B testing."""
    import argparse

    parser = argparse.ArgumentParser(
        description="A/B test different model combinations for article generation"
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=5,
        help="Number of test iterations per configuration (default: 5)",
    )
    parser.add_argument(
        "--configs",
        nargs="+",
        choices=["budget", "mixed", "mini", "selective", "premium"],
        help="Specific configurations to test (default: all)",
    )
    parser.add_argument(
        "--adaptive",
        action="store_true",
        help="Enable adaptive pruning of poor performers",
    )
    parser.add_argument(
        "--prune-after",
        type=int,
        default=3,
        help="Iterations before pruning (default: 3)",
    )
    parser.add_argument(
        "--keep-top",
        type=int,
        default=3,
        help="Number of top configs to keep when pruning (default: 3)",
    )
    parser.add_argument(
        "--output",
        default="data/ab_test_results.json",
        help="Output file for results",
    )
    parser.add_argument(
        "--parallel",
        type=int,
        default=8,
        help="Number of parallel workers (default: 8, max: 16 for your CPU)",
    )

    args = parser.parse_args()

    # Select configurations
    config_map = {
        "budget": CONFIGS[0],
        "mixed": CONFIGS[1],
        "mini": CONFIGS[2],
        "selective": CONFIGS[3],
        "premium": CONFIGS[4],
    }

    if args.configs:
        test_configs = [config_map[name] for name in args.configs]
    else:
        test_configs = CONFIGS

    config = get_config()
    client = OpenAI(api_key=config.openai_api_key)

    results = run_ab_tests(
        client,
        test_configs,
        iterations=args.iterations,
        adaptive=args.adaptive,
        prune_after=args.prune_after,
        keep_top=args.keep_top,
        parallel=args.parallel,
    )

    display_comparison(results)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    save_results(results, output_path)

    console.print("\n[bold green]A/B Testing Complete![/bold green]")


if __name__ == "__main__":
    main()
