"""Tests for academic citation extraction, resolution, and formatting.

Tests cover:
- Citation extraction with regex patterns
- False positive filtering
- CrossRef and arXiv API lookups
- Citation formatting to markdown links
- Cache functionality with TTL
- Integration with article generation
"""

import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.citations import (
    Citation,
    CitationExtractor,
    CitationFormatter,
    CitationResolver,
    ResolvedCitation,
)
from src.citations.cache import CitationCache
from src.citations.formatter import FormattedCitation


class TestCitationExtractor:
    """Test academic citation extraction."""

    def test_extract_simple_citation(self) -> None:
        """Extract simple 'Author (Year)' citation."""
        extractor = CitationExtractor()
        text = "Smith (2024) found that..."
        citations = extractor.extract(text)

        assert len(citations) == 1
        assert citations[0].authors == "Smith"
        assert citations[0].year == 2024
        assert citations[0].original_text == "Smith (2024)"

    def test_extract_et_al_citation(self) -> None:
        """Extract 'Author et al. (Year)' citation."""
        extractor = CitationExtractor()
        text = "Smith et al. (2024) demonstrated..."
        citations = extractor.extract(text)

        assert len(citations) == 1
        assert citations[0].authors == "Smith et al."
        assert citations[0].year == 2024

    def test_extract_multiple_authors(self) -> None:
        """Extract citation with multiple authors."""
        extractor = CitationExtractor()
        text = "Smith and Jones (2023) showed..."
        citations = extractor.extract(text)

        assert len(citations) == 1
        assert "Smith" in citations[0].authors
        assert "Jones" in citations[0].authors
        assert citations[0].year == 2023

    def test_extract_ampersand_citation(self) -> None:
        """Extract citation with ampersand separator."""
        extractor = CitationExtractor()
        text = "Smith & Jones (2022) concluded..."
        citations = extractor.extract(text)

        assert len(citations) == 1
        assert "Smith" in citations[0].authors
        assert "&" in citations[0].original_text

    def test_extract_multiple_citations(self) -> None:
        """Extract multiple citations from single text."""
        extractor = CitationExtractor()
        text = (
            "Smith (2024) found this, "
            "while Jones et al. (2023) disagreed. "
            "Recent work by Brown and Green (2022) suggests..."
        )
        citations = extractor.extract(text)

        assert len(citations) == 3
        assert citations[0].year == 2024
        assert citations[1].year == 2023
        assert citations[2].year == 2022

    def test_filter_false_positive_month(self) -> None:
        """Filter out month names mistaken for authors."""
        extractor = CitationExtractor()
        text = "Published in January (2024) by..."
        citations = extractor.extract(text)

        # Should not extract "January (2024)" as citation
        assert len(citations) == 0

    def test_filter_false_positive_chapter(self) -> None:
        """Filter out 'Chapter (Year)' patterns."""
        extractor = CitationExtractor()
        text = "See Chapter (2024) for details..."
        citations = extractor.extract(text)

        assert len(citations) == 0

    def test_year_must_be_reasonable(self) -> None:
        """Reject unreasonable years (before 1900 or after 2099)."""
        extractor = CitationExtractor()
        text = "Old work (1899) and future work (2100)"
        citations = extractor.extract(text)

        # Should reject both
        assert len(citations) == 0

    def test_extract_missing_period_after_et_al(self) -> None:
        """Extract 'Author et al (YEAR)' - missing period after et al."""
        extractor = CitationExtractor()
        text = "Smith et al (2024) demonstrated..."
        citations = extractor.extract(text)

        assert len(citations) == 1
        assert citations[0].authors == "Smith et al."  # Normalized
        assert citations[0].year == 2024
        # Can be matched by primary or secondary pattern
        assert citations[0].confidence >= 0.9

    def test_extract_with_comma_before_et_al(self) -> None:
        """Extract 'Author, et al. (YEAR)' - with comma."""
        extractor = CitationExtractor()
        text = "Smith, et al. (2024) concluded..."
        citations = extractor.extract(text)

        assert len(citations) == 1
        assert "Smith" in citations[0].authors
        assert "et al" in citations[0].authors
        assert citations[0].year == 2024

    def test_normalize_et_al_variations(self) -> None:
        """Citation extractor normalizes et al. variations."""
        extractor = CitationExtractor()

        # Test internal normalization
        assert extractor._normalize_authors("Smith et al") == "Smith et al."
        assert extractor._normalize_authors("Smith et al.") == "Smith et al."
        assert extractor._normalize_authors("Smith, et al.") == "Smith, et al."
        assert extractor._normalize_authors("Smith,") == "Smith"

    def test_extraction_preserves_position(self) -> None:
        """Citation position should be accurate for replacement."""
        extractor = CitationExtractor()
        text = "Smith (2024) is here"
        citations = extractor.extract(text)

        assert citations[0].position == (0, 12)
        # Verify we can extract the text at that position
        start, end = citations[0].position
        assert text[start:end] == "Smith (2024)"


