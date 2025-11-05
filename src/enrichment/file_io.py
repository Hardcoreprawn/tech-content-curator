"""File I/O operations for enrichment pipeline.

This module handles loading and saving enriched content:
- Load collected items from JSON files
- Save enriched items to JSON files
- Timestamp management for file naming
"""

import json
from datetime import UTC, datetime
from pathlib import Path

from rich.console import Console

from ..config import get_data_dir
from ..models import CollectedItem, EnrichedItem
from ..utils.logging import get_logger

logger = get_logger(__name__)
console = Console()


def save_enriched_items(
    items: list[EnrichedItem], timestamp: str | None = None
) -> Path:
    """Save enriched items to JSON file.

    Args:
        items: List of enriched items to save
        timestamp: Optional timestamp for filename (default: current time)

    Returns:
        Path to saved file
    """
    logger.debug(f"Saving {len(items)} enriched items")
    if not timestamp:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    filename = f"enriched_{timestamp}.json"
    filepath = get_data_dir() / filename

    # Convert to dict for JSON serialization
    data = {
        "enriched_at": datetime.now(UTC).isoformat(),
        "total_items": len(items),
        "items": [item.model_dump() for item in items],
    }

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)

    logger.info(f"Saved {len(items)} enriched items to {filename}")
    console.print(f"[green]✓[/green] Saved {len(items)} enriched items to {filename}")
    return filepath


def load_collected_items(filepath: Path) -> list[CollectedItem]:
    """Load collected items from a JSON file.

    Args:
        filepath: Path to the collected items JSON file

    Returns:
        List of CollectedItem objects
    """
    logger.debug(f"Loading collected items from {filepath.name}")
    with open(filepath, encoding="utf-8") as f:
        data = json.load(f)

    items = []
    for item_data in data["items"]:
        try:
            item = CollectedItem(**item_data)
            items.append(item)
        except Exception as e:
            logger.warning(f"Failed to load item: {type(e).__name__}: {e}")
            console.print(f"[yellow]⚠[/yellow] Failed to load item: {e}")
            continue

    logger.info(f"Loaded {len(items)} collected items from {filepath.name}")
    console.print(
        f"[green]✓[/green] Loaded {len(items)} collected items from {filepath.name}"
    )
    return items


def load_enriched_items(filepath: Path) -> list[EnrichedItem]:
    """Load enriched items from a JSON file.

    Args:
        filepath: Path to the enriched items JSON file

    Returns:
        List of EnrichedItem objects
    """
    logger.debug(f"Loading enriched items from {filepath.name}")
    with open(filepath, encoding="utf-8") as f:
        data = json.load(f)

    items = []
    for item_data in data["items"]:
        try:
            item = EnrichedItem(**item_data)
            items.append(item)
        except Exception as e:
            logger.warning(f"Failed to load item: {type(e).__name__}: {e}")
            console.print(f"[yellow]⚠[/yellow] Failed to load item: {e}")
            continue

    logger.info(f"Loaded {len(items)} enriched items from {filepath.name}")
    console.print(
        f"[green]✓[/green] Loaded {len(items)} enriched items from {filepath.name}"
    )
    return items
