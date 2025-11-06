#!/usr/bin/env python3
"""Regenerate illustrations for specific articles.

This script allows regenerating illustrations for existing articles
without regenerating the entire article content. Useful for testing
illustration validators and quality improvements.

Usage:
    python scripts/regenerate_article_illustrations.py \
        --files content/posts/2025-11-03-collatz-weyl-generators.md \
                 content/posts/2025-11-03-oxy-cloudflare-rust-proxy.md
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from openai import OpenAI
from rich.console import Console

from src.config import PipelineConfig, get_config
from src.pipeline.illustration_service import IllustrationService

if TYPE_CHECKING:
    pass

console = Console()
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def extract_frontmatter(content: str) -> tuple[str, str]:
    """Extract YAML frontmatter from markdown content.

    Returns:
        Tuple of (frontmatter_text, markdown_content)
    """
    if not content.startswith("---"):
        return "", content

    # Find the closing ---
    end_index = content.find("\n---\n", 4)
    if end_index == -1:
        return "", content

    frontmatter = content[3:end_index].strip()
    markdown = content[end_index + 5 :].strip()
    return frontmatter, markdown


def remove_existing_diagrams(content: str) -> str:
    """Remove existing mermaid and ASCII diagrams from content.

    Preserves HTML comments about what was removed for reference.
    """
    # Pattern for mermaid diagrams
    mermaid_pattern = r"<!-- MERMAID:.*?-->\s*```mermaid\s*.*?```\s*"
    content = re.sub(mermaid_pattern, "", content, flags=re.DOTALL)

    # Pattern for ASCII diagrams
    ascii_pattern = (
        r"<!-- ASCII:.*?-->\s*<div[^>]*>.*?```.*?```.*?</div>\s*(?:\*Figure:.*?\*\s*)?"
    )
    content = re.sub(ascii_pattern, "", content, flags=re.DOTALL)

    # Pattern for remaining diagram blocks
    diagram_comment_pattern = r"<!-- MERMAID:.*?-->\n*"
    content = re.sub(diagram_comment_pattern, "", content)

    # Clean up multiple newlines
    content = re.sub(r"\n\n\n+", "\n\n", content)

    return content.strip()


def regenerate_illustrations(
    article_file: Path,
    config: PipelineConfig,
    client: OpenAI,
) -> bool:
    """Regenerate illustrations for a single article.

    Args:
        article_file: Path to the markdown article file
        config: Pipeline configuration
        client: OpenAI client

    Returns:
        True if successful, False otherwise
    """
    console.print(f"\n[bold blue]Processing:[/bold blue] {article_file.name}")

    if not article_file.exists():
        console.print(f"[red]✗[/red] File not found: {article_file}")
        return False

    # Read the article
    content = article_file.read_text(encoding="utf-8")
    frontmatter, markdown_content = extract_frontmatter(content)

    if not frontmatter:
        console.print("[yellow]⚠[/yellow] No frontmatter found, skipping")
        return False

    console.print(f"[dim]Content length: {len(markdown_content)} chars[/dim]")

    # Extract generator name from frontmatter
    generator_match = re.search(r"generator:\s*(.+)", frontmatter)
    generator_name = (
        generator_match.group(1).strip()
        if generator_match
        else "General Article Generator"
    )
    console.print(f"[dim]Generator: {generator_name}[/dim]")

    # Remove existing diagrams
    cleaned_content = remove_existing_diagrams(markdown_content)
    if cleaned_content != markdown_content:
        console.print("[dim]Removed existing diagrams[/dim]")

    # Generate new illustrations
    console.print("[dim]Generating new illustrations...[/dim]")
    illustration_service = IllustrationService(client, config)

    try:
        result = illustration_service.generate_illustrations(
            generator_name, cleaned_content
        )

        if result.count > 0:
            console.print(f"[green]✓[/green] Generated {result.count} illustration(s)")
            console.print(f"[dim]Cost: ${result.costs.get('total', 0):.6f}[/dim]")

            # Update frontmatter with new illustration count and costs
            new_frontmatter = re.sub(
                r"illustrations_count:\s*\d+",
                f"illustrations_count: {result.count}",
                frontmatter,
            )

            # Merge costs into frontmatter
            if "generation_costs:" in new_frontmatter:
                # Replace existing generation_costs section
                costs_yaml = _format_costs_yaml(result.costs)
                new_frontmatter = re.sub(
                    r"generation_costs:\s*\n(?:  [^\n]+\n)*",
                    f"generation_costs:\n{costs_yaml}",
                    new_frontmatter,
                )
            else:
                # Add generation_costs section before illustrations_count
                costs_yaml = _format_costs_yaml(result.costs)
                new_frontmatter = re.sub(
                    r"(generator:.+\n)",
                    f"\\1generation_costs:\n{costs_yaml}",
                    new_frontmatter,
                )

            # Reconstruct the file
            updated_content = f"---\n{new_frontmatter}\n---\n\n{result.content}"

            # Write back
            article_file.write_text(updated_content, encoding="utf-8")
            console.print(f"[green]✓[/green] Updated: {article_file.name}")
            return True
        else:
            console.print("[yellow]⚠[/yellow] No illustrations generated")
            return False

    except Exception as e:
        logger.error(f"Illustration generation failed: {e}", exc_info=True)
        console.print(f"[red]✗[/red] Generation failed: {str(e)[:80]}")
        return False


def _format_costs_yaml(costs: dict) -> str:
    """Format costs dictionary as YAML."""
    lines = []
    for key, value in costs.items():
        if isinstance(value, float):
            lines.append(f"  {key}: {value}")
        else:
            lines.append(f"  {key}: {value}")
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(
        description="Regenerate illustrations for specific articles"
    )
    parser.add_argument(
        "--files",
        nargs="+",
        help="Article files to regenerate illustrations for",
        required=True,
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Verbose logging",
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Load config
    config = get_config()
    console.print(
        f"[dim]Config loaded: illustrations enabled = {config.enable_illustrations}[/dim]"
    )

    # Verify OpenAI API key
    api_key = config.openai_api_key
    if not api_key:
        console.print("[red]✗[/red] OpenAI API key not configured")
        return 1

    client = OpenAI(api_key=api_key)

    # Process each file
    successful = 0
    failed = 0

    for file_path in args.files:
        article_file = Path(file_path)
        if regenerate_illustrations(article_file, config, client):
            successful += 1
        else:
            failed += 1

    # Summary
    console.print(f"\n[bold]Summary:[/bold] {successful} successful, {failed} failed")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
