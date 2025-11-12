"""Quality tracking system for monitoring article quality over time.

This module stores and analyzes quality metrics to help evaluate model
performance and identify quality trends across different configurations.
"""

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from ..models import GeneratedArticle
from ..utils.logging import get_logger
from .quality_scorer import QualityScore

logger = get_logger(__name__)


@dataclass
class QualityRecord:
    """Record of quality metrics for a single article."""

    # Article identification
    article_id: str  # Usually the slug
    title: str
    timestamp: str  # ISO format

    # Model configuration
    content_model: str
    title_model: str
    review_model: str | None
    enrichment_model: str

    # Quality metrics
    overall_score: float
    dimension_scores: dict[str, float]
    passed_threshold: bool

    # Article metadata
    content_type: str | None
    difficulty_level: str | None
    voice: str | None
    word_count: int

    # Readability metrics
    flesch_reading_ease: float | None
    grade_level: float | None

    # Additional context
    topics: list[str]
    source_platform: str


class QualityTracker:
    """Track and analyze article quality metrics over time."""

    def __init__(self, storage_path: str | Path = "data/quality_history.json"):
        """Initialize quality tracker.

        Args:
            storage_path: Path to JSON file for storing quality history
        """
        self.storage_path = Path(storage_path)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

        # Load existing history
        self.history: list[dict[str, Any]] = self._load_history()

    def _load_history(self) -> list[dict[str, Any]]:
        """Load quality history from storage.

        Returns:
            List of quality records
        """
        if not self.storage_path.exists():
            logger.info(f"No existing quality history at {self.storage_path}")
            return []

        try:
            with open(self.storage_path, encoding="utf-8") as f:
                data = json.load(f)
                logger.info(
                    f"Loaded {len(data.get('records', []))} quality records from {self.storage_path}"
                )
                return data.get("records", [])
        except Exception as e:
            logger.error(f"Failed to load quality history: {e}")
            return []

    def _save_history(self) -> None:
        """Save quality history to storage."""
        try:
            data = {
                "version": "1.0",
                "last_updated": datetime.now().isoformat(),
                "total_records": len(self.history),
                "records": self.history,
            }

            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            logger.debug(
                f"Saved {len(self.history)} quality records to {self.storage_path}"
            )
        except Exception as e:
            logger.error(f"Failed to save quality history: {e}")

    def record_quality(
        self,
        article: GeneratedArticle,
        quality_score: QualityScore,
        content: str,
        models: dict[str, str],
    ) -> None:
        """Record quality metrics for an article.

        Args:
            article: The generated article
            quality_score: Quality score from QualityScorer
            content: Article content text
            models: Dict of model names used (content_model, title_model, etc.)
        """
        record = QualityRecord(
            article_id=article.filename or article.title[:50],
            title=article.title,
            timestamp=datetime.now().isoformat(),
            content_model=models.get("content_model", "unknown"),
            title_model=models.get("title_model", "unknown"),
            review_model=models.get("review_model"),
            enrichment_model=models.get("enrichment_model", "unknown"),
            overall_score=quality_score.overall_score,
            dimension_scores=quality_score.dimension_scores,
            passed_threshold=quality_score.passed_threshold,
            content_type=article.content_type,
            difficulty_level=article.difficulty_level,
            voice=models.get(
                "voice", "unknown"
            ),  # Voice not in article model, pass via models
            word_count=len(content.split()),
            flesch_reading_ease=article.readability_score,
            grade_level=article.grade_level,
            topics=article.tags,  # Use tags field instead of topics
            source_platform=article.sources[0].original.source
            if article.sources
            else "unknown",
        )

        self.history.append(asdict(record))
        self._save_history()

        logger.info(
            f"Recorded quality metrics for '{article.title[:50]}': "
            f"score={quality_score.overall_score:.1f}, "
            f"model={models.get('content_model', 'unknown')}"
        )

    def get_statistics(
        self,
        model_filter: str | None = None,
        content_type_filter: str | None = None,
        min_records: int = 5,
    ) -> dict[str, Any]:
        """Get quality statistics across recorded articles.

        Args:
            model_filter: Filter by content_model (e.g., "gpt-5-mini")
            content_type_filter: Filter by content_type (e.g., "tutorial")
            min_records: Minimum records needed for statistics

        Returns:
            Dictionary of statistics including:
            - count: Number of articles
            - avg_overall_score: Average overall quality score
            - avg_dimension_scores: Average scores per dimension
            - pass_rate: Percentage passing threshold
            - avg_word_count: Average article length
            - models_used: Breakdown by model
        """
        # Filter records
        records = self.history
        if model_filter:
            records = [r for r in records if r.get("content_model") == model_filter]
        if content_type_filter:
            records = [
                r for r in records if r.get("content_type") == content_type_filter
            ]

        if len(records) < min_records:
            logger.warning(
                f"Only {len(records)} records found, need {min_records} for reliable statistics"
            )
            return {
                "count": len(records),
                "insufficient_data": True,
                "message": f"Need at least {min_records} records for statistics",
            }

        # Calculate statistics
        overall_scores = [r["overall_score"] for r in records]
        passed = [r for r in records if r["passed_threshold"]]
        word_counts = [r["word_count"] for r in records]

        # Average dimension scores
        dimension_names = records[0]["dimension_scores"].keys()
        avg_dimensions = {}
        for dim in dimension_names:
            scores = [r["dimension_scores"][dim] for r in records]
            avg_dimensions[dim] = sum(scores) / len(scores)

        # Model breakdown
        models_used = {}
        for record in records:
            model = record["content_model"]
            if model not in models_used:
                models_used[model] = {"count": 0, "avg_score": 0.0, "scores": []}
            models_used[model]["count"] += 1
            models_used[model]["scores"].append(record["overall_score"])

        for model in models_used:
            scores = models_used[model]["scores"]
            models_used[model]["avg_score"] = sum(scores) / len(scores)
            del models_used[model]["scores"]  # Clean up temporary data

        return {
            "count": len(records),
            "avg_overall_score": sum(overall_scores) / len(overall_scores),
            "avg_dimension_scores": avg_dimensions,
            "pass_rate": len(passed) / len(records) * 100,
            "avg_word_count": sum(word_counts) / len(word_counts),
            "models_used": models_used,
            "score_distribution": {
                "min": min(overall_scores),
                "max": max(overall_scores),
                "median": sorted(overall_scores)[len(overall_scores) // 2],
            },
        }

    def compare_models(
        self, model_a: str, model_b: str, min_records: int = 5
    ) -> dict[str, Any]:
        """Compare quality metrics between two models.

        Args:
            model_a: First model to compare
            model_b: Second model to compare
            min_records: Minimum records per model

        Returns:
            Dictionary with comparison statistics
        """
        stats_a = self.get_statistics(model_filter=model_a, min_records=min_records)
        stats_b = self.get_statistics(model_filter=model_b, min_records=min_records)

        if stats_a.get("insufficient_data") or stats_b.get("insufficient_data"):
            return {
                "insufficient_data": True,
                "message": f"Need at least {min_records} records per model",
                "model_a_count": stats_a.get("count", 0),
                "model_b_count": stats_b.get("count", 0),
            }

        # Calculate differences
        score_diff = stats_b["avg_overall_score"] - stats_a["avg_overall_score"]
        pass_rate_diff = stats_b["pass_rate"] - stats_a["pass_rate"]

        return {
            "model_a": model_a,
            "model_b": model_b,
            "model_a_stats": stats_a,
            "model_b_stats": stats_b,
            "differences": {
                "score_diff": score_diff,
                "score_diff_pct": (score_diff / stats_a["avg_overall_score"]) * 100,
                "pass_rate_diff": pass_rate_diff,
                "better_model": model_b if score_diff > 0 else model_a,
            },
        }

    def get_trend_analysis(
        self, window_size: int = 10, model_filter: str | None = None
    ) -> dict[str, Any]:
        """Analyze quality trends over time.

        Args:
            window_size: Number of recent articles to analyze
            model_filter: Filter by content_model

        Returns:
            Dictionary with trend analysis including moving averages
        """
        records = self.history
        if model_filter:
            records = [r for r in records if r.get("content_model") == model_filter]

        if len(records) < window_size:
            return {
                "insufficient_data": True,
                "message": f"Need at least {window_size} records for trend analysis",
                "count": len(records),
            }

        # Get recent records
        recent = records[-window_size:]
        older = records[:-window_size] if len(records) > window_size else []

        recent_avg = sum(r["overall_score"] for r in recent) / len(recent)
        older_avg = (
            sum(r["overall_score"] for r in older) / len(older) if older else recent_avg
        )

        return {
            "total_articles": len(records),
            "window_size": window_size,
            "recent_avg_score": recent_avg,
            "historical_avg_score": older_avg,
            "trend": "improving"
            if recent_avg > older_avg
            else "declining"
            if recent_avg < older_avg
            else "stable",
            "improvement": recent_avg - older_avg,
            "recent_pass_rate": sum(1 for r in recent if r["passed_threshold"])
            / len(recent)
            * 100,
        }

    def export_summary(self, output_path: str | Path | None = None) -> str:
        """Export a human-readable summary of quality metrics.

        Args:
            output_path: Optional path to save summary (defaults to console only)

        Returns:
            Formatted summary string
        """
        if not self.history:
            return "No quality data recorded yet."

        stats = self.get_statistics()

        summary = f"""
=== Quality Tracking Summary ===

Total Articles Tracked: {stats["count"]}
Average Quality Score: {stats["avg_overall_score"]:.1f}/100
Pass Rate: {stats["pass_rate"]:.1f}%
Average Word Count: {stats["avg_word_count"]:.0f} words

=== Dimension Scores ===
"""
        for dim, score in stats["avg_dimension_scores"].items():
            summary += f"  {dim.replace('_', ' ').title()}: {score:.1f}/100\n"

        summary += "\n=== Models Used ===\n"
        for model, data in stats["models_used"].items():
            summary += f"  {model}: {data['count']} articles, avg score {data['avg_score']:.1f}\n"

        summary += f"""
=== Score Distribution ===
  Min: {stats["score_distribution"]["min"]:.1f}
  Median: {stats["score_distribution"]["median"]:.1f}
  Max: {stats["score_distribution"]["max"]:.1f}
"""

        if output_path:
            output_path = Path(output_path)
            output_path.write_text(summary, encoding="utf-8")
            logger.info(f"Exported quality summary to {output_path}")

        return summary
