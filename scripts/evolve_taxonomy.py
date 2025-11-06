#!/usr/bin/env python3
"""AI-managed dynamic taxonomy evolution.

This script analyzes actual content usage and evolves the tag taxonomy:
1. Discovers frequently used tags that aren't canonical
2. Promotes popular tags to canonical status
3. Removes canonical tags with low usage
4. Updates tag mappings based on co-occurrence patterns
5. Uses AI to validate proposed changes

Run monthly or when tag statistics show drift.
"""

import sys
from collections import Counter
from pathlib import Path

import frontmatter
from openai import OpenAI
from rich.console import Console

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import get_config
from src.content.tag_normalizer import (
    CANONICAL_TAGS,
    TAG_MAPPINGS,
    normalize_tag,
)

console = Console()


def analyze_current_usage(content_dir: Path = Path("content/posts")) -> dict:
    """Analyze current tag usage patterns."""
    stats = {
        "raw_tags": Counter(),  # All raw tags from articles
        "normalized_tags": Counter(),  # Normalized tags
        "discarded_tags": Counter(),  # Tags that didn't normalize
        "total_articles": 0,
    }

    for article_path in content_dir.glob("*.md"):
        try:
            post = frontmatter.load(str(article_path))
            tags = post.get("tags", [])
            if not tags:
                continue

            stats["total_articles"] += 1

            # Ensure tags is a list
            if not isinstance(tags, list):
                continue

            for tag in tags:
                stats["raw_tags"][tag] += 1
                normalized = normalize_tag(tag)
                if normalized:
                    stats["normalized_tags"][normalized] += 1
                else:
                    stats["discarded_tags"][tag] += 1

        except Exception as e:
            console.print(f"[yellow]Warning: Could not process {article_path}: {e}")

    return stats


def identify_candidates_for_promotion(
    stats: dict, min_usage: int = 5
) -> list[tuple[str, str, int]]:
    """Find discarded tags used frequently enough to promote to canonical."""
    candidates = []

    for tag, count in stats["discarded_tags"].most_common(50):
        if count >= min_usage:
            # Normalize the tag name (lowercase, hyphens)
            normalized = tag.lower().replace(" ", "-").replace("_", "-")
            candidates.append((normalized, tag, count))

    return candidates


def identify_underused_tags(stats: dict, min_usage: int = 2) -> list[tuple[str, int]]:
    """Find canonical tags that are barely used."""
    underused = []

    for tag in CANONICAL_TAGS:
        usage_count = stats["normalized_tags"].get(tag, 0)
        if usage_count < min_usage:
            underused.append((tag, usage_count))

    return underused


