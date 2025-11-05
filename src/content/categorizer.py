"""Article categorization and metadata tagging.

This module categorizes articles by content type (tutorial, news, analysis, etc.),
difficulty level (beginner, intermediate, advanced), and target audience.
"""

from enum import Enum

from ..models import EnrichedItem
from ..utils.logging import get_logger

logger = get_logger(__name__)


class ContentType(str, Enum):
    """Enumeration of article content types."""

    TUTORIAL = "tutorial"
    NEWS = "news"
    ANALYSIS = "analysis"
    RESEARCH = "research"
    GUIDE = "guide"
    GENERAL = "general"


class DifficultyLevel(str, Enum):
    """Enumeration of article difficulty levels."""

    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class ArticleCategorizer:
    """Categorize articles by type, difficulty, and target audience."""

    def categorize(self, item: EnrichedItem, content: str) -> dict:
        """Categorize an article and return metadata.

        Args:
            item: The enriched item
            content: The generated article content

        Returns:
            Dictionary with keys:
            - content_type: Primary content type
            - difficulty_level: Estimated difficulty
            - audience: List of target audience segments
            - estimated_read_time: Human-readable reading time
        """
        logger.debug(f"Starting categorization for item: {item.original.title[:50]}")

        result = {
            "content_type": self._detect_content_type(item),
            "difficulty_level": self._detect_difficulty(item, content),
            "audience": self._detect_audience(item),
            "estimated_read_time": self._calculate_read_time(content),
        }

        logger.debug(
            f"Categorization result: type={result['content_type']}, "
            f"difficulty={result['difficulty_level']}, "
            f"audiences={len(result['audience'])}"
        )
        return result

    def _detect_content_type(self, item: EnrichedItem) -> str:
        """Detect primary content type from item metadata.

        Args:
            item: The enriched item to analyze

        Returns:
            ContentType value as string
        """
        text = (item.original.title + " " + " ".join(item.topics)).lower()
        logger.debug(f"Detecting content type from: {text[:60]}")

        # Tutorial indicators
        if any(
            k in text
            for k in ["how to", "guide", "tutorial", "step by step", "getting started"]
        ):
            logger.debug("Detected content type: TUTORIAL")
            return ContentType.TUTORIAL.value

        # News indicators
        if any(
            k in text for k in ["announced", "released", "launched", "breaking", "news"]
        ):
            logger.debug("Detected content type: NEWS")
            return ContentType.NEWS.value

        # Analysis indicators
        if any(
            k in text
            for k in ["analysis", "review", "comparison", "deep dive", "benchmark"]
        ):
            logger.debug("Detected content type: ANALYSIS")
            return ContentType.ANALYSIS.value

        # Research indicators
        if any(
            k in text for k in ["research", "study", "paper", "findings", "academic"]
        ):
            logger.debug("Detected content type: RESEARCH")
            return ContentType.RESEARCH.value

        # Guide indicators
        if any(
            k in text
            for k in ["getting started", "introduction to", "overview", "primer"]
        ):
            logger.debug("Detected content type: GUIDE")
            return ContentType.GUIDE.value

        logger.debug("Detected content type: GENERAL (default)")
        return ContentType.GENERAL.value

    def _detect_difficulty(self, item: EnrichedItem, content: str) -> str:
        """Estimate difficulty level from content and metadata.

        Args:
            item: The enriched item
            content: The article content

        Returns:
            DifficultyLevel value as string
        """
        text = content.lower()

        # Beginner indicators
        beginner_keywords = [
            "introduction",
            "getting started",
            "basics",
            "beginner",
            "simple",
            "easy",
            "first time",
            "new to",
            "what is",
            "explain",
        ]
        beginner_score = sum(1 for k in beginner_keywords if k in text)

        # Advanced indicators
        advanced_keywords = [
            "advanced",
            "optimization",
            "internals",
            "architecture",
            "performance tuning",
            "deep dive",
            "complex",
            "sophisticated",
            "low-level",
            "under the hood",
        ]
        advanced_score = sum(1 for k in advanced_keywords if k in text)

        # Code complexity (rough proxy)
        code_blocks = text.count("```")
        has_complex_code = code_blocks > 5

        # Calculus/math complexity
        has_math = "$" in content or "equation" in text or "formula" in text

        if advanced_score >= 2 or has_complex_code or has_math:
            return DifficultyLevel.ADVANCED.value
        elif beginner_score >= 2:
            return DifficultyLevel.BEGINNER.value
        else:
            return DifficultyLevel.INTERMEDIATE.value

    def _detect_audience(self, item: EnrichedItem) -> list[str]:
        """Identify target audiences from topics.

        Args:
            item: The enriched item to analyze

        Returns:
            List of target audience segment names
        """
        audiences = []
        topics_text = " ".join(item.topics).lower()

        # DevOps/Infrastructure audience
        if any(
            k in topics_text
            for k in [
                "devops",
                "kubernetes",
                "docker",
                "ci/cd",
                "infrastructure",
                "deployment",
            ]
        ):
            audiences.append("DevOps Engineers")

        # Software Developers
        if any(
            k in topics_text
            for k in [
                "python",
                "javascript",
                "rust",
                "go",
                "java",
                "typescript",
                "programming",
                "code",
            ]
        ):
            audiences.append("Software Developers")

        # Security Professionals
        if any(
            k in topics_text
            for k in [
                "security",
                "privacy",
                "encryption",
                "vulnerability",
                "cve",
                "attack",
            ]
        ):
            audiences.append("Security Professionals")

        # Data Scientists / ML Engineers
        if any(
            k in topics_text
            for k in ["data", "machine learning", "ai", "analytics", "neural", "model"]
        ):
            audiences.append("Data Scientists")

        # Self-Hosters / Home Lab
        if any(
            k in topics_text
            for k in [
                "self-hosted",
                "home lab",
                "raspberry pi",
                "self-hosting",
                "open source",
            ]
        ):
            audiences.append("Self-Hosters")

        # System Administrators
        if any(
            k in topics_text
            for k in ["linux", "windows", "admin", "system", "network", "server"]
        ):
            audiences.append("System Administrators")

        # Fallback if no specific audience detected
        if not audiences:
            audiences.append("Tech Professionals")

        return audiences

    def _calculate_read_time(self, content: str) -> str:
        """Calculate estimated reading time.

        Uses average reading speed of 200-250 words per minute.

        Args:
            content: The article content

        Returns:
            Human-readable reading time string (e.g., "5 min read")
        """
        word_count = len(content.split())
        # Average reading speed: 200-250 wpm, use 225
        minutes = max(1, round(word_count / 225))
        return f"{minutes} min read"
