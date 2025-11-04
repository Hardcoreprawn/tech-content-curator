#!/usr/bin/env python
"""
Demo: Robust citation resolution on scientific article content.

Shows the citation engine handling poorly formatted citations.
"""

from src.citations import CitationExtractor, CitationFormatter, CitationResolver
from src.citations.cache import CitationCache


def main() -> None:
    """Run citation demo on sample article text with variations."""

    # Sample article text with VARIOUS citation formats
    # Including poorly formatted ones
    article_text = """Recent research by Lentink (2014) established foundational
principles for understanding avian aerodynamics. This work demonstrated how
biological flight systems achieve remarkable efficiency through specialized
wing structures.

Building on this foundation, Usherwood et al. (2017) conducted detailed
studies. Jones et al (2016) also contributed findings. Additionally,
Smith, et al. (2015) examined related phenomena. Prior work by Brown (2013)
laid groundwork for these investigations."""

    print("\n" + "=" * 80)
    print("ROBUST CITATION ENGINE DEMO")
    print("=" * 80)

    # Step 1: Extract (handling variations)
    print("\n[1] EXTRACT: Finding citations (handles variations)")
    print("-" * 80)
    extractor = CitationExtractor()
    citations = extractor.extract(article_text)

    print("Original article text:")
    print(article_text)
    print(f"\nFound {len(citations)} citation(s):")
    for i, cit in enumerate(citations, 1):
        confidence_str = f"{int(cit.confidence * 100)}%"
        print(f"  {i}. '{cit.original_text}' ({cit.authors}, confidence: {confidence_str})")

    # Step 2: Resolve (with fallback strategies)
    print("\n\n[2] RESOLVE: Looking up papers (tries multiple strategies)")
    print("-" * 80)
    resolver = CitationResolver()
    cache = CitationCache()
    resolved_list = []

    for citation in citations:
        print(f"\nResolving: {citation.original_text} ({citation.year})")

        # Try 1: Check cache
        cached = cache.get(citation.authors, citation.year)
        if cached and cached.get("url"):
            print("  - CACHE HIT")
            print("    URL: {}".format(cached.get("url")))
            resolved_list.append(cached)
        else:
            # Try 2-4: APIs with fallback strategies
            resolved = resolver.resolve(citation.authors, citation.year)
            if resolved.url:
                print("  - FOUND via API")
                print(f"    URL: {resolved.url}")
                if resolved.doi:
                    print(f"    DOI: {resolved.doi}")
                # Cache for next time
                cache.put(citation.authors, citation.year, resolved.doi, resolved.url)
                resolved_list.append(resolved)
            else:
                print("  - NOT FOUND")
                resolved_list.append(None)

    # Step 3: Format
    print("\n\n[3] FORMAT: Creating markdown links")
    print("-" * 80)
    formatter = CitationFormatter()
    formatted_citations = []

    for citation, resolved in zip(citations, resolved_list, strict=False):
        if resolved:
            if isinstance(resolved, dict):
                from src.citations.resolver import ResolvedCitation
                resolved_obj = ResolvedCitation(
                    doi=resolved.get("doi"),
                    arxiv_id=None,
                    pmid=None,
                    url=resolved.get("url"),
                    confidence=0.95
                )
            else:
                resolved_obj = resolved

            formatted = formatter.format(citation, resolved_obj)
            formatted_citations.append(formatted)

    # Step 4: Show result
    print("\n\n[4] RESULT: Article with linked citations")
    print("-" * 80)
    print("BEFORE:")
    print(article_text)

    result = formatter.apply_to_text(article_text, formatted_citations)
    print("\n\nAFTER (citations linked to papers):")
    print(result)

    # Summary
    print("\n\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    resolved_count = sum(1 for item in resolved_list if item is not None)
    print(f"Extracted: {len(citations)} citations (including variations)")
    print(f"Resolved: {resolved_count} citations")
    print(f"Cached: {len(cache.data)} entries")
    print("\nRobust features demonstrated:")
    print("  - Multi-pattern extraction (et al., et al (no period), comma variants)")
    print("  - Fallback resolution (CrossRef full -> first author -> arXiv)")
    print("  - Author normalization")
    print("  - Caching for performance")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
