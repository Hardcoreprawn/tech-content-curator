"""
Post-generation deduplication check for generated articles.

This module provides additional deduplication checks to be run AFTER article
generation but BEFORE publishing, catching duplicates that semantic dedup missed.

See: docs/ADR-002-ENHANCED-DEDUPLICATION.md
"""

import re
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
    entity_similarity: float
    content_similarity: float
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


def extract_entities(text: str) -> set[str]:
    """
    Extract likely entities from text.
    
    This is a simple approach that extracts:
    - Capitalized words (likely proper nouns)
    - Common tech/business terms
    - Acronyms
    - Key domain terms
    
    Args:
        text: Text to extract entities from
        
    Returns:
        Set of extracted entity strings (normalized to lowercase)
    """
    entities = set()
    
    if not text:
        return entities
    
    # Extract capitalized words (proper nouns)
    # Match words that start with capital letter and are at least 2 chars
    proper_nouns = re.findall(r'\b[A-Z][a-z]+\b', text)
    entities.update(w.lower() for w in proper_nouns)
    
    # Extract common tech/business entities (case-insensitive)
    tech_entities = [
        # Design/software
        'affinity', 'microsoft', 'open source', 'icc', 'adobe', 'figma',
        'canva', 'github', 'docker', 'kubernetes', 'aws', 'azure',
        'google', 'apple', 'ai', 'ml', 'ai features', 'freemium',
        'software', 'office', 'cloud', 'enterprise', 'office',
        # Key concepts
        'saas', 'subscription', 'licensing', 'acquisition', 'deprecation',
        'open-source', 'free', 'paid', 'proprietary', 'free software',
        'international criminal court', 'data privacy', 'data security'
    ]
    
    text_lower = text.lower()
    for entity in tech_entities:
        if entity in text_lower:
            entities.add(entity)
    
    # Extract acronyms (sequences of 2+ capital letters)
    acronyms = re.findall(r'\b[A-Z]{2,}\b', text)
    entities.update(a.lower() for a in acronyms)
    
    # Extract key tech terms using word boundaries
    key_terms = [
        'freemium', 'subscription', 'deprecation', 'acquisition', 'licensing',
        'cloud', 'open', 'source', 'proprietary', 'alternative', 'migrate',
        'transition', 'shift', 'move', 'adoption'
    ]
    
    for term in key_terms:
        if f' {term} ' in f' {text_lower} ' or text_lower.startswith(term) or text_lower.endswith(term):
            entities.add(term)
    
    return entities


def calculate_entity_similarity(entities1: set[str], entities2: set[str]) -> float:
    """
    Calculate similarity based on shared entities.
    
    Args:
        entities1: Set of entities from first text
        entities2: Set of entities from second text
        
    Returns:
        Similarity score (0.0-1.0) based on entity overlap
    """
    if not entities1 or not entities2:
        return 0.0
    
    intersection = len(entities1 & entities2)
    union = len(entities1 | entities2)
    
    return intersection / union if union > 0 else 0.0


def calculate_content_similarity(content1: str, content2: str) -> float:
    """
    Calculate similarity based on article content.
    
    Uses sequence matching on the full content to catch duplicates
    that have different titles but same content.
    
    Args:
        content1: Full content of first article
        content2: Full content of second article
        
    Returns:
        Similarity score (0.0-1.0)
    """
    if not content1 or not content2:
        return 0.0
    
    # Use a normalized version (lowercase, remove extra whitespace)
    norm1 = ' '.join(content1.lower().split())
    norm2 = ' '.join(content2.lower().split())
    
    return SequenceMatcher(None, norm1, norm2).ratio()


