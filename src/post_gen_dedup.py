"""
Post-generation deduplication check for generated articles.

This module provides additional deduplication checks to be run AFTER article
generation but BEFORE publishing, catching duplicates that semantic dedup missed.

See: docs/ADR-002-ENHANCED-DEDUPLICATION.md
"""

from difflib import SequenceMatcher
from pathlib import Path
from typing import NamedTuple

from rich.console import Console

console = Console()


class DuplicateCandidate(NamedTuple):
    """A pair of articles suspected to be duplicates."""

    article1_path: Path
    article2_path: Path
    title_similarity: float
    summary_similarity: float
    tag_overlap: float
    overall_score: float


def calculate_text_similarity(text1: str, text2: str) -> float:
    """Calculate similarity between two texts using SequenceMatcher."""
    if not text1 or not text2:
        return 0.0
    return SequenceMatcher(None, text1.lower(), text2.lower()).ratio()


def calculate_tag_overlap(tags1: list[str], tags2: list[str]) -> float:
    """Calculate tag overlap as percentage."""
    if not tags1 or not tags2:
        return 0.0
    overlap = len(set(tags1) & set(tags2))
    total = max(len(tags1), len(tags2))
    return overlap / total if total > 0 else 0.0


def check_articles_for_duplicates(
    article1_data: dict, article2_data: dict
) -> DuplicateCandidate | None:
    """
    Check if two articles are likely duplicates.

    Args:
        article1_data: Article metadata dict with keys: title, summary, tags
        article2_data: Article metadata dict with keys: title, summary, tags

    Returns:
        DuplicateCandidate if similarity exceeds threshold, None otherwise
    """
    # Extract data with defaults
    title1 = article1_data.get("title", "")
    title2 = article2_data.get("title", "")
    summary1 = article1_data.get("summary", "")
    summary2 = article2_data.get("summary", "")
    tags1 = article1_data.get("tags", [])
    tags2 = article2_data.get("tags", [])

    # Calculate similarities
    title_sim = calculate_text_similarity(title1, title2)
    summary_sim = calculate_text_similarity(summary1, summary2)
    tag_overlap = calculate_tag_overlap(tags1, tags2)

    # Weighted overall score
    # High title similarity is strong indicator of duplicate
    overall_score = (title_sim * 0.5) + (summary_sim * 0.3) + (tag_overlap * 0.2)

    # Thresholds for different match types
    # High title match + some tag overlap = likely duplicate
    if title_sim > 0.75 and tag_overlap > 0.2:
        return DuplicateCandidate(
            article1_path=Path(article1_data.get("path", "unknown")),
            article2_path=Path(article2_data.get("path", "unknown")),
            title_similarity=title_sim,
            summary_similarity=summary_sim,
            tag_overlap=tag_overlap,
            overall_score=overall_score,
        )

    # Strong summary match + high tag overlap = likely duplicate
    if summary_sim > 0.70 and tag_overlap > 0.6:
        return DuplicateCandidate(
            article1_path=Path(article1_data.get("path", "unknown")),
            article2_path=Path(article2_data.get("path", "unknown")),
            title_similarity=title_sim,
            summary_similarity=summary_sim,
            tag_overlap=tag_overlap,
            overall_score=overall_score,
        )

    # Multiple indicators present
    if overall_score > 0.65:
        return DuplicateCandidate(
            article1_path=Path(article1_data.get("path", "unknown")),
            article2_path=Path(article2_data.get("path", "unknown")),
            title_similarity=title_sim,
            summary_similarity=summary_sim,
            tag_overlap=tag_overlap,
            overall_score=overall_score,
        )

    return None


def find_duplicate_articles(articles: list[dict]) -> list[DuplicateCandidate]:
    """
    Find all likely duplicate pairs in a list of articles.

    Args:
        articles: List of article metadata dicts

    Returns:
        List of DuplicateCandidate pairs sorted by overall_score (highest first)
    """
    duplicates = []

    for i, article1 in enumerate(articles):
        for article2 in articles[i + 1 :]:
            candidate = check_articles_for_duplicates(article1, article2)
            if candidate:
                duplicates.append(candidate)

    # Sort by overall score (highest similarity first)
    duplicates.sort(key=lambda x: x.overall_score, reverse=True)
    return duplicates


def report_duplicate_candidates(
    duplicates: list[DuplicateCandidate], verbose: bool = False
) -> None:
    """Print a formatted report of duplicate candidates."""
    if not duplicates:
        console.print("[green]✓ No duplicate articles found[/green]")
        return

    console.print(f"\n[yellow]⚠️  Found {len(duplicates)} potential duplicate pairs:[/yellow]\n")

    for i, dup in enumerate(duplicates, 1):
        console.print(f"[bold]Pair {i}:[/bold]")
        console.print(f"  Article 1: {dup.article1_path.name}")
        console.print(f"  Article 2: {dup.article2_path.name}")
        console.print(f"  Overall similarity: {dup.overall_score:.1%}")
        if verbose:
            console.print(f"    Title similarity: {dup.title_similarity:.1%}")
            console.print(f"    Summary similarity: {dup.summary_similarity:.1%}")
            console.print(f"    Tag overlap: {dup.tag_overlap:.1%}")
        console.print()
