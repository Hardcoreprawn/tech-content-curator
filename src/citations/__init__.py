"""Academic citation extraction, resolution, and formatting.

This module provides functionality to:
1. Extract academic citations from article text using regex patterns
2. Resolve citations to DOIs/arXiv links via free APIs
3. Format citations as markdown links
4. Cache resolutions to avoid re-querying

All external APIs used are free and require no authentication:
- CrossRef (DOI lookup)
- arXiv (preprint search)

Example:
    >>> from src.citations import CitationExtractor, CitationResolver, CitationFormatter
    >>> extractor = CitationExtractor()
    >>> citations = extractor.extract("Smith et al. (2024) found...")
    >>> resolver = CitationResolver()
    >>> formatter = CitationFormatter()
    >>> for citation in citations:
    ...     resolved = resolver.resolve(citation.authors, citation.year)
    ...     formatted = formatter.format(citation, resolved)
"""

from .extractor import Citation, CitationExtractor
from .formatter import CitationFormatter, FormattedCitation
from .resolver import CitationResolver, ResolvedCitation

__all__ = [
    "Citation",
    "CitationExtractor",
    "CitationResolver",
    "ResolvedCitation",
    "CitationFormatter",
    "FormattedCitation",
]
