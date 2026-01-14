#!/usr/bin/env python
"""Local simulation: generate one article without network calls.

Uses a fake generator and stubs title generation to avoid external APIs.
Prints the article summary and the `generation_costs` breakdown for inspection.
"""

import sys
from datetime import datetime
from pathlib import Path

# Ensure repo root is on sys.path so `src` imports resolve when running script directly
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


# Avoid requiring the real OpenAI package for local simulation
class _NoOpClient:
    pass


import json
from pathlib import Path

# Local simple cost estimator using data/model_pricing.json so we don't import src
PRICING_PATH = Path(__file__).resolve().parents[1] / "data" / "model_pricing.json"


def _load_pricing():
    try:
        return json.loads(PRICING_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"text": {}, "image": {}}


def _estimate_text_cost(
    model: str, prompt_tokens: int, completion_tokens: int
) -> float:
    data = _load_pricing()
    text = data.get("text", {})
    entry = text.get(model) or next(
        (v for k, v in text.items() if model in v.get("aliases", [])), None
    )
    if not entry:
        return 0.0
    input_rate = entry.get("input_per_million", 0.0)
    output_rate = entry.get("output_per_million", 0.0)
    cost = (prompt_tokens / 1_000_000) * input_rate + (
        completion_tokens / 1_000_000
    ) * output_rate
    return cost


class FakeGenerator:
    def __init__(self):
        self._name = "fake-generator"

    @property
    def name(self):
        return self._name

    @property
    def priority(self):
        return 10

    def can_handle(self, item) -> bool:
        return True

    def generate_content(self, item):
        # Produce a medium-length article and token estimates (approx)
        content = (
            """
## Introduction

Bird flight evolved over millions of years. This article explains basic
aerodynamic principles (lift, drag), common anatomical adaptations, and
how researchers measure flight performance.

## Lift and Aerodynamics

Lift arises when airflow over the wing creates a pressure differential...

## Evolutionary Context

Species vary widely in wing shape and flight style; migratory birds tend to
have high aspect ratio wings, while maneuverable forest birds have shorter,
rounded wings.

## Conclusion

Understanding flight helps engineers and biologists alike.
"""
        ).strip()
        # Return content, input tokens (rough), output tokens (rough)
        return content, 150, 400


def _make_sample_enriched():
    # Use simple namespaces to avoid importing project models
    from types import SimpleNamespace

    collected = SimpleNamespace(
        id="demo-1",
        title="Understanding Bird Flight: Aerodynamics and Evolution",
        content="Birds use wings to generate lift and maneuver through air.",
        source="hackernews",
        url="https://example.com/demo-bird-flight",
        author="demo_user",
    )

    enriched = SimpleNamespace(
        original=collected,
        research_summary="Short summary: bird flight overview.",
        related_sources=["https://example.com/ref1"],
        topics=["birds", "aerodynamics"],
        quality_score=0.8,
    )
    return enriched


def main() -> None:
    # Simulate generation locally without importing the pipeline
    item = _make_sample_enriched()
    fake_gen = FakeGenerator()

    content, in_tokens, out_tokens = fake_gen.generate_content(item)
    word_count = len(content.split())

    # Choose a model name that exists in pricing table (fallback if missing)
    content_model = "gpt-5-mini"
    content_cost = _estimate_text_cost(content_model, in_tokens, out_tokens)

    # Simulate title generation cost (small call)
    title = "Understanding Bird Flight: Aerodynamics and Evolution"
    title_cost = _estimate_text_cost(content_model, 10, 8)

    # Build article-like dict
    article = {
        "title": title,
        "content": content,
        "filename": f"{datetime.now().strftime('%Y-%m-%d')}-understanding-bird-flight.md",
        "word_count": word_count,
        "generation_costs": {
            "content_generation": [content_cost],
            "title_generation": [title_cost],
        },
    }

    print("\n=== Article Generated (Simulated) ===")
    print(f"Title: {article['title']}")
    print(f"Filename: {article['filename']}")
    print(f"Word count: {article['word_count']}")
    print("\n--- Generation Costs ---")
    for k, v in article["generation_costs"].items():
        print(f"{k}: {v} (sum=${sum(v):.6f})")

    print("\n--- Content Preview ---")
    print(article["content"][:1000])


if __name__ == "__main__":
    main()
