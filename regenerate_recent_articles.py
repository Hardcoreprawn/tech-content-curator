#!/usr/bin/env python3
"""
Regenerate recent articles with Feature 3 (AI Illustrations) enabled.

This script:
1. Loads the most recent enriched data
2. Regenerates articles with enable_illustrations=True
3. Overwrites existing articles
4. Reports on illustrations added and costs
"""

import os
import sys
from pathlib import Path

from openai import OpenAI

from src.models import PipelineConfig
from src.pipeline import (
    generate_articles_from_enriched,
    get_available_generators,
    load_enriched_items,
)


def find_latest_enriched_file() -> Path:
    """Find the most recent enriched JSON file in data/."""
    data_dir = Path("data")
    enriched_files = sorted(data_dir.glob("enriched_*.json"), reverse=True)
    
    if not enriched_files:
        raise FileNotFoundError("No enriched files found in data/")
    
    return enriched_files[0]


def main():
    """Regenerate recent articles with illustrations."""
    
    print("\n" + "=" * 80)
    print("REGENERATE RECENT ARTICLES WITH FEATURE 3")
    print("=" * 80 + "\n")
    
    # Find latest enriched file
    enriched_file = find_latest_enriched_file()
    print(f"Loading enriched items from: {enriched_file.name}")
    
    # Load enriched items
    items = load_enriched_items(enriched_file)
    print(f"Loaded: {len(items)} enriched items\n")
    
    # Configure pipeline with illustrations enabled
    config = PipelineConfig(
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        enable_illustrations=True,  # ✅ FEATURE 3 ENABLED
    )
    
    # Get generators
    client = OpenAI()
    generators = get_available_generators(client)
    
    print(f"Illustrations enabled: {config.enable_illustrations}")
    print(f"Available generators: {len(generators)}\n")
    
    # Regenerate articles (force regenerate to overwrite)
    print("=" * 80)
    print("REGENERATING ARTICLES")
    print("=" * 80 + "\n")
    
    articles = generate_articles_from_enriched(
        items,
        max_articles=10,  # Regenerate up to 10 articles
        force_regenerate=True,  # Overwrite existing
        generate_images=False,  # Skip cover images for now
        fact_check=False,
    )
    
    # Summary
    print("\n" + "=" * 80)
    print("REGENERATION SUMMARY")
    print("=" * 80 + "\n")
    
    total_illustrations = sum(a.illustrations_count for a in articles if a)
    total_cost = sum(
        a.generation_costs.get("illustrations", 0) for a in articles if a
    )
    
    successful = len([a for a in articles if a])
    
    print(f"✅ Articles regenerated: {successful}/{len(articles)}")
    print(f"📊 Total illustrations added: {total_illustrations}")
    print(f"💰 Illustration costs: ${total_cost:.6f}")
    
    if successful > 0:
        avg_illustrations = total_illustrations / successful
        print(f"📈 Average illustrations per article: {avg_illustrations:.1f}")
        print(f"💵 Average cost per article: ${total_cost / successful:.6f}")
    
    # Show article details
    if articles:
        print("\n" + "-" * 80)
        print("REGENERATED ARTICLES:")
        print("-" * 80)
        for i, article in enumerate(articles, 1):
            if article:
                ill_cost = article.generation_costs.get("illustrations", 0)
                print(
                    f"{i}. {article.title[:50]:50s} | "
                    f"Illustrations: {article.illustrations_count:2d} | "
                    f"Cost: ${ill_cost:.6f}"
                )
    
    print("\n" + "=" * 80)
    print("✅ REGENERATION COMPLETE")
    print("=" * 80 + "\n")
    
    return 0 if successful > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
