"""Article readability analysis using standard metrics.

This module provides readability scoring using multiple established formulas
to ensure articles are appropriately accessible for their target audience.
"""

from dataclasses import dataclass

import textstat

from ..utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ReadabilityScore:
    """Container for readability analysis results."""

    flesch_reading_ease: float
    """Flesch Reading Ease score (0-100, higher = easier)"""

    grade_level: float
    """Flesch-Kincaid Grade Level (U.S. school grade)"""

    fog_index: float
    """Gunning Fog Index (years of formal education needed)"""

    smog_index: float
    """SMOG Index (years of education for 100% comprehension)"""

    overall_rating: str
    """Human-readable difficulty: very_easy, easy, medium, difficult, very_difficult"""

    recommendations: list[str]
    """List of actionable improvement suggestions"""


class ReadabilityAnalyzer:
    """Analyze article readability using multiple standard metrics."""

    def analyze(self, content: str) -> ReadabilityScore:
        """Calculate all readability metrics for the given content.

        Args:
            content: The article text to analyze

        Returns:
            ReadabilityScore containing all metrics and recommendations
        """
        logger.debug(f"Starting readability analysis ({len(content)} chars)")

        # Calculate core metrics using textstat
        flesch_ease = textstat.flesch_reading_ease(content)
        grade_level = textstat.flesch_kincaid_grade(content)
        fog_index = textstat.gunning_fog(content)
        smog_index = textstat.smog_index(content)

        # Determine overall rating based on Flesch Reading Ease
        overall_rating = self._rate_difficulty(flesch_ease)

        # Generate recommendations
        recommendations = self._suggest_improvements(
            flesch_ease, grade_level, fog_index, smog_index, content
        )

        logger.debug(
            f"Readability metrics: flesch={flesch_ease:.1f}, "
            f"grade={grade_level:.1f}, rating={overall_rating}"
        )

        return ReadabilityScore(
            flesch_reading_ease=flesch_ease,
            grade_level=grade_level,
            fog_index=fog_index,
            smog_index=smog_index,
            overall_rating=overall_rating,
            recommendations=recommendations,
        )

    def _rate_difficulty(self, flesch_ease: float) -> str:
        """Convert Flesch Reading Ease to human-readable rating.

        Args:
            flesch_ease: Flesch Reading Ease score (0-100)

        Returns:
            Rating string: very_easy, easy, medium, difficult, very_difficult
        """
        if flesch_ease >= 80:
            return "very_easy"
        elif flesch_ease >= 60:
            return "easy"
        elif flesch_ease >= 50:
            return "medium"
        elif flesch_ease >= 30:
            return "difficult"
        else:
            return "very_difficult"

    def _suggest_improvements(
        self,
        flesch_ease: float,
        grade_level: float,
        fog_index: float,
        smog_index: float,
        content: str,
    ) -> list[str]:
        """Generate actionable recommendations based on scores.

        Args:
            flesch_ease: Flesch Reading Ease score
            grade_level: Grade level score
            fog_index: Gunning Fog Index
            smog_index: SMOG Index
            content: The article content

        Returns:
            List of specific improvement suggestions
        """
        suggestions = []

        # Analyze sentence and word complexity
        sentence_count = textstat.sentence_count(content)
        word_count = textstat.lexicon_count(content, removepunct=True)
        avg_sentence_length = word_count / sentence_count if sentence_count > 0 else 0

        # Too difficult (low Flesch score)
        if flesch_ease < 30:
            suggestions.append(
                "Content is very difficult. Consider breaking down complex concepts into simpler terms."
            )
            suggestions.append("Use more concrete examples and avoid excessive jargon.")

        if flesch_ease < 50:
            suggestions.append(
                "Readability is challenging. Try shorter sentences and simpler vocabulary."
            )

        # Long sentences
        if avg_sentence_length > 25:
            suggestions.append(
                f"Average sentence length is {avg_sentence_length:.1f} words. "
                "Aim for 15-20 words per sentence for better readability."
            )

        # High grade level for general content
        if grade_level > 14:
            suggestions.append(
                f"Grade level is {grade_level:.1f} (college+). "
                "Consider simplifying for broader accessibility unless targeting advanced readers."
            )

        # High fog index
        if fog_index > 14:
            suggestions.append(
                f"Fog index is {fog_index:.1f}. Reduce complex words and sentence length."
            )

        # No issues found
        if not suggestions:
            suggestions.append("Readability is well-balanced for the content type.")

        return suggestions

    def matches_target_difficulty(
        self, readability: ReadabilityScore, target_difficulty: str
    ) -> tuple[bool, str]:
        """Check if readability matches the target difficulty level.

        Args:
            readability: The calculated readability scores
            target_difficulty: Target difficulty (beginner, intermediate, advanced)

        Returns:
            Tuple of (matches: bool, explanation: str)
        """
        flesch = readability.flesch_reading_ease
        logger.debug(
            f"Checking readability match: target={target_difficulty}, flesch={flesch:.1f}"
        )

        # Define acceptable ranges for each difficulty level via dispatch
        def _check_beginner() -> tuple[bool, str]:
            """Beginners need easier content (Flesch 60-100)."""
            if flesch >= 60:
                logger.debug("Readability matches beginner level")
                return True, "Readability is appropriate for beginners."
            else:
                logger.debug(
                    f"Readability too difficult for beginner level (need 60+, got {flesch:.1f})"
                )
                return (
                    False,
                    f"Too difficult for beginners (Flesch: {flesch:.1f}, need 60+). "
                    "Simplify language and sentence structure.",
                )

        def _check_intermediate() -> tuple[bool, str]:
            """Intermediate readers (Flesch 50-70)."""
            if 50 <= flesch <= 70:
                logger.debug("Readability matches intermediate level")
                return True, "Readability is appropriate for intermediate readers."
            elif flesch > 70:
                logger.debug(
                    f"Readability too easy for intermediate level ({flesch:.1f})"
                )
                return (
                    False,
                    f"Too easy for intermediate readers (Flesch: {flesch:.1f}). "
                    "Can introduce more technical depth.",
                )
            else:
                logger.debug(
                    f"Readability too difficult for intermediate level ({flesch:.1f})"
                )
                return (
                    False,
                    f"Too difficult for intermediate readers (Flesch: {flesch:.1f}, need 50-70). "
                    "Simplify complex sentences.",
                )

        def _check_advanced() -> tuple[bool, str]:
            """Advanced readers can handle complex content (Flesch 30-60)."""
            if 30 <= flesch <= 60:
                logger.debug("Readability matches advanced level")
                return True, "Readability is appropriate for advanced readers."
            elif flesch > 60:
                logger.debug(
                    f"Readability too simple for advanced level ({flesch:.1f})"
                )
                return (
                    False,
                    f"Too simple for advanced readers (Flesch: {flesch:.1f}). "
                    "Can use more precise technical terminology.",
                )
            else:
                logger.debug(
                    f"Readability very technical for advanced level ({flesch:.1f})"
                )
                return (
                    True,
                    f"Very technical (Flesch: {flesch:.1f}), acceptable for advanced readers.",
                )

        difficulty_checkers = {
            "beginner": _check_beginner,
            "intermediate": _check_intermediate,
            "advanced": _check_advanced,
        }

        checker = difficulty_checkers.get(target_difficulty)
        if checker:
            return checker()

        else:
            # Unknown difficulty level
            logger.debug(f"Unknown target difficulty: {target_difficulty}")
            return True, f"Unknown difficulty level: {target_difficulty}"
