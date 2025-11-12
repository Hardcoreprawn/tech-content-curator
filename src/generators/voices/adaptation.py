"""Voice adaptation system for continuous improvement.

This module tracks voice performance metrics and suggests improvements
to voice prompts based on quality scores and review feedback.

It learns which voices work best for different content types and
can suggest prompt refinements when voices consistently underperform.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from ...config import get_project_root
from ...utils.logging import get_logger

if TYPE_CHECKING:
    from ..content.article_reviewer import ArticleReview

logger = get_logger(__name__)


@dataclass
class VoicePerformanceMetrics:
    """Performance metrics for a single voice."""

    voice_id: str
    """Voice identifier"""

    total_uses: int = 0
    """Total number of articles generated"""

    avg_quality_score: float = 0.0
    """Average quality score across all articles"""

    avg_review_score: float = 0.0
    """Average review score (0-10) when reviews enabled"""

    avg_voice_consistency: float = 0.0
    """Average voice consistency score (0-10)"""

    content_type_scores: dict[str, float] | None = None
    """Average scores by content type"""

    recent_scores: list[float] | None = None
    """Last 10 quality scores for trend analysis"""

    improvement_suggestions: list[str] | None = None
    """Accumulated suggestions from reviews"""

    last_updated: str = ""
    """ISO timestamp of last update"""

    def __post_init__(self):
        """Initialize mutable default values."""
        if self.content_type_scores is None:
            self.content_type_scores = {}
        if self.recent_scores is None:
            self.recent_scores = []
        if self.improvement_suggestions is None:
            self.improvement_suggestions = []
        if not self.last_updated:
            self.last_updated = datetime.now().isoformat()


@dataclass
class VoiceAdaptationSuggestion:
    """Suggested improvement to a voice prompt."""

    voice_id: str
    """Voice to improve"""

    issue: str
    """What issue was detected"""

    suggestion: str
    """Specific improvement to make"""

    priority: str
    """Priority: 'high', 'medium', 'low'"""

    evidence: list[str]
    """Examples/data supporting this suggestion"""


class VoiceAdapter:
    """Tracks voice performance and suggests improvements."""

    def __init__(self, data_dir: Path | None = None):
        """Initialize voice adapter.

        Args:
            data_dir: Directory for metrics storage (defaults to project data/)
        """
        self.data_dir = data_dir or (get_project_root() / "data")
        self.metrics_file = self.data_dir / "voice_metrics.json"
        self.suggestions_file = self.data_dir / "voice_suggestions.json"

        # Load existing metrics
        self.metrics: dict[str, VoicePerformanceMetrics] = self._load_metrics()
        logger.debug(f"Loaded metrics for {len(self.metrics)} voices")

    def _load_metrics(self) -> dict[str, VoicePerformanceMetrics]:
        """Load voice metrics from disk."""
        if not self.metrics_file.exists():
            return {}

        try:
            with open(self.metrics_file) as f:
                data = json.load(f)

            metrics = {}
            for voice_id, voice_data in data.items():
                metrics[voice_id] = VoicePerformanceMetrics(**voice_data)

            return metrics

        except Exception as e:
            logger.exception(f"Failed to load voice metrics: {e}")
            return {}

    def _save_metrics(self):
        """Save voice metrics to disk."""
        try:
            self.data_dir.mkdir(parents=True, exist_ok=True)

            data = {
                voice_id: asdict(metrics) for voice_id, metrics in self.metrics.items()
            }

            with open(self.metrics_file, "w") as f:
                json.dump(data, f, indent=2)

            logger.debug(f"Saved metrics for {len(self.metrics)} voices")

        except Exception as e:
            logger.exception(f"Failed to save voice metrics: {e}")

    def record_article(
        self,
        voice_id: str,
        content_type: str,
        quality_score: float,
        review: ArticleReview | None = None,
    ):
        """Record metrics for a generated article.

        Args:
            voice_id: Voice used
            content_type: Type of content generated
            quality_score: Quality score (0-100)
            review: Optional review results
        """
        if voice_id not in self.metrics:
            self.metrics[voice_id] = VoicePerformanceMetrics(voice_id=voice_id)

        metrics = self.metrics[voice_id]

        # Ensure mutable fields are initialized (should be from __post_init__)
        if metrics.content_type_scores is None:
            metrics.content_type_scores = {}
        if metrics.recent_scores is None:
            metrics.recent_scores = []
        if metrics.improvement_suggestions is None:
            metrics.improvement_suggestions = []

        # Update counts
        metrics.total_uses += 1

        # Update average quality score (0-100 scale)
        metrics.avg_quality_score = (
            metrics.avg_quality_score * (metrics.total_uses - 1) + quality_score
        ) / metrics.total_uses

        # Update content type scores
        if content_type not in metrics.content_type_scores:
            metrics.content_type_scores[content_type] = quality_score
        else:
            # Running average for this content type
            count = sum(
                1
                for ct in metrics.content_type_scores.keys()
                if ct == content_type  # Count articles of this type
            )
            old_avg = metrics.content_type_scores[content_type]
            metrics.content_type_scores[content_type] = (
                old_avg * count + quality_score
            ) / (count + 1)

        # Update recent scores (keep last 10)
        metrics.recent_scores.append(quality_score)
        if len(metrics.recent_scores) > 10:
            metrics.recent_scores.pop(0)

        # Update review metrics if available
        if review:
            metrics.avg_review_score = (
                metrics.avg_review_score * (metrics.total_uses - 1)
                + review.overall_score * 10  # Convert 0-10 to 0-100
            ) / metrics.total_uses

            metrics.avg_voice_consistency = (
                metrics.avg_voice_consistency * (metrics.total_uses - 1)
                + review.voice_consistency * 10
            ) / metrics.total_uses

            # Collect improvement suggestions
            for feedback in review.actionable_feedback:
                if feedback not in metrics.improvement_suggestions:
                    metrics.improvement_suggestions.append(feedback)
                    # Keep only last 20 suggestions
                    if len(metrics.improvement_suggestions) > 20:
                        metrics.improvement_suggestions.pop(0)

        metrics.last_updated = datetime.now().isoformat()

        logger.info(
            f"Recorded article for {voice_id}: quality={quality_score:.1f}, "
            f"total_uses={metrics.total_uses}, avg={metrics.avg_quality_score:.1f}"
        )

        # Save after each update
        self._save_metrics()

    def get_metrics(self, voice_id: str) -> VoicePerformanceMetrics | None:
        """Get metrics for a specific voice.

        Args:
            voice_id: Voice identifier

        Returns:
            Metrics object or None if no data
        """
        return self.metrics.get(voice_id)

    def get_all_metrics(self) -> dict[str, VoicePerformanceMetrics]:
        """Get metrics for all voices."""
        return self.metrics.copy()

    def analyze_voice_performance(
        self, voice_id: str
    ) -> list[VoiceAdaptationSuggestion]:
        """Analyze voice performance and suggest improvements.

        Args:
            voice_id: Voice to analyze

        Returns:
            List of suggestions for improvement
        """
        metrics = self.metrics.get(voice_id)
        if not metrics or metrics.total_uses < 5:
            # Need at least 5 articles to make suggestions
            return []

        # Ensure mutable fields are initialized
        if metrics.recent_scores is None:
            metrics.recent_scores = []
        if metrics.content_type_scores is None:
            metrics.content_type_scores = {}
        if metrics.improvement_suggestions is None:
            metrics.improvement_suggestions = []

        suggestions = []

        # Check 1: Low overall quality
        if metrics.avg_quality_score < 70:
            suggestions.append(
                VoiceAdaptationSuggestion(
                    voice_id=voice_id,
                    issue="Low average quality score",
                    suggestion=(
                        f"Voice '{voice_id}' averages {metrics.avg_quality_score:.1f}/100. "
                        "Consider refining style guidance to emphasize clarity and structure."
                    ),
                    priority="high",
                    evidence=[
                        f"Average score: {metrics.avg_quality_score:.1f}",
                        f"Sample size: {metrics.total_uses} articles",
                    ],
                )
            )

        # Check 2: Low voice consistency
        if metrics.avg_voice_consistency < 7.0 and metrics.avg_voice_consistency > 0:
            suggestions.append(
                VoiceAdaptationSuggestion(
                    voice_id=voice_id,
                    issue="Voice consistency issues",
                    suggestion=(
                        f"Articles often don't match expected voice (avg {metrics.avg_voice_consistency:.1f}/10). "
                        "Review and clarify voice-specific style guidance and examples."
                    ),
                    priority="high",
                    evidence=[
                        f"Voice consistency: {metrics.avg_voice_consistency:.1f}/10",
                        f"Based on {metrics.total_uses} reviews",
                    ],
                )
            )

        # Check 3: Declining trend
        if len(metrics.recent_scores) >= 5:
            early_avg = sum(metrics.recent_scores[:3]) / 3
            recent_avg = sum(metrics.recent_scores[-3:]) / 3

            if recent_avg < early_avg - 5:  # Dropped by 5+ points
                suggestions.append(
                    VoiceAdaptationSuggestion(
                        voice_id=voice_id,
                        issue="Quality declining over time",
                        suggestion=(
                            f"Recent articles scoring lower ({recent_avg:.1f}) than earlier ones ({early_avg:.1f}). "
                            "Voice may need refreshing or prompt may be drifting."
                        ),
                        priority="medium",
                        evidence=[
                            f"Early articles: {early_avg:.1f}",
                            f"Recent articles: {recent_avg:.1f}",
                            f"Trend: -{(early_avg - recent_avg):.1f} points",
                        ],
                    )
                )

        # Check 4: Poor fit for specific content types
        for content_type, score in metrics.content_type_scores.items():
            if score < 65:
                suggestions.append(
                    VoiceAdaptationSuggestion(
                        voice_id=voice_id,
                        issue=f"Poor fit for {content_type} content",
                        suggestion=(
                            f"Voice struggles with {content_type} articles (avg {score:.1f}). "
                            f"Consider adding content-type specific guidance or avoiding this pairing."
                        ),
                        priority="medium",
                        evidence=[
                            f"{content_type} average: {score:.1f}",
                            f"Overall average: {metrics.avg_quality_score:.1f}",
                        ],
                    )
                )

        # Check 5: Recurring suggestions from reviews
        if metrics.improvement_suggestions:
            # Find most common suggestions (simplified)
            from collections import Counter

            # Get first word/concept from each suggestion
            concepts = [s.split()[0].lower() for s in metrics.improvement_suggestions]
            common = Counter(concepts).most_common(3)

            if common and common[0][1] >= 3:  # Appears 3+ times
                suggestions.append(
                    VoiceAdaptationSuggestion(
                        voice_id=voice_id,
                        issue="Recurring feedback patterns",
                        suggestion=(
                            f"Reviews frequently mention improvements needed around: "
                            f"{', '.join(c[0] for c in common)}. "
                            f"Consider addressing these in voice guidance."
                        ),
                        priority="medium",
                        evidence=[
                            f"'{concept}' mentioned {count} times"
                            for concept, count in common
                        ],
                    )
                )

        logger.info(f"Generated {len(suggestions)} suggestions for {voice_id}")
        return suggestions

    def get_best_voice_for_content_type(
        self, content_type: str, min_uses: int = 3
    ) -> str | None:
        """Get the best-performing voice for a content type.

        Args:
            content_type: Content type to find best voice for
            min_uses: Minimum number of articles to consider

        Returns:
            Voice ID of best performer, or None if insufficient data
        """
        candidates = []

        for voice_id, metrics in self.metrics.items():
            if metrics.total_uses < min_uses:
                continue

            if metrics.content_type_scores is None:
                continue

            score = metrics.content_type_scores.get(content_type)
            if score:
                candidates.append((voice_id, score))

        if not candidates:
            return None

        # Sort by score (descending)
        candidates.sort(key=lambda x: x[1], reverse=True)

        best_voice = candidates[0][0]
        logger.info(
            f"Best voice for {content_type}: {best_voice} (score: {candidates[0][1]:.1f})"
        )

        return best_voice

    def generate_report(self) -> str:
        """Generate a human-readable performance report.

        Returns:
            Formatted report text
        """
        if not self.metrics:
            return "No voice performance data available yet."

        lines = [
            "# Voice Performance Report",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "",
            "## Overall Performance",
            "",
        ]

        # Sort voices by average quality score
        sorted_voices = sorted(
            self.metrics.items(), key=lambda x: x[1].avg_quality_score, reverse=True
        )

        for voice_id, metrics in sorted_voices:
            lines.append(f"### {voice_id.title()}")
            lines.append(f"- Articles Generated: {metrics.total_uses}")
            lines.append(f"- Average Quality: {metrics.avg_quality_score:.1f}/100")

            if metrics.avg_review_score > 0:
                lines.append(f"- Review Score: {metrics.avg_review_score:.1f}/100")
                lines.append(
                    f"- Voice Consistency: {metrics.avg_voice_consistency:.1f}/100"
                )

            if metrics.content_type_scores:
                lines.append("- Best Content Types:")
                sorted_types = sorted(
                    metrics.content_type_scores.items(),
                    key=lambda x: x[1],
                    reverse=True,
                )
                for ct, score in sorted_types[:3]:
                    lines.append(f"  - {ct}: {score:.1f}")

            # Add suggestions
            suggestions = self.analyze_voice_performance(voice_id)
            if suggestions:
                high_priority = [s for s in suggestions if s.priority == "high"]
                if high_priority:
                    lines.append("- ⚠️ High Priority Issues:")
                    for s in high_priority:
                        lines.append(f"  - {s.issue}")

            lines.append("")

        return "\n".join(lines)
