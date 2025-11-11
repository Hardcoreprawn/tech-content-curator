"""Adaptive scoring system that learns from AI feedback to improve heuristics.

This module implements a feedback loop where AI quality scores are used to
improve the heuristic scoring system over time. It identifies patterns where
the AI consistently scores content higher than heuristics, then adapts.
"""

import json
import statistics
from datetime import UTC, datetime
from threading import Lock

from rich.console import Console

from ..config import get_data_dir
from ..models import CollectedItem
from ..utils.logging import get_logger

logger = get_logger(__name__)
console = Console()

# Module-level cache for shared patterns (loaded once, shared immutably)
_SHARED_PATTERNS_CACHE: dict | None = None
_PATTERNS_LOCK = Lock()


class ScoringAdapter:
    """Learns from AI vs heuristic score differences to improve heuristic scoring."""

    def __init__(self, use_empty=False):
        """
        Initialize adapter.

        Args:
            use_empty: If True, create with empty feedback (for thread-local accumulation).
                      If False, load from disk (for main/merge instance).
        """
        self.feedback_file = get_data_dir() / "scoring_feedback.json"
        self.patterns_file = get_data_dir() / "scoring_patterns.json"
        self.use_empty = use_empty

        if use_empty:
            # Thread-local instance: empty feedback, shared patterns reference
            self.feedback_history = []
            self.learned_patterns = ScoringAdapter.get_shared_patterns().copy()
        else:
            # Main instance: load everything from disk
            self.load_feedback_data()

    @staticmethod
    def get_shared_patterns() -> dict:
        """Load patterns once, cache at module level (immutable during execution).

        This is critical for avoiding per-thread disk loads. Called once before
        thread pool starts, then shared reference passed to each thread.
        """
        global _SHARED_PATTERNS_CACHE

        if _SHARED_PATTERNS_CACHE is not None:
            return _SHARED_PATTERNS_CACHE

        with _PATTERNS_LOCK:
            # Double-check pattern
            if _SHARED_PATTERNS_CACHE is not None:
                return _SHARED_PATTERNS_CACHE

            patterns_file = get_data_dir() / "scoring_patterns.json"
            try:
                if patterns_file.exists():
                    with open(patterns_file) as f:
                        _SHARED_PATTERNS_CACHE = json.load(f)
                        logger.debug("Loaded shared patterns from disk")
                else:
                    _SHARED_PATTERNS_CACHE = {
                        "undervalued_keywords": [],
                        "engagement_thresholds": {},
                        "content_patterns": [],
                        "length_adjustments": {},
                    }
                    logger.debug("Initialized empty shared patterns")
            except Exception as e:
                logger.error(f"Failed to load shared patterns: {e}")
                _SHARED_PATTERNS_CACHE = {
                    "undervalued_keywords": [],
                    "engagement_thresholds": {},
                    "content_patterns": [],
                    "length_adjustments": {},
                }

            return _SHARED_PATTERNS_CACHE

    @staticmethod
    def clear_shared_patterns_cache():
        """Clear the shared patterns cache. Useful for testing."""
        global _SHARED_PATTERNS_CACHE
        _SHARED_PATTERNS_CACHE = None

    def load_feedback_data(self) -> None:
        """Load historical scoring feedback and learned patterns."""
        try:
            if self.feedback_file.exists():
                with open(self.feedback_file) as f:
                    self.feedback_history = json.load(f)
            else:
                self.feedback_history = []

            if self.patterns_file.exists():
                with open(self.patterns_file) as f:
                    self.learned_patterns = json.load(f)
            else:
                self.learned_patterns = {
                    "undervalued_keywords": [],
                    "engagement_thresholds": {},
                    "content_patterns": [],
                    "length_adjustments": {},
                }
        except Exception as e:
            console.print(
                f"[yellow]Warning: Could not load feedback data: {e}[/yellow]"
            )
            self.feedback_history = []
            self.learned_patterns = {
                "undervalued_keywords": [],
                "engagement_thresholds": {},
                "content_patterns": [],
                "length_adjustments": {},
            }

    def record_feedback(
        self,
        item: CollectedItem,
        heuristic_score: float,
        ai_score: float,
        heuristic_reasoning: str,
    ) -> None:
        """Record a feedback instance for learning."""
        feedback_entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "content_preview": item.content[:200],
            "content_length": len(item.content),
            "heuristic_score": heuristic_score,
            "ai_score": ai_score,
            "score_gap": ai_score - heuristic_score,
            "heuristic_reasoning": heuristic_reasoning,
            "metadata": item.metadata or {},
            "source": item.source.value
            if hasattr(item.source, "value")
            else str(item.source),
        }

        self.feedback_history.append(feedback_entry)

        # Keep only recent feedback (last 1000 entries)
        if len(self.feedback_history) > 1000:
            self.feedback_history = self.feedback_history[-1000:]

    def analyze_underperformance(self) -> dict:
        """Analyze cases where AI scored significantly higher than heuristics."""
        if len(self.feedback_history) < 10:
            return {"message": "Not enough feedback data yet"}

        # Find cases where AI scored ≥0.2 points higher than heuristics
        undervalued_cases = [
            entry
            for entry in self.feedback_history
            if entry["score_gap"] >= 0.2 and entry["ai_score"] >= 0.4
        ]

        if not undervalued_cases:
            return {"message": "No significant undervaluation patterns found"}

        analysis = {
            "total_undervalued": len(undervalued_cases),
            "avg_gap": statistics.mean(
                [case["score_gap"] for case in undervalued_cases]
            ),
            "patterns": self._extract_patterns(undervalued_cases),
        }

        return analysis

    def _extract_patterns(self, cases: list[dict]) -> dict:
        """Extract common patterns from undervalued cases."""
        patterns = {
            "keywords": {},
            "length_ranges": {},
            "engagement_levels": {},
            "content_features": {},
        }

        for case in cases:
            content = case["content_preview"].lower()

            # Track keywords that appear in undervalued content
            words = content.split()
            for word in words:
                if len(word) > 3 and word.isalpha():
                    patterns["keywords"][word] = patterns["keywords"].get(word, 0) + 1

            # Track length ranges
            length = case["content_length"]
            length_bucket = f"{(length // 100) * 100}-{((length // 100) + 1) * 100}"
            patterns["length_ranges"][length_bucket] = (
                patterns["length_ranges"].get(length_bucket, 0) + 1
            )

            # Track engagement levels
            metadata = case.get("metadata", {})
            engagement = (
                metadata.get("favourites_count", 0)
                + metadata.get("reblogs_count", 0) * 2
                + metadata.get("replies_count", 0) * 3
            )

            if engagement > 0:
                eng_bucket = f"{(engagement // 50) * 50}+"
                patterns["engagement_levels"][eng_bucket] = (
                    patterns["engagement_levels"].get(eng_bucket, 0) + 1
                )

            # Track content features
            if "http" in content:
                patterns["content_features"]["has_links"] = (
                    patterns["content_features"].get("has_links", 0) + 1
                )
            if any(char in content for char in "?!"):
                patterns["content_features"]["has_questions_exclamations"] = (
                    patterns["content_features"].get("has_questions_exclamations", 0)
                    + 1
                )

        # Sort by frequency
        for category in patterns:
            if isinstance(patterns[category], dict):
                patterns[category] = dict(
                    sorted(
                        patterns[category].items(), key=lambda x: x[1], reverse=True
                    )[:10]
                )

        return patterns

    def get_adaptive_adjustments(self, item: CollectedItem) -> tuple[float, list[str]]:
        """Get score adjustments based on learned patterns."""
        adjustments = 0.0
        reasons = []

        content = item.content.lower()

        # Check for undervalued keywords
        undervalued_keywords = self.learned_patterns.get("undervalued_keywords", [])
        for keyword in undervalued_keywords:
            if keyword in content:
                adjustments += 0.1
                reasons.append(f"contains undervalued keyword: {keyword}")

        # Check engagement patterns
        if hasattr(item, "metadata") and item.metadata:
            engagement = (
                item.metadata.get("favourites_count", 0)
                + item.metadata.get("reblogs_count", 0) * 2
                + item.metadata.get("replies_count", 0) * 3
            )

            learned_thresholds = self.learned_patterns.get("engagement_thresholds", {})
            for threshold, adjustment in learned_thresholds.items():
                if engagement >= int(threshold):
                    adjustments += adjustment
                    reasons.append(f"engagement above learned threshold: {threshold}")

        # Check content patterns
        content_patterns = self.learned_patterns.get("content_patterns", [])
        for pattern in content_patterns:
            if pattern.get("pattern") in content:
                adjustments += pattern.get("adjustment", 0)
                reasons.append(f"matches learned pattern: {pattern['pattern']}")

        return adjustments, reasons

    def update_learned_patterns(self) -> None:
        """Update learned patterns based on recent feedback."""
        analysis = self.analyze_underperformance()

        if "patterns" not in analysis:
            return

        patterns = analysis["patterns"]

        # Update undervalued keywords (words that appear frequently in undervalued content)
        keyword_counts = patterns.get("keywords", {})
        high_frequency_keywords = [
            word
            for word, count in keyword_counts.items()
            if count >= 3 and word not in ["the", "and", "for", "with", "this", "that"]
        ]
        self.learned_patterns["undervalued_keywords"] = high_frequency_keywords

        # Update engagement thresholds
        engagement_patterns = patterns.get("engagement_levels", {})
        for eng_level, count in engagement_patterns.items():
            if count >= 3:  # Appears in at least 3 undervalued cases
                threshold = int(eng_level.rstrip("+"))
                self.learned_patterns["engagement_thresholds"][str(threshold)] = 0.15

        self.save_patterns()

    def save_patterns(self) -> None:
        """Save learned patterns to disk."""
        try:
            with open(self.patterns_file, "w") as f:
                json.dump(self.learned_patterns, f, indent=2)
        except Exception as e:
            console.print(f"[yellow]Warning: Could not save patterns: {e}[/yellow]")

    def get_feedback_data(self) -> dict:
        """Export feedback for merging across threads.

        Returns:
            Dictionary with feedback history and learned patterns
        """
        return {
            "feedback_history": self.feedback_history[:],  # Copy
            "learned_patterns": {
                "undervalued_keywords": self.learned_patterns.get(
                    "undervalued_keywords", []
                )[:],
                "engagement_thresholds": self.learned_patterns.get(
                    "engagement_thresholds", {}
                ).copy(),
                "content_patterns": self.learned_patterns.get("content_patterns", [])[
                    :
                ],
                "length_adjustments": self.learned_patterns.get(
                    "length_adjustments", {}
                ).copy(),
            },
        }

    def merge_feedback(self, data: dict) -> None:
        """Merge feedback from thread-local adapter.

        Args:
            data: Dictionary from get_feedback_data() containing feedback to merge
        """
        # Merge feedback history
        self.feedback_history.extend(data.get("feedback_history", []))

        # Merge learned patterns
        patterns = data.get("learned_patterns", {})

        # Merge undervalued keywords (deduplicate)
        existing_keywords = set(self.learned_patterns.get("undervalued_keywords", []))
        new_keywords = patterns.get("undervalued_keywords", [])
        existing_keywords.update(new_keywords)
        self.learned_patterns["undervalued_keywords"] = list(existing_keywords)

        # Merge engagement thresholds (take max adjustment for each threshold)
        existing_thresholds = self.learned_patterns.get("engagement_thresholds", {})
        new_thresholds = patterns.get("engagement_thresholds", {})
        for threshold, adjustment in new_thresholds.items():
            if threshold in existing_thresholds:
                existing_thresholds[threshold] = max(
                    existing_thresholds[threshold], adjustment
                )
            else:
                existing_thresholds[threshold] = adjustment

        # Merge content patterns
        self.learned_patterns["content_patterns"].extend(
            patterns.get("content_patterns", [])
        )

        # Merge length adjustments
        existing_lengths = self.learned_patterns.get("length_adjustments", {})
        new_lengths = patterns.get("length_adjustments", {})
        for length, adjustment in new_lengths.items():
            if length in existing_lengths:
                existing_lengths[length] = max(existing_lengths[length], adjustment)
            else:
                existing_lengths[length] = adjustment

    def save_feedback(self) -> None:
        """Save feedback history to disk."""
        try:
            with open(self.feedback_file, "w") as f:
                json.dump(self.feedback_history, f, indent=2)
        except Exception as e:
            console.print(f"[yellow]Warning: Could not save feedback: {e}[/yellow]")

    def print_analysis_report(self) -> None:
        """Print a detailed analysis report."""
        console.print("\n[bold blue]Adaptive Scoring Analysis Report[/bold blue]")

        if len(self.feedback_history) < 10:
            console.print(
                "[yellow]Not enough data for meaningful analysis (need ≥10 entries)[/yellow]"
            )
            return

        # Basic stats
        total_entries = len(self.feedback_history)
        avg_heuristic = statistics.mean(
            [e["heuristic_score"] for e in self.feedback_history]
        )
        avg_ai = statistics.mean([e["ai_score"] for e in self.feedback_history])
        avg_gap = statistics.mean([e["score_gap"] for e in self.feedback_history])

        console.print(f"Total feedback entries: {total_entries}")
        console.print(f"Average heuristic score: {avg_heuristic:.3f}")
        console.print(f"Average AI score: {avg_ai:.3f}")
        console.print(f"Average score gap (AI - Heuristic): {avg_gap:.3f}")

        # Underperformance analysis
        analysis = self.analyze_underperformance()
        if "patterns" in analysis:
            console.print("\n[bold]Undervaluation Analysis:[/bold]")
            console.print(
                f"Cases where AI scored ≥0.2 higher: {analysis['total_undervalued']}"
            )
            console.print(f"Average gap in these cases: {analysis['avg_gap']:.3f}")

            patterns = analysis["patterns"]

            # Top keywords in undervalued content
            keywords = patterns.get("keywords", {})
            if keywords:
                console.print("\n[bold]Top keywords in undervalued content:[/bold]")
                for word, count in list(keywords.items())[:5]:
                    console.print(f"  {word}: {count} occurrences")

            # Length patterns
            length_ranges = patterns.get("length_ranges", {})
            if length_ranges:
                console.print("\n[bold]Length ranges in undervalued content:[/bold]")
                for range_str, count in list(length_ranges.items())[:3]:
                    console.print(f"  {range_str} chars: {count} cases")

        # Current learned patterns
        console.print("\n[bold]Currently Applied Adjustments:[/bold]")
        undervalued_kw = self.learned_patterns.get("undervalued_keywords", [])
        if undervalued_kw:
            console.print(f"Undervalued keywords: {', '.join(undervalued_kw[:5])}")

        thresholds = self.learned_patterns.get("engagement_thresholds", {})
        if thresholds:
            console.print(f"Engagement thresholds: {thresholds}")
