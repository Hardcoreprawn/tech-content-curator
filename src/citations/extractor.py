"""Extract academic citations from text using regex patterns and fuzzy matching.

Detects citations in the format:
- "Author(s) (YEAR)"
- "Author(s) et al. (YEAR)"
- "Author(s) & Author(s) (YEAR)"

Also handles variations like:
- "Author et al (YEAR)" (missing period)
- "Author, et al. (YEAR)" (with comma)
- "Author(s) YEAR" (missing parentheses - less reliable)

Filters false positives like month names, section references, etc.
"""

import re
from dataclasses import dataclass


@dataclass
class Citation:
    """A detected academic citation.

    Attributes:
        authors: Author names (e.g., "Smith et al.")
        year: Publication year (4-digit integer)
        original_text: Full matched text for replacement
        position: (start, end) tuple of match position in text
        confidence: Extraction confidence (0-1)
    """

    authors: str
    year: int
    original_text: str
    position: tuple[int, int]
    confidence: float = 1.0


class CitationExtractor:
    """Extract academic citations from text using regex patterns.

    The regex pattern matches multiple citation formats:
    - "Smith (2024)" - single author with year
    - "Smith et al. (2024)" - et al notation
    - "Smith & Jones (2024)" - ampersand notation
    - "Smith et al (2024)" - missing period
    - "Smith, et al. (2024)" - with comma

    Then filters out false positives like month names.
    Also attempts to handle poorly formatted citations by trying variations.
    """

    # Primary pattern: standard academic citation format
    # Matches: "Author(s) (YEAR)" or "Author(s) et al. (YEAR)"
    PRIMARY_CITATION_PATTERN = (
        r"([A-Z][a-z]+(?:\s+(?:et al\.?|&|and)\s+)?(?:[A-Z][a-z]+)*)\s*\((\d{4})\)"
    )

    # Secondary pattern: missing period after et al
    # Matches: "Author et al (YEAR)"
    SECONDARY_CITATION_PATTERN = r"([A-Z][a-z]+\s+et\s+al)\s*\((\d{4})\)"

    # Tertiary pattern: with comma before et al
    # Matches: "Author, et al. (YEAR)"
    TERTIARY_CITATION_PATTERN = r"([A-Z][a-z]+,\s+et\s+al\.?)\s*\((\d{4})\)"

    # Common false positives to filter out
    FALSE_POSITIVES = {
        "Chapter",
        "Section",
        "Figure",
        "Table",
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
        "According",
        "Available",
        "Based",
        "Located",
        "Retrieved",
    }

    def extract(self, text: str) -> list[Citation]:
        """Extract all academic citations from text.

        Uses multiple patterns to catch variations and poorly formatted citations.
        Returns citations in order of appearance, with confidence scores.

        Args:
            text: Article text to search for citations

        Returns:
            List of Citation objects found, in order of appearance
        """
        citations: list[Citation] = []
        seen_positions: set[tuple[int, int]] = set()

        # Try primary pattern first (most reliable)
        citations.extend(
            self._extract_with_pattern(
                text,
                self.PRIMARY_CITATION_PATTERN,
                confidence=1.0,
                seen_positions=seen_positions,
            )
        )

        # Try secondary pattern (missing period)
        citations.extend(
            self._extract_with_pattern(
                text,
                self.SECONDARY_CITATION_PATTERN,
                confidence=0.9,
                seen_positions=seen_positions,
            )
        )

        # Try tertiary pattern (with comma)
        citations.extend(
            self._extract_with_pattern(
                text,
                self.TERTIARY_CITATION_PATTERN,
                confidence=0.85,
                seen_positions=seen_positions,
            )
        )

        # Sort by position to maintain order
        citations.sort(key=lambda c: c.position[0])
        return citations

    def _extract_with_pattern(
        self,
        text: str,
        pattern: str,
        confidence: float,
        seen_positions: set[tuple[int, int]],
    ) -> list[Citation]:
        """Extract citations using a specific pattern.

        Args:
            text: Text to search
            pattern: Regex pattern to use
            confidence: Confidence score for matches with this pattern
            seen_positions: Set of already-found positions to avoid duplicates

        Returns:
            List of Citation objects found
        """
        citations: list[Citation] = []

        for match in re.finditer(pattern, text):
            authors = match.group(1).strip()
            year_str = match.group(2)
            position = match.span()

            # Skip if we already found citation at this position
            if position in seen_positions:
                continue

            # Skip false positives
            if self._is_false_positive(authors):
                continue

            # Validate year is reasonable (1900-2099)
            try:
                year = int(year_str)
                if year < 1900 or year > 2099:
                    continue
            except ValueError:
                continue

            # Normalize author string (remove trailing comma, etc.)
            authors = self._normalize_authors(authors)

            citation = Citation(
                authors=authors,
                year=year,
                original_text=match.group(0),
                position=position,
                confidence=confidence,
            )
            citations.append(citation)
            seen_positions.add(position)

        return citations

    def _normalize_authors(self, text: str) -> str:
        """Normalize author string for better matching.

        Args:
            text: Raw author text

        Returns:
            Normalized author string
        """
        # Remove trailing commas
        text = text.rstrip(",")
        # Normalize "et al" variations
        text = re.sub(r"\bet\s+al\.?", "et al.", text, flags=re.IGNORECASE)
        return text.strip()

    def _is_false_positive(self, text: str) -> bool:
        """Check if text matches known false positive patterns.

        Args:
            text: Text to check

        Returns:
            True if text is likely a false positive
        """
        return text in self.FALSE_POSITIVES
