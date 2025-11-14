#!/usr/bin/env python3
"""Probe OpenAI models to detect their parameter capabilities.

This script systematically tests which parameters each model supports
by making minimal API calls and analyzing error messages. The results
can be used to automatically generate MODEL_CONFIGS entries.

Strategy:
1. Test each parameter individually with minimal tokens
2. Detect unsupported parameters from error messages
3. Infer parameter name mappings (max_tokens vs max_completion_tokens)
4. Generate complete capability profile for each model

Usage:
    # Probe a single model
    python probe_model_capabilities.py --model gpt-6-mini

    # Probe all new models from discovery
    python probe_model_capabilities.py --from-discovery

    # Generate MODEL_CONFIGS code
    python probe_model_capabilities.py --model gpt-6-mini --generate-config
"""

import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from openai import OpenAI
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from src.config import get_config

console = Console()


@dataclass
class ParameterProbe:
    """Result of probing a single parameter."""

    param_name: str
    supported: bool
    error_message: str | None = None
    actual_api_name: str | None = None  # e.g., max_completion_tokens
    tested_value: Any = None


@dataclass
class ModelCapabilities:
    """Complete capability profile for a model."""

    model_id: str
    timestamp: str
    prefix: str  # Detected prefix (e.g., "gpt-6")
    supported_params: dict[str, str] = field(
        default_factory=dict
    )  # our_name -> api_name
    unsupported_params: list[str] = field(default_factory=list)
    parameter_probes: list[ParameterProbe] = field(default_factory=list)
    suggested_fallback: str | None = None


# Parameters to test with their test values
PARAMETERS_TO_TEST = {
    "max_tokens": 10,  # Minimal token count
    "temperature": 0.7,
    "top_p": 0.9,
    "frequency_penalty": 0.0,
    "presence_penalty": 0.0,
    "seed": 12345,
    "stop": ["END"],
    "logprobs": True,
    "top_logprobs": 1,
}

# Alternative parameter names to test (for max_tokens -> max_completion_tokens)
PARAMETER_ALTERNATIVES = {
    "max_tokens": ["max_tokens", "max_completion_tokens"],
}

# Minimal test message to reduce costs
TEST_MESSAGE = [{"role": "user", "content": "Hi"}]


def probe_parameter(
    client: OpenAI, model: str, param_name: str, param_value: Any
) -> ParameterProbe:
    """Test if a model supports a specific parameter.

    Args:
        client: OpenAI client
        model: Model ID to test
        param_name: Parameter name (our standard name)
        param_value: Value to test with

    Returns:
        ParameterProbe with results
    """
    # Try standard parameter name first
    api_names_to_try = PARAMETER_ALTERNATIVES.get(param_name, [param_name])

    for api_name in api_names_to_try:
        try:
            params = {
                "model": model,
                "messages": TEST_MESSAGE,
                api_name: param_value,
            }

            # Make minimal API call
            response = client.chat.completions.create(**params)

            # Success! Parameter is supported
            return ParameterProbe(
                param_name=param_name,
                supported=True,
                actual_api_name=api_name,
                tested_value=param_value,
            )

        except Exception as e:
            error_msg = str(e).lower()

            # Check if this is an "unsupported parameter" error
            if any(
                keyword in error_msg
                for keyword in [
                    "unsupported",
                    "does not support",
                    "not supported",
                    "unexpected",
                    "invalid",
                ]
            ):
                # Try next alternative name if available
                if api_name == api_names_to_try[-1]:
                    # Last alternative failed - parameter not supported
                    return ParameterProbe(
                        param_name=param_name,
                        supported=False,
                        error_message=str(e),
                        tested_value=param_value,
                    )
                continue  # Try next alternative
            else:
                # Different error - might be model issue, not parameter issue
                console.print(
                    f"  [yellow]Warning: Unexpected error for {api_name}: {e}[/yellow]"
                )
                return ParameterProbe(
                    param_name=param_name,
                    supported=False,
                    error_message=f"Unexpected error: {str(e)}",
                    tested_value=param_value,
                )

    # Should not reach here
    return ParameterProbe(
        param_name=param_name,
        supported=False,
        error_message="All alternatives failed",
        tested_value=param_value,
    )


