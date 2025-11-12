#!/usr/bin/env python
"""
Demo: Multi-source image selection with smart fallback.

Shows the image selector trying free sources before falling back to DALL-E.
Also shows what each individual service returns for comparison.

Usage:
    python demo_image_selector.py                 # Test all services
    python demo_image_selector.py --wikimedia     # Wikimedia only
    python demo_image_selector.py --unsplash      # Unsplash only
    python demo_image_selector.py --pexels        # Pexels only
    python demo_image_selector.py --unsplash --pexels  # Multiple services
"""

import argparse

from openai import OpenAI

from src.config import get_config
from src.images import CoverImageSelector


def main() -> None:
    """Run image selector demo on sample article metadata."""

    # Parse arguments
    parser = argparse.ArgumentParser(description="Image selector demo")
    parser.add_argument(
        "--wikimedia", action="store_true", help="Test Wikimedia Commons"
    )
    parser.add_argument("--unsplash", action="store_true", help="Test Unsplash")
    parser.add_argument("--pexels", action="store_true", help="Test Pexels")
    parser.add_argument(
        "--all", action="store_true", help="Test all services (default)"
    )
    args = parser.parse_args()

    # Determine which services to test
    # If no specific services requested, test all
    test_all = not any([args.wikimedia, args.unsplash, args.pexels])
    services_to_test = {
        "wikimedia": args.wikimedia or test_all or args.all,
        "unsplash": args.unsplash or test_all or args.all,
        "pexels": args.pexels or test_all or args.all,
    }

    # Get configuration with API keys
    config = get_config()

    # Create OpenAI client
    client = OpenAI(api_key=config.openai_api_key)

    # Create image selector
    selector = CoverImageSelector(client, config)

    # Test articles with different topics
    test_articles = [
        {
            "title": "Understanding Bird Flight: Aerodynamics and Evolution",
            "tags": ["birds", "aerodynamics", "flight", "biology", "science"],
        },
        {
            "title": "Machine Learning in Healthcare: Practical Applications",
            "tags": [
                "machine-learning",
                "healthcare",
                "AI",
                "technology",
                "data-science",
            ],
        },
        {
            "title": "Quantum Computing: From Theory to Practice",
            "tags": ["quantum-computing", "physics", "technology", "computer-science"],
        },
    ]

    print("\n" + "=" * 80)
    print("MULTI-SOURCE IMAGE SELECTOR DEMO")
    print("=" * 80)
    print("\nConfiguration:")
    print(f"  - Unsplash API Key: {'✓' if config.unsplash_api_key else '✗'}")
    print(f"  - Pexels API Key: {'✓' if config.pexels_api_key else '✗'}")
    print(f"  - Timeout: {config.image_source_timeout}s")

    print("\nTesting Services:")
    print(f"  - Wikimedia: {'✓' if services_to_test['wikimedia'] else '✗'}")
    print(f"  - Unsplash:  {'✓' if services_to_test['unsplash'] else '✗'}")
    print(f"  - Pexels:    {'✓' if services_to_test['pexels'] else '✗'}")

    for i, article in enumerate(test_articles, 1):
        print(f"\n{'=' * 80}")
        print(f"[{i}] Article: {article['title']}")
        print(f"    Tags: {', '.join(article['tags'][:3])}...")
        print(f"{'-' * 80}")

        try:
            # Generate search queries
            queries = selector._generate_search_queries(
                article["title"], article["tags"]
            )
            print("\nGenerated Search Queries:")
            print(f"  Wikimedia: {queries['wikimedia']}")
            print(f"  Unsplash:  {queries['unsplash']}")
            print(f"  Pexels:    {queries['pexels']}")

            # Test each service individually
            print(f"\n{'-' * 80}")
            print("Individual Service Results (Engineering Debug):")
            print(f"{'-' * 80}")

            # Try Wikimedia
            if services_to_test["wikimedia"]:
                print("\n[Wikimedia Commons]")
                wiki_result = selector._search_wikimedia(queries["wikimedia"])
                if wiki_result:
                    print("  ✓ Found image")
                    print(f"    Source: {wiki_result.source}")
                    print(f"    Quality: {wiki_result.quality_score:.2f}")
                    print(f"    Cost: ${wiki_result.cost:.4f}")
                    print(f"    URL: {wiki_result.url[:70]}...")
                    print(f"    Alt: {wiki_result.alt_text[:50]}...")
                else:
                    print("  ✗ No image found")

            # Try Unsplash
            if services_to_test["unsplash"]:
                print("\n[Unsplash]")
                unsplash_result = selector._search_unsplash(queries["unsplash"])
                if unsplash_result:
                    print("  ✓ Found image")
                    print(f"    Source: {unsplash_result.source}")
                    print(f"    Quality: {unsplash_result.quality_score:.2f}")
                    print(f"    Cost: ${unsplash_result.cost:.4f}")
                    print(f"    URL: {unsplash_result.url[:70]}...")
                    print(f"    Alt: {unsplash_result.alt_text[:50]}...")
                else:
                    print("  ✗ No image found")

            # Try Pexels
            if services_to_test["pexels"]:
                print("\n[Pexels]")
                pexels_result = selector._search_pexels(queries["pexels"])
                if pexels_result:
                    print("  ✓ Found image")
                    print(f"    Source: {pexels_result.source}")
                    print(f"    Quality: {pexels_result.quality_score:.2f}")
                    print(f"    Cost: ${pexels_result.cost:.4f}")
                    print(f"    URL: {pexels_result.url[:70]}...")
                    print(f"    Alt: {pexels_result.alt_text[:50]}...")
                else:
                    print("  ✗ No image found")

            # Show final selection
            print(f"\n{'-' * 80}")
            print("Final Selection (Highest Priority):")
            print(f"{'-' * 80}")
            image = selector.select(article["title"], article["tags"])

            print(f"  Selected: {image.source.upper()}")
            print(f"  Quality: {image.quality_score:.2f}/1.00")
            print(f"  Cost: ${image.cost:.4f}")
            print(f"  URL: {image.url[:70]}...")
            print(f"  Alt: {image.alt_text[:70]}...")

        except Exception as e:
            print(f"\n✗ Selection failed: {e}")

    print(f"\n{'=' * 80}")
    print("DEMO COMPLETE")
    print("=" * 80)
    print("\nNext steps:")
    print("1. Review the images selected above")
    print("2. Commit changes and push to main")
    print("3. Run GitHub Actions to generate articles with real images")
    print("4. Check that articles use Unsplash/Pexels instead of DALL-E")


if __name__ == "__main__":
    main()
