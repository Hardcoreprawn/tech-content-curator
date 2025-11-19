"""Pricing utilities backed by ``data/model_pricing.json``.

Loads the canonical model pricing table once per process and provides helpers to
estimate text and image costs. All amounts are in USD.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from .logging import get_logger

logger = get_logger(__name__)

_PRICING_PATH = Path(__file__).resolve().parents[2] / "data" / "model_pricing.json"


@lru_cache(maxsize=1)
def _load_pricing() -> dict[str, Any]:
    if not _PRICING_PATH.exists():
        logger.warning(
            "Pricing file %s missing; defaulting to empty pricing", _PRICING_PATH
        )
        return {"text": {}, "image": {}}

    try:
        with _PRICING_PATH.open(encoding="utf-8") as handle:
            return json.load(handle)
    except json.JSONDecodeError as exc:
        logger.error("Failed to parse pricing file %s: %s", _PRICING_PATH, exc)
        return {"text": {}, "image": {}}


def _match_entry(table: dict[str, Any], model: str) -> dict[str, Any] | None:
    if model in table:
        return table[model]

    for entry_name, entry in table.items():
        aliases = entry.get("aliases", []) if isinstance(entry, dict) else []
        if model in aliases:
            return table[entry_name]
    return None


def get_text_pricing(model: str) -> dict[str, Any] | None:
    """Return pricing info for a text model (tokens per million)."""

    data = _load_pricing()
    text_table = data.get("text", {})
    return _match_entry(text_table, model)


def estimate_text_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Estimate USD cost for a text call based on token counts."""

    pricing = get_text_pricing(model)
    if not pricing:
        return 0.0

    input_rate = pricing.get("input_per_million", 0.0)
    output_rate = pricing.get("output_per_million", 0.0)
    cost = 0.0
    if prompt_tokens:
        cost += (prompt_tokens / 1_000_000) * input_rate
    if completion_tokens:
        cost += (completion_tokens / 1_000_000) * output_rate
    return cost


def get_image_pricing(model: str) -> dict[str, Any] | None:
    """Return pricing info for an image model."""

    data = _load_pricing()
    image_table = data.get("image", {})
    return _match_entry(image_table, model)


def estimate_image_cost(
    model: str,
    *,
    size: str = "1024x1024",
    quality: str = "standard",
    count: int = 1,
) -> float:
    """Estimate USD cost for image generation."""

    pricing = get_image_pricing(model)
    if not pricing:
        return 0.0

    size_table = pricing.get(size)
    if not size_table:
        return 0.0

    base_cost = size_table.get(quality)
    if base_cost is None:
        return 0.0

    return base_cost * max(count, 1)
