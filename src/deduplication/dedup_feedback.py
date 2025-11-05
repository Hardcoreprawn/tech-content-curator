"""
Feedback system for deduplication quality assessment.
"""

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from ..utils.logging import get_logger
from .semantic_dedup import SemanticDeduplicator

logger = get_logger(__name__)


@dataclass
class DeduplicationFeedback:
    """Feedback about deduplication quality."""

    items_processed: int
    duplicates_found: int
    patterns_used: int
    timestamp: datetime
    examples: list[dict]  # Examples of items that were/weren't deduplicated
    user_corrections: dict | None = None  # Manual corrections if any


class DeduplicationFeedbackSystem:
    """System for collecting and analyzing deduplication feedback."""

    def __init__(self, feedback_file: Path = Path("data/dedup_feedback.json")):
        self.feedback_file = feedback_file
        self.feedback_history: list[DeduplicationFeedback] = []
        self.load_feedback()

    def record_deduplication_session(
        self,
        original_items: list,
        deduplicated_items: list,
        deduplicator: SemanticDeduplicator,
    ):
        """Record the results of a deduplication session."""

        logger.debug(f"Recording dedup session: {len(original_items)} items -> {len(deduplicated_items)} unique")

        # Get examples of what was deduplicated
        examples = []
        duplicate_groups = deduplicator.find_duplicates(original_items, threshold=0.6)

        for group in duplicate_groups[:3]:  # First 3 groups as examples
            group_example = {
                "group_size": len(group),
                "kept_item": group[0].content[:100]
                if hasattr(group[0], "content")
                else str(group[0])[:100],
                "removed_items": [
                    item.content[:100] if hasattr(item, "content") else str(item)[:100]
                    for item in group[1:]
                ],
            }
            examples.append(group_example)

        stats = deduplicator.get_pattern_stats()

        feedback = DeduplicationFeedback(
            items_processed=len(original_items),
            duplicates_found=len(original_items) - len(deduplicated_items),
            patterns_used=stats.get("total_patterns", 0),
            timestamp=datetime.now(),
            examples=examples,
        )

        self.feedback_history.append(feedback)
        self.save_feedback()

        logger.info(f"Dedup session recorded: {feedback.duplicates_found} duplicates found, "
                   f"{feedback.patterns_used} patterns used")

        return feedback

    def suggest_improvements(self) -> list[str]:
        """Analyze feedback history and suggest improvements."""
        if not self.feedback_history:
            return ["No feedback history available yet."]

        suggestions = []
        recent_sessions = self.feedback_history[-5:]  # Last 5 sessions

        # Analyze duplicate detection rate
        total_processed = sum(f.items_processed for f in recent_sessions)
        total_duplicates = sum(f.duplicates_found for f in recent_sessions)

        if total_processed > 0:
            duplicate_rate = total_duplicates / total_processed

            if duplicate_rate < 0.05:
                suggestions.append(
                    "Low duplicate detection rate (<5%). Consider lowering similarity threshold."
                )
            elif duplicate_rate > 0.3:
                suggestions.append(
                    "High duplicate detection rate (>30%). Consider raising similarity threshold to avoid false positives."
                )

        # Analyze pattern usage
        avg_patterns = sum(f.patterns_used for f in recent_sessions) / len(
            recent_sessions
        )
        if avg_patterns < 2:
            suggestions.append("Few learned patterns. System needs more training data.")
        elif avg_patterns > 20:
            suggestions.append(
                "Many patterns learned. Consider pruning old or low-confidence patterns."
            )

        # Check for consistent duplication examples
        common_entities = {}
        for feedback in recent_sessions:
            for example in feedback.examples:
                # Extract common words from kept items
                words = example["kept_item"].lower().split()[:10]  # First 10 words
                for word in words:
                    if len(word) > 4:  # Skip short words
                        common_entities[word] = common_entities.get(word, 0) + 1

        # Suggest new entity patterns
        frequent_entities = [
            word for word, count in common_entities.items() if count >= 3
        ]
        if frequent_entities:
            suggestions.append(
                f"Consider adding these entities to pattern matching: {', '.join(frequent_entities[:5])}"
            )

        return suggestions if suggestions else ["Deduplication performance looks good!"]

    def get_quality_metrics(self) -> dict:
        """Get quality metrics for deduplication performance."""
        if not self.feedback_history:
            return {}

        recent = self.feedback_history[-10:]  # Last 10 sessions

        return {
            "total_sessions": len(self.feedback_history),
            "avg_items_per_session": sum(f.items_processed for f in recent)
            / len(recent),
            "avg_duplicates_found": sum(f.duplicates_found for f in recent)
            / len(recent),
            "duplicate_rate": sum(f.duplicates_found for f in recent)
            / max(1, sum(f.items_processed for f in recent)),
            "patterns_growth": recent[-1].patterns_used - recent[0].patterns_used
            if len(recent) > 1
            else 0,
            "last_session": recent[-1].timestamp.isoformat(),
        }

    def save_feedback(self):
        """Save feedback history to file."""
        self.feedback_file.parent.mkdir(exist_ok=True)

        feedback_data = []
        for feedback in self.feedback_history:
            data = asdict(feedback)
            data["timestamp"] = feedback.timestamp.isoformat()
            feedback_data.append(data)

        with open(self.feedback_file, "w") as f:
            json.dump(feedback_data, f, indent=2)

    def load_feedback(self):
        """Load feedback history from file."""
        if not self.feedback_file.exists():
            return

        try:
            with open(self.feedback_file) as f:
                feedback_data = json.load(f)

            self.feedback_history = []
            for data in feedback_data:
                feedback = DeduplicationFeedback(
                    items_processed=data["items_processed"],
                    duplicates_found=data["duplicates_found"],
                    patterns_used=data["patterns_used"],
                    timestamp=datetime.fromisoformat(data["timestamp"]),
                    examples=data["examples"],
                    user_corrections=data.get("user_corrections"),
                )
                self.feedback_history.append(feedback)

        except Exception as e:
            print(f"Error loading deduplication feedback: {e}")
            self.feedback_history = []
