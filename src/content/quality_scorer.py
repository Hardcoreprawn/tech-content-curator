"""Multi-dimensional article quality scoring system.

This module evaluates article quality across multiple dimensions including
readability, structure, citations, code examples, and content completeness.
"""

import re
from dataclasses import dataclass

from ..models import GeneratedArticle
from .readability import ReadabilityAnalyzer


@dataclass
class QualityScore:
    """Container for comprehensive quality analysis results."""

    overall_score: float
    """Overall quality score (0-100)"""

    dimension_scores: dict[str, float]
    """Scores for each quality dimension"""

    passed_threshold: bool
    """Whether article meets minimum quality standards"""

    improvement_suggestions: list[str]
    """Actionable recommendations for improvement"""


class QualityScorer:
    """Multi-dimensional article quality scoring system."""

    def __init__(self, readability_analyzer: ReadabilityAnalyzer | None = None):
        """Initialize quality scorer.

        Args:
            readability_analyzer: Optional ReadabilityAnalyzer instance.
                                If None, creates a new one.
        """
        self.readability_analyzer = readability_analyzer or ReadabilityAnalyzer()

    def score(
        self,
        article: GeneratedArticle,
        content: str,
        min_threshold: float = 70.0,
    ) -> QualityScore:
        """Calculate comprehensive quality score for an article.

        Args:
            article: The generated article with metadata
            content: The article content text
            min_threshold: Minimum passing score (0-100)

        Returns:
            QualityScore with overall score, dimension scores, and suggestions
        """
        # Calculate individual dimension scores
        readability_score = self._score_readability(article, content)
        structure_score = self._score_structure(content)
        citation_score = self._score_citations(
            content, article.content_type or "general"
        )
        code_score = self._score_code_examples(
            content, article.content_type or "general"
        )
        length_score = self._score_length(content, article.content_type or "general")
        tone_score = self._score_tone(content, article.content_type or "general")

        # Store dimension scores
        dimension_scores = {
            "readability": readability_score,
            "structure": structure_score,
            "citations": citation_score,
            "code_examples": code_score,
            "length": length_score,
            "tone": tone_score,
        }

        # Calculate weighted overall score
        weights = {
            "readability": 0.25,
            "structure": 0.20,
            "citations": 0.15,
            "code_examples": 0.15,
            "length": 0.15,
            "tone": 0.10,
        }

        overall_score = sum(dimension_scores[dim] * weights[dim] for dim in weights)

        # Check if passed threshold
        passed = overall_score >= min_threshold

        # Generate improvement suggestions
        suggestions = self._generate_suggestions(dimension_scores, article, content)

        return QualityScore(
            overall_score=overall_score,
            dimension_scores=dimension_scores,
            passed_threshold=passed,
            improvement_suggestions=suggestions,
        )

    def _score_readability(self, article: GeneratedArticle, content: str) -> float:
        """Score readability match to target difficulty.

        Args:
            article: Article with difficulty_level metadata
            content: Article content

        Returns:
            Score 0-100
        """
        readability = self.readability_analyzer.analyze(content)
        difficulty = article.difficulty_level or "intermediate"

        matches, _ = self.readability_analyzer.matches_target_difficulty(
            readability, difficulty
        )

        if matches:
            # Full marks if matches target
            return 100.0

        # Partial credit based on how close
        flesch = readability.flesch_reading_ease

        if difficulty == "beginner":
            # Want 60+, penalize if lower
            return min(100.0, max(0.0, (flesch / 60) * 100))
        elif difficulty == "intermediate":
            # Want 50-70, penalize if outside
            if flesch < 50:
                return min(100.0, max(0.0, (flesch / 50) * 100))
            elif flesch > 70:
                return min(100.0, max(0.0, (140 - flesch) / 70 * 100))
            else:
                return 100.0
        elif difficulty == "advanced":
            # Want 30-60, more flexible
            if 30 <= flesch <= 60:
                return 100.0
            elif flesch > 60:
                return min(100.0, max(60.0, (120 - flesch) / 60 * 100))
            else:
                return min(100.0, max(60.0, (flesch / 30) * 100))

        return 70.0  # Default for unknown difficulty

    def _score_structure(self, content: str) -> float:
        """Score article structure completeness.

        Args:
            content: Article content

        Returns:
            Score 0-100
        """
        score = 0.0

        # Check for key structural elements
        has_headings = bool(re.search(r"^##+ ", content, re.MULTILINE))
        has_key_takeaways = "key takeaway" in content.lower()
        has_conclusion = any(
            word in content.lower() for word in ["conclusion", "summary", "takeaway"]
        )
        has_intro = len(content.split("\n\n")[0]) > 100  # Substantial intro

        # Award points for each element
        if has_headings:
            score += 40.0
        if has_key_takeaways:
            score += 20.0
        if has_conclusion:
            score += 20.0
        if has_intro:
            score += 20.0

        return min(100.0, score)

    def _score_citations(self, content: str, content_type: str) -> float:
        """Score citation quality and quantity.

        Args:
            content: Article content
            content_type: Type of content (research, analysis, etc.)

        Returns:
            Score 0-100
        """
        # Count citation patterns (Author et al., Year) or (Author, Year)
        citation_pattern = r"\b[A-Z][a-z]+(?:\s+et\s+al\.)?\s*\(\d{4}\)"
        citations = re.findall(citation_pattern, content)
        citation_count = len(citations)

        # Expected citations by content type
        expected = {
            "research": 8,
            "analysis": 6,
            "tutorial": 3,
            "news": 2,
            "guide": 3,
            "general": 4,
        }

        target = expected.get(content_type, 4)

        # Score based on how close to target
        if citation_count >= target:
            return 100.0
        else:
            # Partial credit
            return (citation_count / target) * 100

    def _score_code_examples(self, content: str, content_type: str) -> float:
        """Score code example quality and quantity.

        Args:
            content: Article content
            content_type: Type of content

        Returns:
            Score 0-100
        """
        # Count code blocks
        code_blocks = content.count("```")
        code_block_count = code_blocks // 2  # Each block has opening and closing

        # Expected code blocks by content type
        expected = {
            "tutorial": 5,
            "guide": 4,
            "analysis": 2,
            "research": 1,
            "news": 1,
            "general": 2,
        }

        target = expected.get(content_type, 2)

        # Score based on target
        if code_block_count >= target:
            return 100.0
        elif target == 0:
            return 100.0  # No code expected
        else:
            return (code_block_count / target) * 100

    def _score_length(self, content: str, content_type: str) -> float:
        """Score article length appropriateness.

        Args:
            content: Article content
            content_type: Type of content

        Returns:
            Score 0-100
        """
        word_count = len(content.split())

        # Expected word counts by content type
        ranges = {
            "tutorial": (1000, 1400),
            "news": (800, 1200),
            "analysis": (1400, 1600),
            "research": (1400, 1600),
            "guide": (1200, 1500),
            "general": (1200, 1600),
        }

        min_words, max_words = ranges.get(content_type, (1200, 1600))

        if min_words <= word_count <= max_words:
            return 100.0
        elif word_count < min_words:
            # Penalize being short
            return (word_count / min_words) * 100
        else:
            # Slight penalty for being long (less severe)
            excess = word_count - max_words
            penalty = min(30, (excess / max_words) * 50)
            return max(70.0, 100.0 - penalty)

    def _score_tone(self, content: str, content_type: str) -> float:
        """Score tone consistency with content type.

        Args:
            content: Article content
            content_type: Type of content

        Returns:
            Score 0-100
        """
        score = 100.0  # Start with perfect, deduct for issues

        content_lower = content.lower()

        # Check for inappropriate casual language in formal content
        if content_type in ["research", "analysis"]:
            casual_markers = ["lol", "omg", "btw", "imho", "gonna", "wanna"]
            casual_count = sum(
                1 for marker in casual_markers if marker in content_lower
            )
            if casual_count > 0:
                score -= casual_count * 10

        # Check for overly formal language in tutorials
        if content_type == "tutorial":
            # Should use second person
            has_second_person = any(
                word in content_lower
                for word in ["you will", "you can", "let's", "we'll"]
            )
            if not has_second_person:
                score -= 20

        # Check for appropriate technical depth indicators
        has_technical_terms = bool(re.search(r"\b[A-Z]{2,}\b", content))  # Acronyms
        if (
            content_type in ["research", "analysis", "guide"]
            and not has_technical_terms
        ):
            score -= 10

        return max(0.0, score)

    def _generate_suggestions(
        self,
        dimension_scores: dict[str, float],
        article: GeneratedArticle,
        content: str,
    ) -> list[str]:
        """Generate actionable improvement suggestions.

        Args:
            dimension_scores: Scores for each dimension
            article: Article metadata
            content: Article content

        Returns:
            List of specific improvement suggestions
        """
        suggestions = []

        # Readability suggestions
        if dimension_scores["readability"] < 70:
            suggestions.append(
                f"Readability needs improvement for {article.difficulty_level or 'target'} level. "
                "Consider adjusting sentence complexity and vocabulary."
            )

        # Structure suggestions
        if dimension_scores["structure"] < 70:
            if "##" not in content:
                suggestions.append(
                    "Add clear section headings (## and ###) for better structure."
                )
            if "key takeaway" not in content.lower():
                suggestions.append(
                    'Include a "Key Takeaways" section after the introduction.'
                )

        # Citation suggestions
        if dimension_scores["citations"] < 70:
            suggestions.append(
                f"Add more citations for {article.content_type or 'this content type'}. "
                "Use format: Author et al. (Year) or Author (Year)."
            )

        # Code suggestions
        if dimension_scores["code_examples"] < 70:
            suggestions.append(
                f"Add more code examples for {article.content_type or 'this content type'}. "
                "Use ``` code blocks with language identifiers."
            )

        # Length suggestions
        if dimension_scores["length"] < 70:
            word_count = len(content.split())
            suggestions.append(
                f"Article is {word_count} words. Adjust length to meet content type guidelines."
            )

        # Tone suggestions
        if dimension_scores["tone"] < 70:
            suggestions.append(
                f"Adjust tone to better match {article.content_type or 'content type'} expectations."
            )

        if not suggestions:
            suggestions.append("Article quality is excellent across all dimensions!")

        return suggestions
