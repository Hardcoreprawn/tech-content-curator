#!/usr/bin/env python3
"""Validate and clean mermaid diagrams in markdown files.

Uses mermaid-cli (mmdc) to validate syntax and removes invalid diagrams.
Ensures diagrams match the mermaid@11.12.1 version used in the site.

Installation:
    npm install -g @mermaid-js/mermaid-cli@11.12.1

This ensures the CLI validator matches the browser version exactly.
"""

import logging
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from rich.console import Console

console = Console()
logger = logging.getLogger(__name__)


def check_mermaid_cli() -> bool:
    """Check if mermaid-cli (mmdc) is installed.

    Returns:
        True if mmdc is available, False otherwise
    """
    try:
        result = subprocess.run(
            ["mmdc", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            console.print(
                f"[green]✓[/green] Found mermaid-cli: {result.stdout.strip()}"
            )
            return True
        return False
    except FileNotFoundError:
        console.print("[yellow]⚠[/yellow] mermaid-cli (mmdc) not found")
        console.print("Install with: npm install -g @mermaid-js/mermaid-cli@11.12.1")
        console.print(
            "(Must match mermaid version in site/layouts/partials/extend_head.html)"
        )
        return False
    except Exception as e:
        logger.warning(f"Failed to check mermaid-cli: {e}")
        return False


def extract_mermaid_blocks(content: str) -> list[tuple[str, int, int]]:
    """Extract mermaid code blocks from markdown content.

    Args:
        content: Markdown content

    Returns:
        List of tuples: (diagram_code, start_pos, end_pos)
    """
    pattern = r"```mermaid\n(.*?)```"
    blocks = []

    for match in re.finditer(pattern, content, re.DOTALL):
        diagram_code = match.group(1).strip()
        start_pos = match.start()
        end_pos = match.end()
        blocks.append((diagram_code, start_pos, end_pos))

    return blocks


def validate_mermaid_syntax(diagram_code: str) -> tuple[bool, str]:
    """Validate mermaid diagram syntax using mmdc.

    Args:
        diagram_code: Mermaid diagram syntax

    Returns:
        Tuple of (is_valid, error_message)
    """
    # Create temporary file with diagram
    with tempfile.NamedTemporaryFile(mode="w", suffix=".mmd", delete=False) as f:
        f.write(diagram_code)
        temp_input = Path(f.name)

    try:
        # Create temporary output file
        temp_output = temp_input.with_suffix(".svg")

        # Run mmdc to validate and render
        result = subprocess.run(
            [
                "mmdc",
                "-i",
                str(temp_input),
                "-o",
                str(temp_output),
                "-t",
                "default",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )

        # Clean up
        temp_input.unlink(missing_ok=True)
        temp_output.unlink(missing_ok=True)

        if result.returncode == 0:
            return (True, "")
        else:
            error_msg = result.stderr or result.stdout or "Unknown error"
            return (False, error_msg.strip())

    except subprocess.TimeoutExpired:
        temp_input.unlink(missing_ok=True)
        return (False, "Validation timeout - diagram too complex")
    except Exception as e:
        temp_input.unlink(missing_ok=True)
        return (False, str(e))


def validate_and_clean_article(
    article_path: Path, dry_run: bool = False
) -> tuple[int, int]:
    """Validate mermaid diagrams in an article and optionally remove invalid ones.

    Args:
        article_path: Path to markdown file
        dry_run: If True, only report issues without modifying file

    Returns:
        Tuple of (total_diagrams, invalid_diagrams)
    """
    content = article_path.read_text(encoding="utf-8")
    blocks = extract_mermaid_blocks(content)

    if not blocks:
        return (0, 0)

    console.print(f"\n[blue]Checking {article_path.name}...[/blue]")
    console.print(f"  Found {len(blocks)} mermaid diagram(s)")

    invalid_blocks = []
    for i, (diagram_code, start_pos, end_pos) in enumerate(blocks, 1):
        console.print(f"\n  [dim]Diagram {i}/{len(blocks)}...[/dim]")

        is_valid, error_msg = validate_mermaid_syntax(diagram_code)

        if is_valid:
            console.print("  [green]✓[/green] Valid")
        else:
            console.print(f"  [red]✗[/red] Invalid: {error_msg[:100]}")
            invalid_blocks.append((start_pos, end_pos, error_msg))

    # Remove invalid diagrams if not dry run
    if invalid_blocks and not dry_run:
        console.print(
            f"\n  [yellow]Removing {len(invalid_blocks)} invalid diagram(s)...[/yellow]"
        )

        # Remove blocks in reverse order to maintain positions
        new_content = content
        for start_pos, end_pos, error_msg in reversed(invalid_blocks):
            # Replace with a comment explaining the removal
            comment = f"<!-- Mermaid diagram removed due to syntax error: {error_msg[:200]} -->\n"
            new_content = new_content[:start_pos] + comment + new_content[end_pos:]

        # Save updated content
        article_path.write_text(new_content, encoding="utf-8")
        console.print(f"  [green]✓[/green] Updated {article_path.name}")

    return (len(blocks), len(invalid_blocks))


def main() -> int:
    """Validate and clean mermaid diagrams in all articles."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Validate and clean mermaid diagrams in markdown files"
    )
    parser.add_argument(
        "paths",
        nargs="*",
        help="Specific files to check (default: all articles in content/posts/)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only report issues without modifying files",
    )

    args = parser.parse_args()

    # Check if mmdc is installed
    if not check_mermaid_cli():
        return 1

    # Get files to check
    if args.paths:
        files = [Path(p) for p in args.paths]
    else:
        content_dir = Path("content/posts")
        if not content_dir.exists():
            console.print(f"[red]Error: {content_dir} not found[/red]")
            return 1
        files = list(content_dir.glob("*.md"))

    console.print(f"\n[bold]Checking {len(files)} file(s)...[/bold]")
    if args.dry_run:
        console.print("[yellow]DRY RUN - no files will be modified[/yellow]")

    total_diagrams = 0
    total_invalid = 0

    for article_path in files:
        try:
            diagrams, invalid = validate_and_clean_article(article_path, args.dry_run)
            total_diagrams += diagrams
            total_invalid += invalid
        except Exception as e:
            console.print(f"[red]✗[/red] Error processing {article_path.name}: {e}")
            logger.exception(f"Failed to process {article_path}")

    console.print("\n[bold]Summary:[/bold]")
    console.print(f"  Total diagrams: {total_diagrams}")
    console.print(f"  Invalid diagrams: {total_invalid}")

    if total_invalid > 0:
        if args.dry_run:
            console.print(
                "\n[yellow]Run without --dry-run to remove invalid diagrams[/yellow]"
            )
        else:
            console.print(
                f"\n[green]✓ Removed {total_invalid} invalid diagrams[/green]"
            )

    return 0 if total_invalid == 0 else 1


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    sys.exit(main())