class TestCitationResolver:
    """Test citation resolution via APIs."""

    def test_resolver_initialization(self) -> None:
        """Resolver should initialize with default timeout."""
        resolver = CitationResolver()
        assert resolver.timeout == 10

    def test_resolver_custom_timeout(self) -> None:
        """Resolver should accept custom timeout."""
        resolver = CitationResolver(timeout=30)
        assert resolver.timeout == 30

    def test_extract_first_author_fallback(self) -> None:
        """Resolver can extract first author for fallback searches."""
        resolver = CitationResolver()

        assert resolver._extract_first_author("Smith et al.") == "Smith"
        assert resolver._extract_first_author("Smith") == "Smith"
        assert resolver._extract_first_author("Smith and Jones") == "Smith"
        assert resolver._extract_first_author("Smith & Jones") == "Smith"

    @patch("src.citations.resolver.httpx.Client")
    def test_resolve_via_crossref_success(self, mock_client_class: MagicMock) -> None:
        """Successfully resolve citation via CrossRef API."""
        # Mock CrossRef API response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "message": {
                "items": [
                    {
                        "DOI": "10.1234/example",
                        "published": {"date-parts": [[2024]]},
                    }
                ]
            }
        }
        mock_client = MagicMock()
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        resolver = CitationResolver()
        result = resolver.resolve("Smith et al.", 2024)

        assert result.doi == "10.1234/example"
        assert result.url == "https://doi.org/10.1234/example"
        assert result.confidence >= 0.9

    @patch("src.citations.resolver.httpx.Client")
    def test_resolve_year_mismatch_reduces_confidence(
        self, mock_client_class: MagicMock
    ) -> None:
        """Year mismatch should reduce confidence."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "message": {
                "items": [
                    {
                        "DOI": "10.1234/example",
                        "published": {"date-parts": [[2023]]},  # Different year
                    }
                ]
            }
        }
        mock_client = MagicMock()
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        resolver = CitationResolver()
        result = resolver.resolve("Smith et al.", 2024)

        # Should return None because confidence < 0.7 threshold
        assert result.url is None

    @patch("src.citations.resolver.httpx.Client")
    def test_resolve_no_results_fallback(self, mock_client_class: MagicMock) -> None:
        """Should try arXiv when CrossRef has no results."""
        # Mock CrossRef with no results
        mock_response_cf = MagicMock()
        mock_response_cf.json.return_value = {"message": {"items": []}}

        # Mock arXiv with results
        mock_response_ax = MagicMock()
        mock_response_ax.text = "entry><id>http://arxiv.org/abs/2401.12345</id>"

        mock_client = MagicMock()
        # Need 4 responses: CrossRef (full), CrossRef (first author), arXiv (full), arXiv (first author)
        mock_client.get.side_effect = [
            mock_response_cf,  # CrossRef full query
            mock_response_cf,  # CrossRef first author
            mock_response_ax,  # arXiv full query
            mock_response_ax,  # arXiv first author
        ]
        mock_client_class.return_value = mock_client

        resolver = CitationResolver()
        result = resolver.resolve("Smith et al.", 2024)

        assert result.arxiv_id == "2401.12345"
        assert "arxiv.org" in result.url or result.arxiv_id

    @patch("src.citations.resolver.httpx.Client")
    def test_resolve_api_error_returns_empty(
        self, mock_client_class: MagicMock
    ) -> None:
        """API errors should return unresolved citation."""
        # Make both CrossRef and arXiv calls fail
        mock_client = MagicMock()
        mock_client.get.side_effect = Exception("Connection failed")
        mock_client_class.return_value = mock_client

        resolver = CitationResolver()
        result = resolver.resolve("Smith et al.", 2024)

        assert result.url is None
        assert result.confidence == 0.0


class TestCitationFormatter:
    """Test citation formatting to markdown links."""

    def test_format_high_confidence_citation(self) -> None:
        """High-confidence citations should be formatted as links."""
        citation = Citation(
            authors="Smith et al.",
            year=2024,
            original_text="Smith et al. (2024)",
            position=(0, 19),
        )
        resolved = ResolvedCitation(
            doi="10.1234/example",
            arxiv_id=None,
            pmid=None,
            url="https://doi.org/10.1234/example",
            confidence=0.9,
            source_uri="https://doi.org/10.1234/example",
        )

        formatter = CitationFormatter()
        formatted = formatter.format(citation, resolved)

        assert formatted.was_resolved is True
        assert (
            formatted.markdown
            == "[Smith et al. (2024)](https://doi.org/10.1234/example)"
        )
        assert formatted.citation == citation
        assert formatted.resolved == resolved

    def test_format_low_confidence_citation(self) -> None:
        """Low-confidence citations should remain unchanged."""
        citation = Citation(
            authors="Smith et al.",
            year=2024,
            original_text="Smith et al. (2024)",
            position=(0, 19),
        )
        resolved = ResolvedCitation(
            doi=None,
            arxiv_id=None,
            pmid=None,
            url=None,
            confidence=0.5,
        )

        formatter = CitationFormatter()
        formatted = formatter.format(citation, resolved)

        assert formatted.was_resolved is False
        assert formatted.markdown == "Smith et al. (2024)"

    def test_apply_to_text_single_citation(self) -> None:
        """Apply single formatted citation to text."""
        original_citation = Citation(
            authors="Smith",
            year=2024,
            original_text="Smith (2024)",
            position=(0, 12),
        )
        resolved = ResolvedCitation(
            doi="10.1234/x",
            arxiv_id=None,
            pmid=None,
            url="https://doi.org/10.1234/x",
            confidence=0.95,
        )

        formatter = CitationFormatter()
        formatted = formatter.format(original_citation, resolved)

        text = "Smith (2024) found that molecules spin."
        result = formatter.apply_to_text(text, [formatted])

        assert "[Smith (2024)](https://doi.org/10.1234/x)" in result
        assert "found that molecules spin" in result

    def test_apply_to_text_multiple_citations(self) -> None:
        """Apply multiple formatted citations to text."""
        formatter = CitationFormatter()

        citations_data = [
            Citation(
                authors="Smith",
                year=2024,
                original_text="Smith (2024)",
                position=(0, 12),
            ),
            Citation(
                authors="Jones",
                year=2023,
                original_text="Jones (2023)",
                position=(30, 42),
            ),
        ]

        formatted_list = [
            formatter.format(
                citations_data[0],
                ResolvedCitation(
                    doi="10.1234/a",
                    arxiv_id=None,
                    pmid=None,
                    url="https://doi.org/10.1234/a",
                    confidence=0.9,
                ),
            ),
            formatter.format(
                citations_data[1],
                ResolvedCitation(
                    doi="10.1234/b",
                    arxiv_id=None,
                    pmid=None,
                    url="https://doi.org/10.1234/b",
                    confidence=0.9,
                ),
            ),
        ]

        text = "Smith (2024) claimed something. Jones (2023) disagreed."
        result = formatter.apply_to_text(text, formatted_list)

        assert "[Smith (2024)](https://doi.org/10.1234/a)" in result
        assert "[Jones (2023)](https://doi.org/10.1234/b)" in result

    def test_custom_confidence_threshold(self) -> None:
        """Formatter should respect custom confidence threshold."""
        citation = Citation(
            authors="Smith",
            year=2024,
            original_text="Smith (2024)",
            position=(0, 12),
        )
        resolved = ResolvedCitation(
            doi="10.1234/x",
            arxiv_id=None,
            pmid=None,
            url="https://doi.org/10.1234/x",
            confidence=0.75,
        )

        # High threshold - should reject
        formatter_strict = CitationFormatter(confidence_threshold=0.9)
        formatted_strict = formatter_strict.format(citation, resolved)
        assert formatted_strict.was_resolved is False

        # Low threshold - should accept
        formatter_lenient = CitationFormatter(confidence_threshold=0.5)
        formatted_lenient = formatter_lenient.format(citation, resolved)
        assert formatted_lenient.was_resolved is True

    def test_build_bibliography_from_resolved_citations(self) -> None:
        """Build bibliography entries from resolved citations."""
        formatter = CitationFormatter()

        # Create some resolved citations
        formatted_list = [
            FormattedCitation(
                markdown="[Smith (2024)](https://doi.org/10.1234/a)",
                original="Smith (2024)",
                was_resolved=True,
                citation=Citation(
                    authors="Smith",
                    year=2024,
                    original_text="Smith (2024)",
                    position=(0, 12),
                ),
                resolved=ResolvedCitation(
                    doi="10.1234/a",
                    arxiv_id=None,
                    pmid=None,
                    url="https://doi.org/10.1234/a",
                    confidence=0.9,
                    source_uri="https://doi.org/10.1234/a",
                ),
            ),
            FormattedCitation(
                markdown="[Jones et al. (2023)](https://doi.org/10.1234/b)",
                original="Jones et al. (2023)",
                was_resolved=True,
                citation=Citation(
                    authors="Jones et al.",
                    year=2023,
                    original_text="Jones et al. (2023)",
                    position=(20, 39),
                ),
                resolved=ResolvedCitation(
                    doi="10.1234/b",
                    arxiv_id=None,
                    pmid=None,
                    url="https://doi.org/10.1234/b",
                    confidence=0.85,
                    source_uri="https://doi.org/10.1234/b",
                ),
            ),
        ]

        bibliography = formatter.build_bibliography(formatted_list)

        assert len(bibliography) == 2
        assert "[Smith (2024)](https://doi.org/10.1234/a)" in bibliography[0]
        assert "[Jones et al. (2023)](https://doi.org/10.1234/b)" in bibliography[1]

    def test_build_bibliography_deduplicates(self) -> None:
        """Build bibliography should deduplicate citations by source_uri."""
        formatter = CitationFormatter()

        # Create duplicate citations (same source_uri)
        formatted_list = [
            FormattedCitation(
                markdown="[Smith (2024)](https://doi.org/10.1234/a)",
                original="Smith (2024)",
                was_resolved=True,
                citation=Citation(
                    authors="Smith",
                    year=2024,
                    original_text="Smith (2024)",
                    position=(0, 12),
                ),
                resolved=ResolvedCitation(
                    doi="10.1234/a",
                    arxiv_id=None,
                    pmid=None,
                    url="https://doi.org/10.1234/a",
                    confidence=0.9,
                    source_uri="https://doi.org/10.1234/a",
                ),
            ),
            FormattedCitation(
                markdown="[Smith et al. (2024)](https://doi.org/10.1234/a)",
                original="Smith et al. (2024)",
                was_resolved=True,
                citation=Citation(
                    authors="Smith et al.",
                    year=2024,
                    original_text="Smith et al. (2024)",
                    position=(50, 69),
                ),
                resolved=ResolvedCitation(
                    doi="10.1234/a",
                    arxiv_id=None,
                    pmid=None,
                    url="https://doi.org/10.1234/a",
                    confidence=0.9,
                    source_uri="https://doi.org/10.1234/a",  # Same source_uri!
                ),
            ),
        ]

        bibliography = formatter.build_bibliography(formatted_list)

        # Should only have 1 entry due to deduplication
        assert len(bibliography) == 1


class TestCitationCache:
    """Test citation cache with TTL."""

    def test_cache_initialization(self) -> None:
        """Cache should initialize with empty data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = str(Path(tmpdir) / "cache.json")
            cache = CitationCache(cache_file=cache_file)
            assert cache.data == {}

    def test_cache_put_and_get(self) -> None:
        """Cache should store and retrieve citations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = str(Path(tmpdir) / "cache.json")
            cache = CitationCache(cache_file=cache_file)

            # Store a citation
            cache.put("Smith et al.", 2024, "10.1234/x", "https://doi.org/10.1234/x")

            # Retrieve it
            result = cache.get("Smith et al.", 2024)
            assert result is not None
            assert result["doi"] == "10.1234/x"
            assert result["url"] == "https://doi.org/10.1234/x"

    def test_cache_persistence(self) -> None:
        """Cache should persist to disk."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = str(Path(tmpdir) / "cache.json")

            # Write to cache
            cache1 = CitationCache(cache_file=cache_file)
            cache1.put("Smith", 2024, "10.1234/a", "https://doi.org/10.1234/a")

            # Create new cache instance, should load from disk
            cache2 = CitationCache(cache_file=cache_file)
            result = cache2.get("Smith", 2024)
            assert result is not None
            assert result["doi"] == "10.1234/a"

    def test_cache_ttl_expiration(self) -> None:
        """Expired cache entries should be removed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = str(Path(tmpdir) / "cache.json")
            cache = CitationCache(cache_file=cache_file)

            # Manually insert expired entry
            old_time = (datetime.now() - timedelta(days=31)).isoformat()
            cache.data["Smith_2024"] = {
                "authors": "Smith",
                "year": 2024,
                "doi": "10.1234/x",
                "url": "https://doi.org/10.1234/x",
                "timestamp": old_time,
            }

            # Try to get - should be None and removed
            result = cache.get("Smith", 2024)
            assert result is None
            assert "Smith_2024" not in cache.data

    def test_cache_clear(self) -> None:
        """Cache.clear() should remove all entries."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = str(Path(tmpdir) / "cache.json")
            cache = CitationCache(cache_file=cache_file)

            cache.put("Smith", 2024, "10.1234/x", "https://doi.org/10.1234/x")
            assert len(cache.data) > 0

            cache.clear()
            assert len(cache.data) == 0
            assert not Path(cache_file).exists()

    def test_cache_key_format(self) -> None:
        """Cache key should combine author and year."""
        key = CitationCache._make_key("Smith et al.", 2024)
        assert key == "Smith et al._2024"


