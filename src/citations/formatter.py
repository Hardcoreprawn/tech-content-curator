"""Format resolved citations as markdown links.

Converts Citation + ResolvedCitation pairs into markdown link syntax:
- Input: "Smith et al. (2024)" + resolved URL
- Output: "[Smith et al. (2024)](https://doi.org/10.1234/example)"

Only formats citations with sufficient confidence (>= 0.7).
Lower-confidence matches are left unchanged.
"""

from dataclasses import dataclass

from .extractor import Citation
from .resolver import ResolvedCitation


@dataclass
class FormattedCitation:
    """A formatted citation ready to insert into text.
    
    Attributes:
        markdown: The formatted markdown link or original text
        original: The original citation text
        was_resolved: Whether a URL was found and linked
    """

    markdown: str
    original: str
    was_resolved: bool


class CitationFormatter:
    """Convert citations to markdown links.
    
    Only formats citations with high confidence (default >= 0.7).
    Leaves uncertain citations unchanged.
    """

    def __init__(self, confidence_threshold: float = 0.7) -> None:
        """Initialize formatter.
        
        Args:
            confidence_threshold: Minimum confidence to create a link (0-1)
        """
        self.confidence_threshold = confidence_threshold

    def format(
        self, citation: Citation, resolved: ResolvedCitation
    ) -> FormattedCitation:
        """Convert a citation and its resolution to a formatted citation.
        
        Args:
            citation: The extracted citation
            resolved: The resolved citation with URL
            
        Returns:
            FormattedCitation with markdown link or original text
        """
        # Check if resolution is confident enough
        if (
            not resolved.url
            or resolved.confidence < self.confidence_threshold
        ):
            # Not confident enough - return original unchanged
            return FormattedCitation(
                markdown=citation.original_text,
                original=citation.original_text,
                was_resolved=False,
            )

        # Create markdown link
        markdown = f"[{citation.original_text}]({resolved.url})"

        return FormattedCitation(
            markdown=markdown,
            original=citation.original_text,
            was_resolved=True,
        )

    def apply_to_text(self, text: str, replacements: list[FormattedCitation]) -> str:
        """Apply formatted citations to article text.
        
        Replaces each formatted citation in the text.
        Processes replacements in reverse position order to avoid offset issues.
        
        Args:
            text: The article text to modify
            replacements: List of FormattedCitation objects to apply
            
        Returns:
            Text with citations replaced by markdown links
        """
        # Filter to only resolved citations
        resolved = [r for r in replacements if r.was_resolved]

        # Sort by position in reverse to avoid offset issues when replacing
        # We need to find positions in the text
        sorted_replacements = sorted(
            resolved,
            key=lambda r: text.find(r.original),
            reverse=True,
        )

        # Apply replacements from end to start
        for replacement in sorted_replacements:
            # Only replace first occurrence to avoid double-replacing
            text = text.replace(replacement.original, replacement.markdown, 1)

        return text
