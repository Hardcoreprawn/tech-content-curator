#!/usr/bin/env python3
"""Update config.py based on evaluation results."""

import json
from pathlib import Path

from rich.console import Console

console = Console()


def update_config(eval_dir: Path):
    """Update config.py with recommended model configuration."""

    # Load AB test results
    ab_test = json.load(open(eval_dir / "ab-test-results.json"))

    # Find best configuration
    ab_configs = ab_test.get("configs", {})
    successful_configs = {k: v for k, v in ab_configs.items() if v.get("success")}

    if not successful_configs:
        console.print("[red]No successful configurations found![/red]")
        return

    best_config_name, best_config_data = min(
        successful_configs.items(), key=lambda x: x[1]["avg_total_cost"]
    )

    recommended_config = best_config_data["config"]

    console.print(f"[bold]Best Configuration:[/bold] {best_config_name}")
    console.print(f"  Content: {recommended_config['content_model']}")
    console.print(f"  Title: {recommended_config['title_model']}")
    console.print(f"  Enrichment: {recommended_config['enrichment_model']}")
    console.print(f"  Review: {recommended_config['review_model']}")
    console.print(f"  Cost: ${best_config_data['avg_total_cost']:.4f}/article")

    # Read current config
    config_file = Path("src/config.py")
    with open(config_file) as f:
        config_content = f.read()

    # Update model assignments in os.getenv() default values
    # Pattern matches: os.getenv("CONTENT_MODEL", "gpt-5-mini")
    import re

    # Update content_model default
    config_content = re.sub(
        r'(content_model=os\.getenv\("CONTENT_MODEL",\s*)"[^"]*"(\))',
        rf'\1"{recommended_config["content_model"]}"\2',
        config_content,
    )

    # Update title_model default
    config_content = re.sub(
        r'(title_model=os\.getenv\("TITLE_MODEL",\s*)"[^"]*"(\))',
        rf'\1"{recommended_config["title_model"]}"\2',
        config_content,
    )

    # Update enrichment_model default
    config_content = re.sub(
        r'(enrichment_model=os\.getenv\("ENRICHMENT_MODEL",\s*)"[^"]*"(\))',
        rf'\1"{recommended_config["enrichment_model"]}"\2',
        config_content,
    )

    # Update review_model default
    config_content = re.sub(
        r'(review_model=os\.getenv\("REVIEW_MODEL",\s*)"[^"]*"(\))',
        rf'\1"{recommended_config["review_model"]}"\2',
        config_content,
    )  # Write updated config
    with open(config_file, "w") as f:
        f.write(config_content)

    console.print(
        f"\n[green]Updated {config_file} with recommended configuration[/green]"
    )


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Update config from evaluation")
    parser.add_argument("--eval-dir", required=True, help="Evaluation directory")

    args = parser.parse_args()

    update_config(Path(args.eval_dir))


if __name__ == "__main__":
    main()
