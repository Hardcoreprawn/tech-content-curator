#!/usr/bin/env python
"""
Demo: Show one article's images from all three free sources.

Engineering demo to compare what each service returns.
"""

from openai import OpenAI

from src.config import get_config
from src.images import CoverImageSelector


def main() -> None:
    """Show images for one article from all services."""

    # Get configuration
    config = get_config()
    client = OpenAI(api_key=config.openai_api_key)
    selector = CoverImageSelector(client, config)

    # Focus on the bird article
    article = {
        "title": "Understanding Bird Flight: Aerodynamics and Evolution",
        "tags": ["birds", "aerodynamics", "flight", "biology", "science"]
    }

    print("\n" + "=" * 100)
    print("SINGLE ARTICLE - ALL IMAGE SOURCES")
    print("=" * 100)
    print(f"\nArticle: {article['title']}")
    print(f"Tags: {', '.join(article['tags'])}")

    try:
        # Generate queries
        queries = selector._generate_search_queries(article["title"], article["tags"])

        print(f"\n{'-'*100}")
        print("SEARCH QUERIES")
        print(f"{'-'*100}")
        print(f"Wikimedia Query: {queries['wikimedia']}")
        print(f"Unsplash Query:  {queries['unsplash']}")
        print(f"Pexels Query:    {queries['pexels']}")

        # Get results from each service
        print(f"\n{'-'*100}")
        print("IMAGE RESULTS FROM EACH SERVICE")
        print(f"{'-'*100}\n")

        results = {}

        # Wikimedia
        print("[1] WIKIMEDIA COMMONS (Public Domain)")
        wiki = selector._search_wikimedia(queries['wikimedia'])
        if wiki:
            results['wikimedia'] = wiki
            print("    ✓ Found")
            print(f"    Source: {wiki.source}")
            print(f"    Quality: {wiki.quality_score:.2f}/1.00")
            print(f"    Cost: ${wiki.cost:.4f}")
            print(f"    URL: {wiki.url}")
            print(f"    Alt: {wiki.alt_text}")
        else:
            print("    ✗ No image found")

        # Unsplash
        print("\n[2] UNSPLASH (Free Stock Photos)")
        unsplash = selector._search_unsplash(queries['unsplash'])
        if unsplash:
            results['unsplash'] = unsplash
            print("    ✓ Found")
            print(f"    Source: {unsplash.source}")
            print(f"    Quality: {unsplash.quality_score:.2f}/1.00")
            print(f"    Cost: ${unsplash.cost:.4f}")
            print(f"    URL: {unsplash.url}")
            print(f"    Alt: {unsplash.alt_text}")
        else:
            print("    ✗ No image found")

        # Pexels
        print("\n[3] PEXELS (Free Stock Photos)")
        pexels = selector._search_pexels(queries['pexels'])
        if pexels:
            results['pexels'] = pexels
            print("    ✓ Found")
            print(f"    Source: {pexels.source}")
            print(f"    Quality: {pexels.quality_score:.2f}/1.00")
            print(f"    Cost: ${pexels.cost:.4f}")
            print(f"    URL: {pexels.url}")
            print(f"    Alt: {pexels.alt_text}")
        else:
            print("    ✗ No image found")

        # Show comparison
        print(f"\n{'-'*100}")
        print("COMPARISON & SELECTION")
        print(f"{'-'*100}\n")

        print("Cost Comparison:")
        for source, img in results.items():
            print(f"  {source.ljust(12)}: ${img.cost:.4f}")

        # Show which one gets selected
        selected = selector.select(article["title"], article["tags"])
        print(f"\nSelected: {selected.source.upper()}")
        print(f"Reason: Quality {selected.quality_score:.2f}, Cost ${selected.cost:.4f}")

        # Summary
        print(f"\n{'-'*100}")
        print("SUMMARY")
        print(f"{'-'*100}")
        print(f"\nTotal free sources found: {len(results)}")
        print(f"Total potential cost: ${sum(img.cost for img in results.values()):.4f}")
        print(f"Actually paying: ${selected.cost:.4f}")
        print(f"Savings: ${sum(img.cost for img in results.values()) - selected.cost:.4f}")

    except Exception as e:
        print(f"\n✗ Failed: {e}")
        import traceback
        traceback.print_exc()

    print(f"\n{'='*100}\n")


if __name__ == "__main__":
    main()
