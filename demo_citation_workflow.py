#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Demonstrate the citation engine's real-world usage in the content pipeline.

This shows the intended workflow:
1. Articles are generated from sources
2. If they mention research, citations are extracted and resolved
3. Citations are automatically linked to DOIs/arXiv IDs
4. Results are cached to avoid duplicate API calls

This is designed to show what SHOULD happen during article generation,
not what currently happens (since existing articles don't have structured citations).
"""

from src.citations import CitationExtractor, CitationResolver, CitationFormatter
from src.citations.cache import CitationCache


def demo_workflow() -> None:
    """Demonstrate the intended citation workflow."""
    
    print("\n" + "=" * 80)
    print("CITATION ENGINE: REAL-WORLD WORKFLOW DEMONSTRATION")
    print("=" * 80)
    
    # Scenario: An article is generated about scientific research
    # The generator includes citations in the standard format
    
    article_content = """## Understanding Aerodynamic Principles

Recent research has fundamentally changed our understanding of efficient flight. 
Lentink (2014) established foundational principles for biomimetic design through 
detailed aerodynamic analysis. This pioneering work was later built upon by 
Usherwood et al. (2017) who conducted comprehensive studies on vortex dynamics.

Their findings demonstrated that Jones et al (2016) had actually identified similar 
principles earlier. Additionally, Smith, et al. (2015) contributed important 
insights into wing efficiency. These studies collectively show that nature has 
optimized flight systems in ways we're only beginning to understand.

## Applications to Technology

The aerodynamic insights from Lentink (2014) and Usherwood et al. (2017) have 
direct applications to drone design. Engineering teams are now using these principles 
to create quieter, more efficient unmanned systems.

## Conclusion

The research cited above, particularly Brown (2013), provides the theoretical 
foundation for the next generation of biomimetic technologies."""
    
    print("\n[STEP 1] GENERATED ARTICLE CONTENT")
    print("-" * 80)
    print(article_content)
    
    # Step 1: Extract citations
    print("\n\n[STEP 2] EXTRACT CITATIONS")
    print("-" * 80)
    extractor = CitationExtractor()
    citations = extractor.extract(article_content)
    
    print("Found {} citation(s):".format(len(citations)))
    for i, cit in enumerate(citations, 1):
        confidence_pct = int(cit.confidence * 100)
        print("  {}. '{}' - {} ({})".format(
            i, cit.original_text, cit.authors, confidence_pct + 1))
    
    # Step 2: Resolve citations
    print("\n\n[STEP 3] RESOLVE CITATIONS (with caching)")
    print("-" * 80)
    
    resolver = CitationResolver()
    cache = CitationCache()
    formatted_citations = []
    
    for citation in citations:
        # Check if we've already looked this up
        cached = cache.get(citation.authors, citation.year)
        if cached and cached.get("url"):
            print("  ✓ {} ({}) → CACHE HIT".format(citation.authors, citation.year))
            print("    URL: {}".format(cached.get("url")))
            # Build formatted citation for caching
            from src.citations.resolver import ResolvedCitation
            resolved = ResolvedCitation(
                doi=cached.get("doi"),
                arxiv_id=None,
                pmid=None,
                url=cached.get("url"),
                confidence=0.95
            )
            formatted_citations.append((citation, resolved))
        else:
            # Query APIs
            print("  → {} ({}) ... querying APIs".format(citation.authors, citation.year))
            resolved = resolver.resolve(citation.authors, citation.year)
            
            if resolved.url:
                print("    ✓ FOUND: {}".format(resolved.url))
                if resolved.doi:
                    print("      DOI: {}".format(resolved.doi))
                # Cache for next run
                cache.put(citation.authors, citation.year, resolved.doi, resolved.url)
                formatted_citations.append((citation, resolved))
            else:
                print("    ✗ NOT FOUND in CrossRef/arXiv")
                formatted_citations.append((citation, resolved))
    
    # Step 3: Format and apply to article
    print("\n\n[STEP 4] FORMAT AND APPLY TO ARTICLE")
    print("-" * 80)
    
    formatter = CitationFormatter()
    
    # Create list of formatted citations
    formatted_list = []
    for citation, resolved in formatted_citations:
        formatted = formatter.format(citation, resolved)
        formatted_list.append(formatted)
    
    # Apply to content
    result = formatter.apply_to_text(article_content, formatted_list)
    
    # Count results
    resolved_count = sum(1 for c in formatted_citations if c[1].url)
    
    print("Article after citation linking:")
    print("-" * 80)
    print(result)
    
    # Summary
    print("\n\n[SUMMARY]")
    print("-" * 80)
    print("✓ Extracted: {} citations".format(len(citations)))
    print("✓ Resolved: {} citations".format(resolved_count))
    print("✓ Resolution rate: {:.1f}%".format(
        (resolved_count / len(citations) * 100) if citations else 0))
    print("✓ Cached entries: {}".format(len(cache.data)))
    
    print("\n[WORKFLOW BENEFITS]")
    print("-" * 80)
    print("1. Automatic citation extraction from generated article content")
    print("2. DOI/arXiv resolution links research to official sources")
    print("3. Caching prevents duplicate API calls (better performance)")
    print("4. Readers can click citations to access original papers")
    print("5. Works with various citation formats (handles et al., missing periods, etc.)")
    
    print("\n[INTEGRATION POINTS]")
    print("-" * 80)
    print("✓ Integrated in: src/generate.py save_article() function")
    print("✓ Config flag: enable_citations (set in .env)")
    print("✓ Cache location: data/citations_cache.json")
    print("✓ Feature flag: ENABLE_CITATIONS=true")
    print("✓ TTL setting: CITATIONS_CACHE_TTL_DAYS=30")
    
    print("\n" + "=" * 80)
    print("WORKFLOW DEMONSTRATION COMPLETE")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    demo_workflow()
