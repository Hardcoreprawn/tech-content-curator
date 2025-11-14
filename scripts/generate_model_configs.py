#!/usr/bin/env python3
"""Generate MODEL_CONFIGS code from probed model capabilities.

This script reads capability probe results and generates Python code
that can be added to src/utils/openai_client.py.

Usage:
    # Generate code for all probed models
    python generate_model_configs.py

    # Generate code for specific model
    python generate_model_configs.py --model gpt-6-mini

    # Output to file instead of console
    python generate_model_configs.py --output model_configs_new.py
"""

import json
from pathlib import Path

from rich.console import Console
from rich.syntax import Syntax

console = Console()


def load_capabilities(capabilities_dir: Path) -> list[dict]:
    """Load all capability probe results.

    Args:
        capabilities_dir: Directory containing capability JSON files

    Returns:
        List of capability dicts
    """
    capabilities = []

    if not capabilities_dir.exists():
        console.print(f"[red]Directory not found: {capabilities_dir}[/red]")
        return capabilities

    for json_file in capabilities_dir.glob("capabilities_*.json"):
        with open(json_file) as f:
            capabilities.append(json.load(f))

    return capabilities


def generate_model_configs(capabilities_list: list[dict]) -> str:
    """Generate MODEL_CONFIGS Python code.

    Args:
        capabilities_list: List of capability dicts

    Returns:
        Python code string
    """
    lines = []
    lines.append("# Model family configurations - add new models here")
    lines.append("MODEL_CONFIGS: list[ModelConfig] = [")

    for cap in capabilities_list:
        lines.append("    {")
        lines.append(f'        "prefix": "{cap["prefix"]}",')
        lines.append('        "param_map": {')

        # Add supported parameters
        for our_name, api_name in sorted(cap["supported_params"].items()):
            lines.append(f'            "{our_name}": "{api_name}",')

        lines.append("        },")
        lines.append('        "unsupported": [')

        # Add unsupported parameters
        for param_name in sorted(cap["unsupported_params"]):
            lines.append(f'            "{param_name}",')

        lines.append("        ],")
        lines.append("    },")

    lines.append("]")

    return "\n".join(lines)


def generate_fallback_mappings(capabilities_list: list[dict]) -> str:
    """Generate GPT fallback mappings.

    Args:
        capabilities_list: List of capability dicts

    Returns:
        Python code string
    """
    lines = []
    lines.append("# Model fallback mappings (for empty response handling)")
    lines.append("MODEL_FALLBACK: dict[str, str] = {")

    for cap in capabilities_list:
        if cap.get("suggested_fallback"):
            model_id = cap["model_id"]
            fallback = cap["suggested_fallback"]

            lines.append(f'    "{model_id}": "{fallback}",')

            # Add common variants
            if "-mini" in model_id:
                base = model_id.replace("-mini", "")
                fallback_base = fallback.replace("-mini", "")
                lines.append(f'    "{base}": "{fallback_base}",')

    lines.append("}")

    return "\n".join(lines)


def generate_update_instructions(capabilities_list: list[dict]) -> str:
    """Generate human-readable update instructions.

    Args:
        capabilities_list: List of capability dicts

    Returns:
        Markdown formatted instructions
    """
    lines = []
    lines.append("# Model Configuration Update Instructions\n")
    lines.append(f"Generated from {len(capabilities_list)} probed model(s)\n")

    for cap in capabilities_list:
        lines.append(f"## {cap['model_id']}\n")
        lines.append(f"**Detected at:** {cap['timestamp']}")
        lines.append(f"**Prefix:** `{cap['prefix']}`")
        lines.append(f"**Supported params:** {len(cap['supported_params'])}")
        lines.append(f"**Unsupported params:** {len(cap['unsupported_params'])}")

        if cap.get("suggested_fallback"):
            lines.append(f"**Suggested fallback:** `{cap['suggested_fallback']}`")

        lines.append("\n**Parameter Support:**")

        # Group parameters
        supported = sorted(cap["supported_params"].items())
        unsupported = sorted(cap["unsupported_params"])

        if supported:
            lines.append("\n*Supported:*")
            for our_name, api_name in supported:
                arrow = f" → `{api_name}`" if our_name != api_name else ""
                lines.append(f"- `{our_name}`{arrow}")

        if unsupported:
            lines.append("\n*Unsupported:*")
            for param in unsupported:
                lines.append(f"- `{param}`")

        lines.append("\n---\n")

    lines.append("## Integration Steps\n")
    lines.append("1. **Review** the generated MODEL_CONFIGS code above")
    lines.append("2. **Add** new entries to `src/utils/openai_client.py`")
    lines.append("3. **Update** MODEL_FALLBACK mappings")
    lines.append(
        "4. **Test** with `python scripts/compare_models.py --model <new-model>`"
    )
    lines.append("5. **Run** full evaluation: `python scripts/ab_test_models.py`")

    return "\n".join(lines)


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate MODEL_CONFIGS from capability probes"
    )
    parser.add_argument(
        "--capabilities-dir",
        default="data/model-capabilities",
        help="Directory with capability JSON files",
    )
    parser.add_argument(
        "--model",
        help="Generate code for specific model only",
    )
    parser.add_argument(
        "--output",
        help="Output file (default: print to console)",
    )
    parser.add_argument(
        "--format",
        choices=["python", "markdown", "both"],
        default="both",
        help="Output format",
    )

    args = parser.parse_args()

    # Load capabilities
    capabilities_dir = Path(args.capabilities_dir)
    capabilities_list = load_capabilities(capabilities_dir)

    if not capabilities_list:
        console.print(
            "[yellow]No capability data found. Run probe_model_capabilities.py first.[/yellow]"
        )
        return

    # Filter by model if specified
    if args.model:
        capabilities_list = [
            c for c in capabilities_list if c["model_id"] == args.model
        ]
        if not capabilities_list:
            console.print(f"[red]No capability data found for {args.model}[/red]")
            return

    console.print(
        f"\n[bold]Generating code for {len(capabilities_list)} model(s)[/bold]\n"
    )

    # Generate code
    output_lines = []

    if args.format in ("python", "both"):
        model_configs_code = generate_model_configs(capabilities_list)
        fallback_code = generate_fallback_mappings(capabilities_list)

        output_lines.append("# " + "=" * 78)
        output_lines.append("# MODEL_CONFIGS - Add these to src/utils/openai_client.py")
        output_lines.append("# " + "=" * 78)
        output_lines.append("")
        output_lines.append(model_configs_code)
        output_lines.append("")
        output_lines.append("")
        output_lines.append("# " + "=" * 78)
        output_lines.append(
            "# FALLBACK MAPPINGS - Add these to src/utils/openai_client.py"
        )
        output_lines.append("# " + "=" * 78)
        output_lines.append("")
        output_lines.append(fallback_code)
        output_lines.append("")

    if args.format in ("markdown", "both"):
        if args.format == "both":
            output_lines.append("\n\n")

        instructions = generate_update_instructions(capabilities_list)
        output_lines.append(instructions)

    output = "\n".join(output_lines)

    # Output
    if args.output:
        output_file = Path(args.output)
        output_file.write_text(output)
        console.print(f"[green]Generated code saved to: {output_file}[/green]")
    else:
        # Print to console with syntax highlighting if Python code
        if args.format == "python":
            syntax = Syntax(output, "python", theme="monokai", line_numbers=True)
            console.print(syntax)
        else:
            console.print(output)


if __name__ == "__main__":
    main()