def ask_ai_to_validate_changes(
    promote: list[tuple[str, str, int]],
    remove: list[tuple[str, int]],
    client: OpenAI,
) -> dict:
    """Use AI to validate proposed taxonomy changes."""
    prompt = f"""
You are helping manage a technical blog's tag taxonomy. Review these proposed changes:

TAGS TO PROMOTE (frequently used but not canonical):
{chr(10).join(f"- {norm} (raw: {raw}, used {count}x)" for norm, raw, count in promote[:20])}

TAGS TO REMOVE (canonical but underused):
{chr(10).join(f"- {tag} (used {count}x)" for tag, count in remove[:20])}

For each proposed change, evaluate:
1. Is this a legitimate technical topic worth tracking?
2. Does it fit the blog's focus (software development, tech)?
3. Is it too specific or too generic?
4. Should it be merged with an existing tag instead?

Return JSON with your recommendations:
{{
  "promote": [list of normalized tags to add to canonical list],
  "remove": [list of canonical tags to remove],
  "mappings": {{"variant": "canonical_tag"}} for any new mappings,
  "reasoning": "Brief explanation of your decisions"
}}

Be conservative - only promote tags that will have lasting value.
Remove underused tags that are redundant or too narrow.
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.3,
        )

        import json

        content = response.choices[0].message.content
        if not content:
            raise ValueError("Empty response from AI")

        return json.loads(content)
    except Exception as e:
        console.print(f"[red]AI validation failed: {e}")
        return {"promote": [], "remove": [], "mappings": {}, "reasoning": "Error"}


def generate_updated_taxonomy(
    validated: dict, promote_candidates: list, remove_candidates: list
) -> tuple[set[str], dict[str, str]]:
    """Generate updated canonical tags and mappings."""
    # Start with current canonical tags
    new_canonical = CANONICAL_TAGS.copy()

    # Remove underused tags
    for tag in validated["remove"]:
        if tag in new_canonical:
            new_canonical.discard(tag)
            console.print(f"[yellow]Removing: {tag}")

    # Add promoted tags
    for tag in validated["promote"]:
        new_canonical.add(tag)
        console.print(f"[green]Adding: {tag}")

    # Update mappings
    new_mappings = TAG_MAPPINGS.copy()
    for variant, canonical in validated["mappings"].items():
        if canonical in new_canonical:
            new_mappings[variant] = canonical
            console.print(f"[cyan]Mapping: {variant} -> {canonical}")

    # Add mappings for all promoted tags (map original variants to normalized form)
    for norm_tag, raw_tag, _count in promote_candidates:
        if norm_tag in validated["promote"] and norm_tag != raw_tag.lower():
            new_mappings[raw_tag.lower()] = norm_tag

    return new_canonical, new_mappings


def write_updated_taxonomy_file(canonical: set[str], mappings: dict[str, str]):
    """Write updated taxonomy to tag_normalizer.py"""
    # Read current file
    normalizer_path = Path("src/content/tag_normalizer.py")
    with open(normalizer_path) as f:
        content = f.read()

    # Format canonical tags (sorted for readability)
    canonical_str = "CANONICAL_TAGS = {\n"
    for tag in sorted(canonical):
        canonical_str += f'    "{tag}",\n'
    canonical_str += "}"

    # Format mappings (sorted for readability)
    mappings_str = "TAG_MAPPINGS = {\n"
    for variant, canonical_tag in sorted(mappings.items()):
        mappings_str += f'    "{variant}": "{canonical_tag}",\n'
    mappings_str += "}"

    # Replace in file
    import re

    # Replace CANONICAL_TAGS
    content = re.sub(
        r"CANONICAL_TAGS = \{[^}]*\}",
        canonical_str,
        content,
        flags=re.DOTALL,
    )

    # Replace TAG_MAPPINGS
    content = re.sub(
        r"TAG_MAPPINGS = \{[^}]*\}",
        mappings_str,
        content,
        flags=re.DOTALL,
    )

    # Backup original
    backup_path = normalizer_path.with_suffix(".py.backup")
    normalizer_path.rename(backup_path)
    console.print(f"[dim]Backed up original to {backup_path}")

    # Write updated
    with open(normalizer_path, "w") as f:
        f.write(content)

    console.print(f"[green]✓ Updated {normalizer_path}")


def print_summary(stats: dict, validated: dict):
    """Print summary of changes."""
    console.print("\n[bold cyan]═══ Taxonomy Evolution Summary ═══[/bold cyan]")

    console.print(f"\nAnalyzed: {stats['total_articles']} articles")
    console.print(f"Raw tags found: {len(stats['raw_tags'])}")
    console.print(f"Canonical tags used: {len(stats['normalized_tags'])}")
    console.print(f"Discarded tags: {len(stats['discarded_tags'])}")

    console.print("\n[bold green]Changes Applied:[/bold green]")
    console.print(f"  + Promoted to canonical: {len(validated['promote'])}")
    console.print(f"  - Removed from canonical: {len(validated['remove'])}")
    console.print(f"  → New mappings added: {len(validated['mappings'])}")

    console.print("\n[bold]AI Reasoning:[/bold]")
    console.print(validated.get("reasoning", "N/A"))

    if validated["promote"]:
        console.print("\n[bold green]Promoted Tags:[/bold green]")
        for tag in validated["promote"][:10]:
            console.print(f"  + {tag}")

    if validated["remove"]:
        console.print("\n[bold yellow]Removed Tags:[/bold yellow]")
        for tag in validated["remove"][:10]:
            console.print(f"  - {tag}")


def main():
    """Main entry point."""
    console.print("[bold cyan]AI-Managed Taxonomy Evolution[/bold cyan]")
    console.print("Analyzing current tag usage and evolving taxonomy...\n")

    # Load config for OpenAI
    config = get_config()
    client = OpenAI(api_key=config.openai_api_key)

    # Analyze current usage
    console.print("[dim]Step 1: Analyzing current usage...")
    stats = analyze_current_usage()

    if stats["total_articles"] == 0:
        console.print("[red]No articles found!")
        return

    # Identify candidates
    console.print("[dim]Step 2: Identifying candidates for promotion/removal...")
    promote_candidates = identify_candidates_for_promotion(stats, min_usage=5)
    remove_candidates = identify_underused_tags(stats, min_usage=2)

    console.print(
        f"  Found {len(promote_candidates)} candidates for promotion (used 5+ times)"
    )
    console.print(
        f"  Found {len(remove_candidates)} underused canonical tags (used <2 times)"
    )

    if not promote_candidates and not remove_candidates:
        console.print("[green]\n✓ Taxonomy looks good! No changes needed.")
        return

    # Ask AI to validate
    console.print("[dim]Step 3: Asking AI to validate changes...")
    validated = ask_ai_to_validate_changes(
        promote_candidates, remove_candidates, client
    )

    if not validated["promote"] and not validated["remove"]:
        console.print("[green]\n✓ AI recommends no changes at this time.")
        console.print(f"Reasoning: {validated.get('reasoning', 'N/A')}")
        return

    # Generate updated taxonomy
    console.print("[dim]Step 4: Generating updated taxonomy...")
    new_canonical, new_mappings = generate_updated_taxonomy(
        validated, promote_candidates, remove_candidates
    )

    # Ask for confirmation
    print_summary(stats, validated)
    console.print("\n[bold yellow]⚠ This will update src/content/tag_normalizer.py")

    response = input("\nProceed with changes? [y/N]: ")
    if response.lower() != "y":
        console.print("[yellow]Aborted. No changes made.")
        return

    # Write updated file
    console.print("[dim]Step 5: Writing updated taxonomy...")
    write_updated_taxonomy_file(new_canonical, new_mappings)

    console.print("\n[bold green]✓ Taxonomy evolution complete!")
    console.print(
        "[dim]Run tests to verify: uv run pytest tests/test_tag_normalizer.py"
    )


if __name__ == "__main__":
    main()