def probe_model(client: OpenAI, model_id: str) -> ModelCapabilities:
    """Probe a model to detect all its parameter capabilities.

    Args:
        client: OpenAI client
        model_id: Model ID to probe

    Returns:
        Complete ModelCapabilities profile
    """
    console.print(f"\n[bold]Probing model: {model_id}[/bold]")

    # Detect prefix (first part before version/variant)
    # e.g., "gpt-6-mini" -> "gpt-6", "o4-preview" -> "o4"
    parts = model_id.split("-")
    if len(parts) >= 2:
        prefix = f"{parts[0]}-{parts[1]}"
    else:
        prefix = parts[0]

    capabilities = ModelCapabilities(
        model_id=model_id,
        timestamp=datetime.now().isoformat(),
        prefix=prefix,
    )

    # Test each parameter
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task(
            f"Testing parameters...", total=len(PARAMETERS_TO_TEST)
        )

        for param_name, test_value in PARAMETERS_TO_TEST.items():
            progress.update(task, description=f"Testing {param_name}...")

            probe = probe_parameter(client, model_id, param_name, test_value)
            capabilities.parameter_probes.append(probe)

            if probe.supported:
                api_name = probe.actual_api_name or param_name
                capabilities.supported_params[param_name] = api_name
                console.print(f"  ✅ {param_name} -> {api_name}")
            else:
                capabilities.unsupported_params.append(param_name)
                console.print(f"  ❌ {param_name}: {probe.error_message[:60]}...")

            progress.advance(task)
            time.sleep(0.5)  # Rate limiting

    # Always support messages
    capabilities.supported_params["messages"] = "messages"

    # Suggest fallback based on prefix similarity
    capabilities.suggested_fallback = suggest_fallback(model_id)

    return capabilities


def suggest_fallback(model_id: str) -> str | None:
    """Suggest a fallback model based on prefix and capabilities.

    Args:
        model_id: Model to find fallback for

    Returns:
        Suggested fallback model ID or None
    """
    # Simple heuristic: map to most similar stable model
    if model_id.startswith("gpt-6"):
        return "gpt-5.1" if "mini" not in model_id else "gpt-4o-mini"
    elif model_id.startswith("gpt-7"):
        return "gpt-6" if "mini" not in model_id else "gpt-6-mini"
    elif model_id.startswith("o4"):
        return "o3-mini"
    elif model_id.startswith("o5"):
        return "o4-mini"
    else:
        return "gpt-4o"  # Safe default


def generate_model_config_code(capabilities: ModelCapabilities) -> str:
    """Generate Python code for MODEL_CONFIGS entry.

    Args:
        capabilities: Probed capabilities

    Returns:
        Python code string
    """
    code = []
    code.append("    {")
    code.append(f'        "prefix": "{capabilities.prefix}",')
    code.append('        "param_map": {')

    # Add supported parameters
    for our_name, api_name in sorted(capabilities.supported_params.items()):
        code.append(f'            "{our_name}": "{api_name}",')

    code.append("        },")
    code.append('        "unsupported": [')

    # Add unsupported parameters
    for param_name in sorted(capabilities.unsupported_params):
        code.append(f'            "{param_name}",')

    code.append("        ],")
    code.append("    },")

    return "\n".join(code)


def generate_fallback_code(capabilities: ModelCapabilities) -> str:
    """Generate Python code for fallback mapping.

    Args:
        capabilities: Probed capabilities

    Returns:
        Python code string
    """
    if not capabilities.suggested_fallback:
        return ""

    model_id = capabilities.model_id
    fallback = capabilities.suggested_fallback

    code = []
    code.append(f'    "{model_id}": "{fallback}",')

    # Add common variants
    if "-mini" in model_id:
        base = model_id.replace("-mini", "")
        code.append(f'    "{base}": "{fallback.replace("-mini", "")}",')

    return "\n".join(code)


