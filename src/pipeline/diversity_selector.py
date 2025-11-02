"""Candidate diversity selection for article generation.

This module provides logic for selecting a diverse set of article candidates
that cover different specialized generators.
"""

from __future__ import annotations

from ..generators.base import BaseGenerator
from ..models import EnrichedItem


def select_diverse_candidates(
    candidates: list[EnrichedItem], max_articles: int, generators: list[BaseGenerator]
) -> list[EnrichedItem]:
    """Pick a diverse set of candidates within the limit.

    Heuristic: Prefer including at least one from each specialized generator when available,
    then fill the rest by quality.

    Args:
        candidates: Already quality-sorted candidates (best first)
        max_articles: Upper bound to return
        generators: List of available generators

    Returns:
        Ordered list of selected items (length <= max_articles)
    """
    if max_articles <= 0 or not candidates:
        return []

    selected: list[EnrichedItem] = []

    # Partition buckets by generator (skip general generator)
    specialized_gens = [g for g in generators if g.priority > 0]
    buckets = {gen.name: [] for gen in specialized_gens}

    for item in candidates:
        for gen in specialized_gens:
            if gen.can_handle(item):
                buckets[gen.name].append(item)
                break

    # Helper to append if capacity remains
    def try_add(item: EnrichedItem) -> None:
        if len(selected) < max_articles and item not in selected:
            selected.append(item)

    # Ensure coverage: pick one from each specialized generator when available
    for _gen_name, items in buckets.items():
        if items:
            try_add(items[0])

    # Fill remaining slots by overall quality order
    for c in candidates:
        if len(selected) >= max_articles:
            break
        try_add(c)

    return selected
