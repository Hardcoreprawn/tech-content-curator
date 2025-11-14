#!/usr/bin/env python3
"""Discover available models from OpenAI API and probe their capabilities."""

import json
from datetime import datetime
from pathlib import Path

from openai import OpenAI
from rich.console import Console

from src.config import get_config

console = Console()


def probe_new_models(client: OpenAI, new_models: list[str], output_dir: Path) -> dict:
    """Probe capabilities of new models.

    Args:
        client: OpenAI client
        new_models: List of new model IDs to probe
        output_dir: Directory to save capability results

    Returns:
        Dict mapping model_id to capabilities summary
    """
    if not new_models:
        return {}

    console.print("\n[bold yellow]Probing capabilities of new models...[/bold yellow]")

    # Import probe function (avoid circular import)
    try:
        from probe_model_capabilities import probe_model, save_capabilities
    except ImportError:
        console.print(
            "[red]Could not import probe_model_capabilities. Skipping probing.[/red]"
        )
        return {}

    capabilities_summary = {}

    for model_id in new_models:
        try:
            console.print(f"\n[cyan]Probing {model_id}...[/cyan]")
            capabilities = probe_model(client, model_id)
            save_capabilities(capabilities, output_dir)

            # Store summary
            capabilities_summary[model_id] = {
                "prefix": capabilities.prefix,
                "supported_count": len(capabilities.supported_params),
                "unsupported_count": len(capabilities.unsupported_params),
                "suggested_fallback": capabilities.suggested_fallback,
            }

            console.print(f"[green]✓ Probed {model_id}[/green]")

        except Exception as e:
            console.print(f"[red]✗ Failed to probe {model_id}: {e}[/red]")
            capabilities_summary[model_id] = {"error": str(e)}

    return capabilities_summary


def discover_models(output_file: Path) -> dict:
    """Query OpenAI API for available models."""
    config = get_config()
    client = OpenAI(api_key=config.openai_api_key)

    console.print("[bold]Discovering available models...[/bold]")

    # Get all models
    models = client.models.list()

    # Filter for GPT models
    gpt_models = [m for m in models.data if m.id.startswith(("gpt-4", "gpt-5"))]

    # Load known models
    known_models_file = Path("data/known-models.json")
    if known_models_file.exists():
        with open(known_models_file) as f:
            known_models = json.load(f)
    else:
        known_models = {"models": [], "last_updated": None}

    known_ids = set(known_models.get("models", []))
    new_models = [m.id for m in gpt_models if m.id not in known_ids]

    result = {
        "timestamp": datetime.now().isoformat(),
        "total_models": len(gpt_models),
        "all_models": [m.id for m in gpt_models],
        "new_models": new_models,
        "known_models": list(known_ids),
    }

    console.print(f"\n[green]Found {len(gpt_models)} GPT models[/green]")
    console.print(f"[cyan]New models: {len(new_models)}[/cyan]")

    if new_models:
        console.print("\n[bold]New models detected:[/bold]")
        for model in new_models:
            console.print(f"  • {model}")

    # Save results
    with open(output_file, "w") as f:
        json.dump(result, f, indent=2)

    # Update known models
    known_models["models"] = [m.id for m in gpt_models]
    known_models["last_updated"] = datetime.now().isoformat()

    known_models_file.parent.mkdir(parents=True, exist_ok=True)
    with open(known_models_file, "w") as f:
        json.dump(known_models, f, indent=2)

    console.print(f"\n[green]Results saved to: {output_file}[/green]")

    return result


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Discover available OpenAI models")
    parser.add_argument(
        "--output",
        default="data/models-discovered.json",
        help="Output file for discovery results",
    )
    parser.add_argument(
        "--probe-new",
        action="store_true",
        help="Probe capabilities of newly discovered models",
    )
    parser.add_argument(
        "--capabilities-dir",
        default="data/model-capabilities",
        help="Directory for capability probe results",
    )

    args = parser.parse_args()

    result = discover_models(Path(args.output))

    # Optionally probe new models
    if args.probe_new and result.get("new_models"):
        config = get_config()
        client = OpenAI(api_key=config.openai_api_key)

        capabilities_dir = Path(args.capabilities_dir)
        capabilities_summary = probe_new_models(
            client, result["new_models"], capabilities_dir
        )

        # Add capabilities to result
        result["capabilities"] = capabilities_summary

        # Re-save result with capabilities
        with open(args.output, "w") as f:
            json.dump(result, f, indent=2)

        console.print(
            f"\n[green]Updated results with capabilities: {args.output}[/green]"
        )


if __name__ == "__main__":
    main()
