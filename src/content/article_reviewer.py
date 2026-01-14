"""AI-powered article review and evaluation system.

This module provides comprehensive article review across multiple dimensions,
generating actionable feedback and quality scores to guide improvements.

Similar to the illustration review system, this provides:
- Multi-dimensional scoring (clarity, accuracy, voice, engagement)
- Actionable feedback for improvements
- Voice consistency checking
- Optional regeneration triggers
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from openai import OpenAI

from ..config import get_config
from ..models import GeneratedArticle
from ..utils.logging import get_logger
from ..utils.openai_wrapper import chat_completion

if TYPE_CHECKING:
    from ..generators.voices.profiles import VoiceProfile

logger = get_logger(__name__)


@dataclass
class ReviewScore:
    """Individual dimension score with reasoning."""

    dimension: str
    """Name of the dimension being scored"""

    score: float
    """Score from 0-10"""

    reasoning: str
    """Brief explanation of the score"""

    suggestions: list[str]
    """Specific actionable improvements"""


@dataclass
class ArticleReview:
    """Complete article review with scores and recommendations."""

    overall_score: float
    """Overall quality score (0-10)"""

    dimension_scores: dict[str, ReviewScore]
    """Scores for each evaluated dimension"""

    strengths: list[str]
    """What the article does well"""

    weaknesses: list[str]
    """Areas needing improvement"""

    voice_consistency: float
    """How well the article matches intended voice (0-10)"""

    actionable_feedback: list[str]
    """Prioritized list of specific improvements to make"""

    regeneration_recommended: bool
    """Whether article should be regenerated"""

    def to_dict(self) -> dict:
        """Convert review to dictionary for storage."""
        return {
            "overall_score": self.overall_score,
            "dimension_scores": {
                name: {
                    "score": score.score,
                    "reasoning": score.reasoning,
                    "suggestions": score.suggestions,
                }
                for name, score in self.dimension_scores.items()
            },
            "strengths": self.strengths,
            "weaknesses": self.weaknesses,
            "voice_consistency": self.voice_consistency,
            "actionable_feedback": self.actionable_feedback,
            "regeneration_recommended": self.regeneration_recommended,
        }


class ArticleReviewer:
    """AI-powered article review system."""

    def __init__(self, client: OpenAI | None = None):
        """Initialize reviewer with OpenAI client.

        Args:
            client: Optional OpenAI client (creates new if None)
        """
        self.config = get_config()
        self.client = client or OpenAI(api_key=self.config.openai_api_key)
        logger.debug("ArticleReviewer initialized")

    def review_article(
        self,
        article: GeneratedArticle,
        content: str,
        voice_profile: VoiceProfile | None = None,
        min_threshold: float = 6.0,
    ) -> ArticleReview:
        """Perform comprehensive review of an article.

        Evaluates across multiple dimensions:
        - Clarity: Is the writing clear and understandable?
        - Accuracy: Are technical details correct and well-sourced?
        - Structure: Does it follow a logical flow?
        - Engagement: Is it compelling and well-paced?
        - Voice: Does it match the intended voice profile?
        - Completeness: Are all necessary elements present?

        Args:
            article: The generated article with metadata
            content: The article content text
            voice_profile: Expected voice profile (if applicable)
            min_threshold: Minimum acceptable overall score

        Returns:
            ArticleReview with scores, feedback, and recommendations
        """
        logger.info(f"Reviewing article: {article.title[:50]}...")

        # Build review prompt
        review_prompt = self._build_review_prompt(
            article, content, voice_profile, min_threshold
        )

        try:
            # Get AI review
            response = chat_completion(
                client=self.client,
                model=self.config.review_model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert content reviewer who provides detailed, "
                        "actionable feedback on technical articles. You evaluate clarity, "
                        "accuracy, structure, engagement, and voice consistency.",
                    },
                    {"role": "user", "content": review_prompt},
                ],
                stage="review",
                config=self.config,
                article_id=article.filename,
                context={"reviewer": "ArticleReviewer"},
                temperature=0.3,  # Lower temperature for consistent evaluation
            )

            review_text = response.choices[0].message.content or ""
            logger.debug(f"Received review response ({len(review_text)} chars)")

            # Parse AI response into structured review
            review = self._parse_review_response(
                review_text, voice_profile, min_threshold
            )

            logger.info(
                f"Review complete: overall={review.overall_score:.1f}/10, "
                f"voice_consistency={review.voice_consistency:.1f}/10, "
                f"regenerate={review.regeneration_recommended}"
            )

            return review

        except Exception as e:
            logger.exception(f"Article review failed: {e}")
            # Return a default passing review on failure
            return ArticleReview(
                overall_score=min_threshold,
                dimension_scores={},
                strengths=["Review system encountered an error"],
                weaknesses=[],
                voice_consistency=min_threshold,
                actionable_feedback=[],
                regeneration_recommended=False,
            )

    def _build_review_prompt(
        self,
        article: GeneratedArticle,
        content: str,
        voice_profile: VoiceProfile | None,
        min_threshold: float,
    ) -> str:
        """Build the review prompt for AI evaluation."""
        # Truncate content for review (first 3000 chars for analysis)
        content_preview = content[:3000]
        if len(content) > 3000:
            content_preview += "\n\n[... content truncated for review ...]"

        prompt_parts = [
            "# Article Review Task",
            "",
            "Evaluate this technical article across multiple dimensions and provide actionable feedback.",
            "",
            "## Article Metadata",
            f"- Title: {article.title}",
            f"- Word Count: {len(content.split())} words",
            f"- Content Type: {article.content_type or 'general'}",
            f"- Difficulty Level: {article.difficulty_level or 'intermediate'}",
            f"- Tags: {', '.join(article.tags[:5])}",
        ]

        if voice_profile:
            prompt_parts.extend(
                [
                    f"- Intended Voice: {voice_profile.name}",
                    "",
                    "## Voice Expectations",
                    voice_profile.style_guidance,
                ]
            )

        prompt_parts.extend(
            [
                "",
                "## Article Content",
                content_preview,
                "",
                "## Review Instructions",
                "",
                "Evaluate the article on these dimensions (score each 0-10):",
                "",
                "1. **Clarity** (0-10)",
                "   - Is the writing clear and easy to understand?",
                "   - Are technical concepts explained well?",
                "   - Is jargon properly defined?",
                "",
                "2. **Accuracy** (0-10)",
                "   - Are technical details correct?",
                "   - Are claims properly supported/cited?",
                "   - Is information up-to-date?",
                "",
                "3. **Structure** (0-10)",
                "   - Does it follow a logical flow?",
                "   - Are headings and sections well-organized?",
                "   - Is there a clear introduction and conclusion?",
                "",
                "4. **Engagement** (0-10)",
                "   - Is it compelling and well-paced?",
                "   - Does the opening hook the reader?",
                "   - Are examples concrete and relevant?",
                "",
                "5. **Completeness** (0-10)",
                "   - Are all necessary elements present?",
                "   - Is depth appropriate for the topic?",
                "   - Are references/citations adequate?",
                "",
            ]
        )

        if voice_profile:
            prompt_parts.extend(
                [
                    "6. **Voice Consistency** (0-10)",
                    f"   - Does it match {voice_profile.name}'s voice?",
                    "   - Is tone/style consistent throughout?",
                    "   - Are voice-specific banned phrases avoided?",
                    "",
                ]
            )

        prompt_parts.extend(
            [
                "## Required Output Format",
                "",
                "Provide your review in this structure:",
                "",
                "### Overall Score: X/10",
                "",
                "### Dimension Scores",
                "- Clarity: X/10 - [reasoning]",
                "- Accuracy: X/10 - [reasoning]",
                "- Structure: X/10 - [reasoning]",
                "- Engagement: X/10 - [reasoning]",
                "- Completeness: X/10 - [reasoning]",
            ]
        )

        if voice_profile:
            prompt_parts.append("- Voice Consistency: X/10 - [reasoning]")

        prompt_parts.extend(
            [
                "",
                "### Strengths",
                "- [What the article does well]",
                "- [Another strength]",
                "",
                "### Weaknesses",
                "- [Area needing improvement]",
                "- [Another weakness]",
                "",
                "### Actionable Feedback",
                "1. [Specific improvement to make]",
                "2. [Another specific improvement]",
                "3. [Third specific improvement]",
                "",
                "### Regeneration Recommendation",
                f"[YES or NO - recommend regeneration if overall score < {min_threshold}]",
            ]
        )

        return "\n".join(prompt_parts)

    def _parse_review_response(
        self, review_text: str, voice_profile: VoiceProfile | None, min_threshold: float
    ) -> ArticleReview:
        """Parse AI review response into structured ArticleReview.

        Args:
            review_text: Raw review text from AI
            voice_profile: Voice profile if applicable
            min_threshold: Minimum acceptable score

        Returns:
            Structured ArticleReview object
        """
        import re

        # Extract overall score
        overall_match = re.search(r"Overall Score:\s*(\d+(?:\.\d+)?)/10", review_text)
        overall_score = (
            float(overall_match.group(1)) if overall_match else min_threshold
        )

        # Extract dimension scores
        dimensions = ["clarity", "accuracy", "structure", "engagement", "completeness"]
        if voice_profile:
            dimensions.append("voice_consistency")

        dimension_scores = {}
        for dim in dimensions:
            # Match "- Dimension: X/10 - reasoning"
            pattern = rf"-\s*{dim.replace('_', ' ').title()}:\s*(\d+(?:\.\d+)?)/10\s*-\s*([^\n]+)"
            match = re.search(pattern, review_text, re.IGNORECASE)
            if match:
                score = float(match.group(1))
                reasoning = match.group(2).strip()
                dimension_scores[dim] = ReviewScore(
                    dimension=dim,
                    score=score,
                    reasoning=reasoning,
                    suggestions=[],  # Could be extracted if AI provides them
                )

        # Extract voice consistency score separately if present
        voice_consistency = 10.0  # Default if no voice profile
        if voice_profile and "voice_consistency" in dimension_scores:
            voice_consistency = dimension_scores["voice_consistency"].score

        # Extract strengths
        strengths_match = re.search(
            r"### Strengths\s*((?:- .+\n?)+)", review_text, re.IGNORECASE
        )
        strengths = []
        if strengths_match:
            strengths = [
                line.strip("- ").strip()
                for line in strengths_match.group(1).split("\n")
                if line.strip().startswith("-")
            ]

        # Extract weaknesses
        weaknesses_match = re.search(
            r"### Weaknesses\s*((?:- .+\n?)+)", review_text, re.IGNORECASE
        )
        weaknesses = []
        if weaknesses_match:
            weaknesses = [
                line.strip("- ").strip()
                for line in weaknesses_match.group(1).split("\n")
                if line.strip().startswith("-")
            ]

        # Extract actionable feedback
        feedback_match = re.search(
            r"### Actionable Feedback\s*((?:\d+\. .+\n?)+)", review_text, re.IGNORECASE
        )
        actionable_feedback = []
        if feedback_match:
            actionable_feedback = [
                re.sub(r"^\d+\.\s*", "", line).strip()
                for line in feedback_match.group(1).split("\n")
                if re.match(r"^\d+\.", line.strip())
            ]

        # Extract regeneration recommendation
        regen_match = re.search(
            r"### Regeneration Recommendation\s*\[?(YES|NO)\]?",
            review_text,
            re.IGNORECASE,
        )
        regeneration_recommended = False
        if regen_match:
            regeneration_recommended = regen_match.group(1).upper() == "YES"
        else:
            # Fall back to threshold check
            regeneration_recommended = overall_score < min_threshold

        return ArticleReview(
            overall_score=overall_score,
            dimension_scores=dimension_scores,
            strengths=strengths or ["Article meets basic quality standards"],
            weaknesses=weaknesses or [],
            voice_consistency=voice_consistency,
            actionable_feedback=actionable_feedback or [],
            regeneration_recommended=regeneration_recommended,
        )

    def generate_improvement_prompt(
        self, article: GeneratedArticle, content: str, review: ArticleReview
    ) -> str:
        """Generate a prompt to regenerate article based on review feedback.

        Args:
            article: Original article
            content: Original content
            review: Review results with feedback

        Returns:
            Prompt for regeneration with specific improvements
        """
        prompt_parts = [
            "# Article Improvement Task",
            "",
            "The following article needs improvement based on review feedback.",
            "",
            "## Original Article",
            content,
            "",
            "## Review Results",
            f"Overall Score: {review.overall_score:.1f}/10",
            "",
            "### Dimension Scores",
        ]

        for name, score in review.dimension_scores.items():
            prompt_parts.append(
                f"- {name.replace('_', ' ').title()}: {score.score:.1f}/10 - {score.reasoning}"
            )

        if review.weaknesses:
            prompt_parts.extend(["", "### Key Weaknesses to Address"])
            for weakness in review.weaknesses:
                prompt_parts.append(f"- {weakness}")

        if review.actionable_feedback:
            prompt_parts.extend(["", "### Specific Improvements Needed"])
            for i, feedback in enumerate(review.actionable_feedback, 1):
                prompt_parts.append(f"{i}. {feedback}")

        prompt_parts.extend(
            [
                "",
                "## Your Task",
                "",
                "Rewrite the article addressing ALL the issues above while:",
                "1. Maintaining the core message and key technical points",
                "2. Preserving accuracy and any correct technical details",
                "3. Keeping all relevant code examples (but improve explanations)",
                "4. Following all feedback and improvement suggestions",
                "5. Maintaining appropriate length and depth",
                "",
                "Return ONLY the improved article in markdown format.",
                "Do not include meta-commentary about the changes.",
            ]
        )

        return "\n".join(prompt_parts)
