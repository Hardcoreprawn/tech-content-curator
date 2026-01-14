"""Tests for pricing-backed cost estimation.

These are regression-style tests to ensure we can trust cost tracking for local runs.
"""

from __future__ import annotations

import pytest

from src.utils.pricing import (
    estimate_image_cost,
    estimate_text_cost,
    estimate_text_cost_components,
    get_text_pricing,
)


def test_estimate_text_cost_components_matches_total() -> None:
    pricing = get_text_pricing("gpt-4o-mini")
    assert pricing is not None

    prompt_tokens = 1000
    completion_tokens = 2000

    prompt_cost, completion_cost = estimate_text_cost_components(
        "gpt-4o-mini", prompt_tokens, completion_tokens
    )
    total_cost = estimate_text_cost("gpt-4o-mini", prompt_tokens, completion_tokens)

    assert prompt_cost == pytest.approx(0.00015)
    assert completion_cost == pytest.approx(0.0012)
    assert (prompt_cost + completion_cost) == pytest.approx(total_cost)


def test_text_pricing_aliases_are_resolved() -> None:
    # Alias defined in data/model_pricing.json
    pricing = get_text_pricing("gpt-5-mini-2025-08-07")
    assert pricing is not None
    assert pricing["input_per_million"] == pytest.approx(0.18)
    assert pricing["output_per_million"] == pytest.approx(0.72)


def test_estimate_image_cost_matches_table() -> None:
    assert estimate_image_cost("dall-e-3", size="1024x1024", quality="standard") == 0.02
    assert (
        estimate_image_cost(
            "dall-e-3",
            size="1024x1024",
            quality="standard",
            count=2,
        )
        == 0.04
    )
