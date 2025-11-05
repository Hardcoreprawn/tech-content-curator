"""Resolve citations to DOIs and arXiv links via free public APIs.

Uses two free APIs with no authentication required:
1. CrossRef (https://api.crossref.org) - for journal articles and DOIs
2. arXiv (https://arxiv.org/api) - for preprints and research papers

Both APIs have generous rate limits and no authentication requirements.
"""

from dataclasses import dataclass

import httpx
from rich.console import Console

from ..utils.logging import get_logger

logger = get_logger(__name__)
# Rich console for styled output
console = Console()


@dataclass
class ResolvedCitation:
    """Resolution result for a citation.

    Attributes:
        doi: Digital Object Identifier if found
        arxiv_id: arXiv preprint ID if found
        pmid: PubMed ID if found
        url: Full URL to the resolved paper
        confidence: Confidence score (0-1) for the resolution
        source_uri: The actual URI/URL where the citation was found (for bibliography)
    """

    doi: str | None
    arxiv_id: str | None
    pmid: str | None
    url: str | None
    confidence: float
    source_uri: str | None = None


class CitationResolver:
    """Look up academic citations via free public APIs.

    Strategy:
    1. Try CrossRef first (covers most published journals)
    2. Fall back to arXiv (covers preprints and CS papers)
    3. Return unresolved if both fail

    All APIs are free and don't require authentication.
    """

    CROSSREF_URL = "https://api.crossref.org/v1/works"
    ARXIV_URL = "https://export.arxiv.org/api/query"  # Use https and allows redirects

    def __init__(self, timeout: int | None = None) -> None:
        """Initialize the resolver.

        Args:
            timeout: HTTP request timeout in seconds (uses config default if not provided)
        """
        from ..config import get_config

        if timeout is None:
            config = get_config()
            timeout = config.timeouts.citation_resolver_timeout
        self.timeout = timeout
        # Create httpx client with redirect handling enabled by default
        self.client = httpx.Client(follow_redirects=True, timeout=timeout)

    def resolve(self, authors: str, year: int) -> ResolvedCitation:
        """Resolve a citation to DOI or arXiv link.

        Tries multiple strategies:
        1. Direct CrossRef lookup with original authors
        2. CrossRef with first author only (handles et al. variations)
        3. arXiv lookup

        Args:
            authors: Author string (e.g., "Smith et al.")
            year: Publication year

        Returns:
            ResolvedCitation with URL and metadata if found
        """
        logger.debug(f"Resolving citation: {authors} ({year})")

        # Try CrossRef (most comprehensive for journal articles)
        result = self._search_crossref(authors, year)
        if result:
            logger.info(f"Resolved via CrossRef: {authors} ({year}) -> {result.url}")
            return result

        # Try with first author only (handles "et al." variations)
        first_author = self._extract_first_author(authors)
        if first_author and first_author != authors:
            logger.debug(f"Trying first author only: {first_author}")
            result = self._search_crossref(first_author, year)
            if result:
                logger.info(
                    f"Resolved via CrossRef (first author): {first_author} ({year}) -> {result.url}"
                )
                return result

        # Try arXiv (good for preprints and CS papers)
        result = self._search_arxiv(authors, year)
        if result:
            logger.info(f"Resolved via arXiv: {authors} ({year}) -> {result.url}")
            return result

        # Try arXiv with first author only
        if first_author and first_author != authors:
            result = self._search_arxiv(first_author, year)
            if result:
                logger.info(
                    f"Resolved via arXiv (first author): {first_author} ({year}) -> {result.url}"
                )
                return result

        # No match found
        logger.debug(f"Could not resolve citation: {authors} ({year})")
        from ..config import get_config

        config = get_config()
        return ResolvedCitation(
            doi=None,
            arxiv_id=None,
            pmid=None,
            url=None,
            confidence=config.confidences.citation_baseline,
            source_uri=None,
        )

    def _extract_first_author(self, authors: str) -> str | None:
        """Extract first author name for fallback queries.

        Handles "Smith et al.", "Smith and Jones", etc.
        Returns just the first author: "Smith"

        Args:
            authors: Full author string

        Returns:
            First author name or None
        """
        import re

        # Match first author name before et al, and, or, &
        match = re.match(r"([A-Z][a-z]+)", authors)
        if match:
            return match.group(1)
        return None

    def _search_crossref(self, authors: str, year: int) -> ResolvedCitation | None:
        """Query CrossRef API for a citation.

        FREE API, no authentication required.
        Rate limit: Unlimited for good-faith use.

        Args:
            authors: Author string
            year: Publication year

        Returns:
            ResolvedCitation if found, None otherwise
        """
        try:
            response = self.client.get(
                self.CROSSREF_URL,
                params={"query": f"{authors} {year}", "rows": 1},
            )
            response.raise_for_status()
            data = response.json()

            # Check if we got results
            items = data.get("message", {}).get("items", [])
            if not items:
                return None

            item = items[0]

            # Extract year from published date
            published_year = None
            date_parts = item.get("published", {}).get("date-parts")
            if date_parts and isinstance(date_parts, list) and date_parts[0]:
                published_year = date_parts[0][0]

            # Calculate confidence based on year match
            from ..config import get_config

            config = get_config()
            confidence = (
                config.confidences.citation_exact_year_match
                if published_year == year
                else config.confidences.citation_partial_year_match
            )

            # Skip low-confidence matches
            if confidence < 0.7:
                return None

            doi = item.get("DOI")
            if not doi:
                return None

            return ResolvedCitation(
                doi=doi,
                arxiv_id=None,
                pmid=None,
                url=f"https://doi.org/{doi}",
                confidence=confidence,
                source_uri=f"https://doi.org/{doi}",
            )

        except Exception as e:
            console.print(f"[yellow]CrossRef lookup failed: {e}[/yellow]")
            return None

    def _search_arxiv(self, authors: str, year: int) -> ResolvedCitation | None:
        """Query arXiv API for a preprint.

        FREE API, no authentication required.
        Rate limit: Generous, designed for research

        Args:
            authors: Author string (primary author)
            year: Publication year

        Returns:
            ResolvedCitation if found, None otherwise
        """
        try:
            # arXiv API search query syntax
            # Searches by author and submission year
            query = (
                f'au:"{authors}" AND submittedDate:'
                f"[{year}0101000000 TO {year}1231235959]"
            )

            response = self.client.get(
                self.ARXIV_URL,
                params={"search_query": query, "max_results": 1},
                follow_redirects=True,  # Explicitly ensure redirects are followed
            )
            response.raise_for_status()

            # Parse XML response for arXiv ID
            text = response.text
            if "entry" not in text:
                return None

            # Extract arXiv ID from URL
            import re

            match = re.search(r"arxiv\.org/abs/([\d.]+)", text)
            if match:
                from ..config import get_config

                config = get_config()
                arxiv_id = match.group(1)
                return ResolvedCitation(
                    doi=None,
                    arxiv_id=arxiv_id,
                    pmid=None,
                    url=f"https://arxiv.org/abs/{arxiv_id}",
                    confidence=config.confidences.citation_extracted_bibtex,
                    source_uri=f"https://arxiv.org/abs/{arxiv_id}",
                )

        except httpx.HTTPError as e:
            console.print(f"[yellow]arXiv lookup failed: {e}[/yellow]")
            return None
        except Exception as e:
            console.print(f"[yellow]arXiv parsing failed: {e}[/yellow]")
            return None

        return None

    def close(self) -> None:
        """Close the HTTP client and clean up resources."""
        if hasattr(self, "client"):
            self.client.close()

    def __del__(self) -> None:
        """Cleanup when resolver is garbage collected."""
        self.close()
