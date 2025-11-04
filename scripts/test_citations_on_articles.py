#!/usr/bin/env python
"""
Test citation extraction and resolution on real articles from the content archive.

This script demonstrates the citation engine's robustness across multiple real-world
articles with varying citation formats and scientific content.
"""

from pathlib import Path

from src.citations import CitationExtractor, CitationResolver
from src.citations.cache import CitationCache


def extract_article_content(file_path: str) -> str:
    """Extract markdown content from article file (skip frontmatter)."""
    with open(file_path, encoding="utf-8") as f:
        content = f.read()

    # Skip YAML frontmatter
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            return parts[2].strip()
    return content


def test_article(file_path: str, article_name: str) -> dict:
    """Test citation engine on a single article."""
    print("\n" + "=" * 80)
    print(f"ARTICLE: {article_name}")
    print("=" * 80)

    try:
        content = extract_article_content(file_path)

        # Extract citations
        extractor = CitationExtractor()
        citations = extractor.extract(content)

        print(f"\nFound {len(citations)} citation(s):")
        for i, cit in enumerate(citations, 1):
            confidence_pct = int(cit.confidence * 100)
            print(f"  {i}. '{cit.original_text}' ({cit.year}, confidence: {confidence_pct}%)")

        if not citations:
            print("  (no citations found)")
            return {"article": article_name, "extracted": 0, "resolved": 0, "error": None}

        # Resolve citations
        resolver = CitationResolver()
        cache = CitationCache()
        resolved_count = 0

        print("\nResolving citations:")
        for citation in citations:
            # Try cache first
            cached = cache.get(citation.authors, citation.year)
            if cached and cached.get("url"):
                print(f"  ✓ {citation.authors} ({citation.year}) - CACHED")
                resolved_count += 1
            else:
                # Try API resolution
                resolved = resolver.resolve(citation.authors, citation.year)
                if resolved.url:
                    print("  ✓ {} ({}) - RESOLVED ({})".format(
                        citation.authors, citation.year, resolved.doi or "arXiv"))
                    resolved_count += 1
                    # Cache for next time
                    cache.put(citation.authors, citation.year, resolved.doi, resolved.url)
                else:
                    print(f"  ✗ {citation.authors} ({citation.year}) - NOT FOUND")

        print(f"\nResult: {resolved_count}/{len(citations)} citations resolved")
        return {
            "article": article_name,
            "extracted": len(citations),
            "resolved": resolved_count,
            "error": None
        }

    except Exception as e:
        print(f"\nERROR: {str(e)}")
        return {
            "article": article_name,
            "extracted": 0,
            "resolved": 0,
            "error": str(e)
        }


def main() -> None:
    """Test citation engine on multiple real articles."""

    articles_to_test = [
        ("content/posts/2025-10-31-owl-flight-quieter-drones.md", "Owl Flight & Drones"),
        ("content/posts/2025-10-31-covid-19-air-travel-safety.md", "COVID-19 Air Travel Safety"),
        ("content/posts/2025-10-30-enhancing-simulations-zozo-solver.md", "ZOZO Contact Solver"),
        ("content/archive/2025-10-28-debugging-challenges-llm-applications-d08d30636b6c.md", "Debugging LLM Applications"),
    ]

    print("\n" + "=" * 80)
    print("CITATION ENGINE: ROBUSTNESS TEST ON REAL ARTICLES")
    print("=" * 80)
    print(f"Testing on {len(articles_to_test)} articles from the content archive...")

    results = []
    for file_path, article_name in articles_to_test:
        full_path = Path(file_path)
        if full_path.exists():
            result = test_article(str(full_path), article_name)
            results.append(result)
        else:
            print(f"\nSKIPPED: {article_name} (file not found)")
            results.append({
                "article": article_name,
                "extracted": 0,
                "resolved": 0,
                "error": "File not found"
            })

    # Summary
    print("\n\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    total_extracted = sum(r["extracted"] for r in results)
    total_resolved = sum(r["resolved"] for r in results)
    successful = sum(1 for r in results if r["error"] is None)

    print(f"\nArticles tested: {len(results)}")
    print(f"Successful: {successful}")
    print(f"Total citations extracted: {total_extracted}")
    print(f"Total citations resolved: {total_resolved}")

    if total_extracted > 0:
        resolution_rate = (total_resolved / total_extracted) * 100
        print(f"Resolution rate: {resolution_rate:.1f}%")

    print("\nDetailed results:")
    for result in results:
        status = "✓" if result["error"] is None else "✗"
        print("  {} {} - {}/{} resolved".format(
            status, result["article"], result["resolved"], result["extracted"]))
        if result["error"]:
            print("     Error: {}".format(result["error"]))

    print("\n" + "=" * 80)
    print("ROBUSTNESS TEST COMPLETE")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
