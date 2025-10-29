"""Base generator class for article generation.

All generators should inherit from BaseGenerator and implement the required methods.
"""

from abc import ABC, abstractmethod

from openai import OpenAI

from ..models import EnrichedItem


class BaseGenerator(ABC):
    """Abstract base class for article generators."""

    def __init__(self, client: OpenAI | None = None):
        """Initialize generator with OpenAI client.

        Args:
            client: Configured OpenAI client instance (optional for can_handle checks)
        """
        self.client = client

    @abstractmethod
    def can_handle(self, item: EnrichedItem) -> bool:
        """Check if this generator can handle the given item.

        Args:
            item: The enriched item to check

        Returns:
            True if this generator should handle this item
        """
        pass

    @abstractmethod
    def generate_content(self, item: EnrichedItem) -> tuple[str, int, int]:
        """Generate article content for the item.

        Args:
            item: The enriched item to generate content for

        Returns:
            Tuple of (article content as markdown string, input tokens, output tokens)
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name for this generator."""
        pass

    @property
    def priority(self) -> int:
        """Priority for generator selection (higher = checked first).

        Default is 0. Specialized generators should have higher priority
        to be checked before general generators.

        Returns:
            Priority value (0-100)
        """
        return 0
