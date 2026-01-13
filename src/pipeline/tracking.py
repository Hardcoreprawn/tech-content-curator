"""Pipeline item tracking for debugging and data-driven optimization.

This module tracks each item's journey through the pipeline with detailed
logging and decision points. All tracking data is written to a JSON file
for post-analysis.
"""

import json
from datetime import UTC, datetime

from ..config import get_data_dir
from ..models import EnrichedItem
from ..utils.logging import get_logger

logger = get_logger(__name__)


class PipelineTracker:
    """Track items through the entire pipeline with detailed decision logging."""

    def __init__(self):
        self.data_dir = get_data_dir()
        self.tracking_file = self.data_dir / "pipeline_tracking.json"
        self.tracker_data = {"run_id": datetime.now(UTC).isoformat(), "items": []}

    def track_enrichment(
        self,
        item: EnrichedItem,
        heuristic_score: float,
        ai_score: float,
        topics_found: int,
    ) -> None:
        """Track an item through enrichment."""
        entry = {
            "item_id": item.original.id,
            "title": item.original.title[:100],
            "source": str(item.original.source),
            "stage": "enrichment",
            "timestamp": datetime.now(UTC).isoformat(),
            "scores": {
                "heuristic": heuristic_score,
                "ai": ai_score,
                "final": item.quality_score,
            },
            "topics_found": topics_found,
            "topics": item.topics,
        }
        self.tracker_data["items"].append(entry)
        logger.debug(
            f"Tracked enrichment: {item.original.id} | h={heuristic_score:.2f} a={ai_score:.2f} f={item.quality_score:.2f}"
        )

    def track_candidate_rejection(
        self, item: EnrichedItem, reason: str, filter_stage: str = "candidate_selection"
    ) -> None:
        """Track why an item was rejected from candidate selection."""
        entry = {
            "item_id": item.original.id,
            "title": item.original.title[:100],
            "stage": filter_stage,
            "timestamp": datetime.now(UTC).isoformat(),
            "rejection_reason": reason,
            "scores": {
                "heuristic": getattr(item, "heuristic_score", 0),
                "ai": getattr(item, "ai_score", item.quality_score),
                "final": item.quality_score,
            },
        }
        self.tracker_data["items"].append(entry)
        logger.debug(f"Tracked rejection: {item.original.id} | reason={reason}")

    def track_candidate_acceptance(
        self, item: EnrichedItem, acceptance_reason: str = "quality_passed"
    ) -> None:
        """Track an item that made it through candidate selection."""
        entry = {
            "item_id": item.original.id,
            "title": item.original.title[:100],
            "stage": "candidate_accepted",
            "timestamp": datetime.now(UTC).isoformat(),
            "acceptance_reason": acceptance_reason,
            "scores": {
                "heuristic": getattr(item, "heuristic_score", 0),
                "ai": getattr(item, "ai_score", item.quality_score),
                "final": item.quality_score,
            },
            "topics": item.topics[:5],
        }
        self.tracker_data["items"].append(entry)
        logger.debug(
            f"Tracked acceptance: {item.original.id} | reason={acceptance_reason}"
        )

    def track_generation(
        self, item: EnrichedItem, generator_name: str, success: bool, reason: str = ""
    ) -> None:
        """Track article generation attempt."""
        entry = {
            "item_id": item.original.id,
            "title": item.original.title[:100],
            "stage": "generation",
            "timestamp": datetime.now(UTC).isoformat(),
            "generator": generator_name,
            "success": success,
            "reason": reason,
            "scores": {
                "heuristic": getattr(item, "heuristic_score", 0),
                "ai": getattr(item, "ai_score", item.quality_score),
                "final": item.quality_score,
            },
        }
        self.tracker_data["items"].append(entry)
        logger.debug(
            f"Tracked generation: {item.original.id} | success={success} gen={generator_name}"
        )

    def save(self) -> None:
        """Save tracking data to file."""
        try:
            # Read existing data if it exists
            existing_data = {"runs": []}
            if self.tracking_file.exists():
                with open(self.tracking_file) as f:
                    existing_data = json.load(f)

            # Append this run
            existing_data["runs"].append(self.tracker_data)

            # Keep only last 10 runs to avoid file bloat
            if len(existing_data["runs"]) > 10:
                existing_data["runs"] = existing_data["runs"][-10:]

            with open(self.tracking_file, "w") as f:
                json.dump(existing_data, f, indent=2)

            logger.info(
                f"Saved pipeline tracking: {len(self.tracker_data['items'])} items in {self.tracking_file}"
            )
        except Exception as e:
            logger.exception("Failed to save tracking data")

    def print_summary(self) -> None:
        """Print a summary of the tracking data."""
        items = self.tracker_data["items"]

        enriched = [i for i in items if i["stage"] == "enrichment"]
        accepted = [i for i in items if i["stage"] == "candidate_accepted"]
        rejected = [i for i in items if "rejection" in i.get("stage", "")]
        generated = [
            i for i in items if i["stage"] == "generation" and i.get("success")
        ]

        logger.info(f"\n{'=' * 70}")
        logger.info("PIPELINE TRACKING SUMMARY")
        logger.info(f"{'=' * 70}")
        logger.info(f"Enriched: {len(enriched)}")
        logger.info(f"Candidates accepted: {len(accepted)}")
        logger.info(f"Candidates rejected: {len(rejected)}")
        logger.info(f"Articles generated: {len(generated)}")

        # Score distribution for enriched items
        if enriched:
            ai_scores = [i["scores"]["ai"] for i in enriched]
            heur_scores = [i["scores"]["heuristic"] for i in enriched]
            logger.info("\nAI Score Distribution (enriched):")
            logger.info(f"  Mean: {sum(ai_scores) / len(ai_scores):.2f}")
            logger.info(f"  Below 0.5: {sum(1 for s in ai_scores if s < 0.5)}")
            logger.info(f"  0.5+: {sum(1 for s in ai_scores if s >= 0.5)}")
            logger.info("\nHeuristic Score Distribution (enriched):")
            logger.info(f"  Mean: {sum(heur_scores) / len(heur_scores):.2f}")
            logger.info(f"  Below 0.3: {sum(1 for s in heur_scores if s < 0.3)}")
            logger.info(f"  0.3+: {sum(1 for s in heur_scores if s >= 0.3)}")