def check_articles_for_duplicates(
    article1_data: dict, article2_data: dict
) -> DuplicateCandidate | None:
    """
    Check if two articles are likely duplicates.
    
    Uses multi-criteria approach:
    1. Title similarity
    2. Summary similarity
    3. Tag overlap
    4. Entity matching (common proper nouns, acronyms, tech terms)
    5. Content body similarity (if available)
    6. Keyword overlap (catches same-topic articles with different angles)

    Args:
        article1_data: Article metadata dict with keys: title, summary, tags, content (optional)
        article2_data: Article metadata dict with keys: title, summary, tags, content (optional)

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
    content1 = article1_data.get("content", "")
    content2 = article2_data.get("content", "")

    # Calculate basic similarities
    title_sim = calculate_text_similarity(title1, title2)
    summary_sim = calculate_text_similarity(summary1, summary2)
    tag_overlap = calculate_tag_overlap(tags1, tags2)
    
    # NEW: Entity-based matching (catches "Affinity" vs "Affinity Software", "ICC" vs "International Criminal Court")
    entities1 = extract_entities(title1 + " " + summary1)
    entities2 = extract_entities(title2 + " " + summary2)
    entity_sim = calculate_entity_similarity(entities1, entities2)
    
    # NEW: Content-based similarity (if content is available)
    content_sim = 0.0
    if content1 and content2:
        content_sim = calculate_content_similarity(content1, content2)
    
    # NEW: Keyword overlap - extract significant keywords (>4 chars) from titles
    def extract_keywords(text: str) -> set[str]:
        """Extract significant keywords (>4 chars) from text."""
        words = text.lower().split()
        return {w.strip('.,!?;:') for w in words if len(w) > 4 and not w.startswith('http')}
    
    keywords1 = extract_keywords(title1)
    keywords2 = extract_keywords(title2)
    keyword_overlap = len(keywords1 & keywords2) / max(len(keywords1), len(keywords2), 1) if (keywords1 or keywords2) else 0.0
    
    # Improved weighted overall score
    if content1 and content2:
        overall_score = (
            (title_sim * 0.20) +
            (summary_sim * 0.12) +
            (tag_overlap * 0.08) +
            (entity_sim * 0.20) +
            (content_sim * 0.25) +
            (keyword_overlap * 0.15)
        )
    else:
        # Fallback if content not available (during generation)
        overall_score = (
            (title_sim * 0.25) +
            (summary_sim * 0.15) +
            (tag_overlap * 0.10) +
            (entity_sim * 0.30) +
            (keyword_overlap * 0.20)
        )

    # Detection thresholds (now more flexible with entity and keyword matching)
    
    # 1. Strong entity match + reasonable summary match
    #    Catches duplicates with different titles but same topic entity
    if entity_sim > 0.4 and (summary_sim > 0.65 or keyword_overlap > 0.3):
        return DuplicateCandidate(
            article1_path=Path(article1_data.get("path", "unknown")),
            article2_path=Path(article2_data.get("path", "unknown")),
            title_similarity=title_sim,
            summary_similarity=summary_sim,
            tag_overlap=tag_overlap,
            entity_similarity=entity_sim,
            content_similarity=content_sim,
            overall_score=overall_score,
        )
    
    # 2. High keyword overlap + some entity match
    #    Catches "Affinity Studio Goes Free" vs "Affinity Software's Freemium Shift"
    if keyword_overlap > 0.4 and entity_sim > 0.1:
        return DuplicateCandidate(
            article1_path=Path(article1_data.get("path", "unknown")),
            article2_path=Path(article2_data.get("path", "unknown")),
            title_similarity=title_sim,
            summary_similarity=summary_sim,
            tag_overlap=tag_overlap,
            entity_similarity=entity_sim,
            content_similarity=content_sim,
            overall_score=overall_score,
        )
    
    # 3. High title match + some tag overlap (original logic)
    if title_sim > 0.75 and tag_overlap > 0.2:
        return DuplicateCandidate(
            article1_path=Path(article1_data.get("path", "unknown")),
            article2_path=Path(article2_data.get("path", "unknown")),
            title_similarity=title_sim,
            summary_similarity=summary_sim,
            tag_overlap=tag_overlap,
            entity_similarity=entity_sim,
            content_similarity=content_sim,
            overall_score=overall_score,
        )

    # 4. Strong summary match + high tag overlap (original logic)
    if summary_sim > 0.70 and tag_overlap > 0.6:
        return DuplicateCandidate(
            article1_path=Path(article1_data.get("path", "unknown")),
            article2_path=Path(article2_data.get("path", "unknown")),
            title_similarity=title_sim,
            summary_similarity=summary_sim,
            tag_overlap=tag_overlap,
            entity_similarity=entity_sim,
            content_similarity=content_sim,
            overall_score=overall_score,
        )

    # 5. High content similarity (catches rephrased duplicates)
    if content_sim > 0.60:
        return DuplicateCandidate(
            article1_path=Path(article1_data.get("path", "unknown")),
            article2_path=Path(article2_data.get("path", "unknown")),
            title_similarity=title_sim,
            summary_similarity=summary_sim,
            tag_overlap=tag_overlap,
            entity_similarity=entity_sim,
            content_similarity=content_sim,
            overall_score=overall_score,
        )
    
    # 6. Overall score threshold (now 0.50 with new metrics)
    if overall_score > 0.50:
        return DuplicateCandidate(
            article1_path=Path(article1_data.get("path", "unknown")),
            article2_path=Path(article2_data.get("path", "unknown")),
            title_similarity=title_sim,
            summary_similarity=summary_sim,
            tag_overlap=tag_overlap,
            entity_similarity=entity_sim,
            content_similarity=content_sim,
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
            console.print(f"    Title similarity:   {dup.title_similarity:.1%}")
            console.print(f"    Summary similarity: {dup.summary_similarity:.1%}")
            console.print(f"    Tag overlap:        {dup.tag_overlap:.1%}")
            console.print(f"    Entity similarity:  {dup.entity_similarity:.1%}")
            console.print(f"    Content similarity: {dup.content_similarity:.1%}")
        console.print()