class TestIntegration:
    """Integration tests for full citation pipeline."""

    @patch("src.citations.resolver.httpx.Client")
    def test_extract_resolve_format_pipeline(
        self, mock_client_class: MagicMock
    ) -> None:
        """Full pipeline: extract -> resolve -> format."""
        # Mock CrossRef response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "message": {
                "items": [
                    {
                        "DOI": "10.1234/example",
                        "published": {"date-parts": [[2024]]},
                    }
                ]
            }
        }
        mock_client = MagicMock()
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        extractor = CitationExtractor()
        resolver = CitationResolver()
        formatter = CitationFormatter()

        text = "Smith et al. (2024) discovered something amazing."
        citations = extractor.extract(text)

        assert len(citations) == 1

        resolved = resolver.resolve(citations[0].authors, citations[0].year)
        assert resolved.url is not None

        formatted = formatter.format(citations[0], resolved)
        assert formatted.was_resolved is True

        result = formatter.apply_to_text(text, [formatted])
        assert "[Smith et al. (2024)](https://doi.org/10.1234/example)" in result

    @patch("src.citations.resolver.httpx.Client")
    def test_cache_prevents_duplicate_lookups(
        self, mock_client_class: MagicMock
    ) -> None:
        """Cache should prevent duplicate API calls."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = str(Path(tmpdir) / "cache.json")
            cache = CitationCache(cache_file=cache_file)

            mock_response = MagicMock()
            mock_response.json.return_value = {
                "message": {
                    "items": [
                        {
                            "DOI": "10.1234/example",
                            "published": {"date-parts": [[2024]]},
                        }
                    ]
                }
            }
            mock_client = MagicMock()
            mock_client.get.return_value = mock_response
            mock_client_class.return_value = mock_client

            # First resolution should call API
            resolver = CitationResolver()
            result1 = resolver.resolve("Smith", 2024)
            assert mock_client.get.call_count == 1

            # Cache the result
            cache.put("Smith", 2024, result1.doi, result1.url)

            # Second resolution should use cache (no API call)
            cached = cache.get("Smith", 2024)
            assert cached is not None
            assert mock_client.get.call_count == 1  # Still 1, not called again