def display_results(capabilities: ModelCapabilities):
    """Display probe results in a formatted table.

    Args:
        capabilities: Probed capabilities
    """
    console.print(f"\n[bold cyan]Results for {capabilities.model_id}[/bold cyan]\n")

    table = Table(show_header=True)
    table.add_column("Parameter", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("API Name", style="yellow")
    table.add_column("Notes")

    for probe in capabilities.parameter_probes:
        status = "✅ Supported" if probe.supported else "❌ Unsupported"
        api_name = probe.actual_api_name or "-"
        notes = probe.error_message[:40] + "..." if probe.error_message else ""

        table.add_row(probe.param_name, status, api_name, notes)

    console.print(table)

    console.print(f"\n[bold]Detected Prefix:[/bold] {capabilities.prefix}")
    console.print(
        f"[bold]Supported Parameters:[/bold] {len(capabilities.supported_params)}"
    )
    console.print(
        f"[bold]Unsupported Parameters:[/bold] {len(capabilities.unsupported_params)}"
    )

    if capabilities.suggested_fallback:
        console.print(
            f"[bold]Suggested Fallback:[/bold] {capabilities.suggested_fallback}"
        )


def save_capabilities(capabilities: ModelCapabilities, output_dir: Path):
    """Save capabilities to JSON file.

    Args:
        capabilities: Probed capabilities
        output_dir: Directory to save to
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Convert to dict for JSON serialization
    data = {
        "model_id": capabilities.model_id,
        "timestamp": capabilities.timestamp,
        "prefix": capabilities.prefix,
        "supported_params": capabilities.supported_params,
        "unsupported_params": capabilities.unsupported_params,
        "suggested_fallback": capabilities.suggested_fallback,
        "parameter_probes": [
            {
                "param_name": p.param_name,
                "supported": p.supported,
                "error_message": p.error_message,
                "actual_api_name": p.actual_api_name,
                "tested_value": str(p.tested_value),
            }
            for p in capabilities.parameter_probes
        ],
    }

    filename = f"capabilities_{capabilities.model_id.replace('.', '_')}.json"
    output_file = output_dir / filename

    with open(output_file, "w") as f:
        json.dump(data, f, indent=2)

    console.print(f"\n[green]Saved capabilities to: {output_file}[/green]")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Probe model parameter capabilities")
    parser.add_argument("--model", help="Model ID to probe")
    parser.add_argument(
        "--from-discovery",
        action="store_true",
        help="Probe all new models from latest discovery",
    )
    parser.add_argument(
        "--generate-config",
        action="store_true",
        help="Generate MODEL_CONFIGS code",
    )
    parser.add_argument(
        "--output-dir",
        default="data/model-capabilities",
        help="Directory for output files",
    )

    args = parser.parse_args()

    config = get_config()
    client = OpenAI(api_key=config.openai_api_key)

    models_to_probe = []

    if args.model:
        models_to_probe.append(args.model)
    elif args.from_discovery:
        # Load latest discovery results
        discovery_file = Path("data/models-discovered.json")
        if discovery_file.exists():
            with open(discovery_file) as f:
                discovery = json.load(f)
                models_to_probe.extend(discovery.get("new_models", []))
        else:
            console.print(
                "[red]No discovery file found. Run discover_models.py first.[/red]"
            )
            return
    else:
        console.print("[red]Specify --model or --from-discovery[/red]")
        return

    if not models_to_probe:
        console.print("[yellow]No models to probe[/yellow]")
        return

    console.print(f"[bold]Probing {len(models_to_probe)} model(s)[/bold]")

    output_dir = Path(args.output_dir)
    all_capabilities = []

    for model_id in models_to_probe:
        try:
            capabilities = probe_model(client, model_id)
            display_results(capabilities)
            save_capabilities(capabilities, output_dir)
            all_capabilities.append(capabilities)

            if args.generate_config:
                console.print("\n[bold]Generated MODEL_CONFIGS entry:[/bold]")
                console.print(generate_model_config_code(capabilities))

                console.print("\n[bold]Generated Fallback mapping:[/bold]")
                console.print(generate_fallback_code(capabilities))

        except Exception as e:
            console.print(f"[red]Failed to probe {model_id}: {e}[/red]")

    console.print(
        f"\n[green]Probed {len(all_capabilities)} model(s) successfully[/green]"
    )


if __name__ == "__main__":
    main()
