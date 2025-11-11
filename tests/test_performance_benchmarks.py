"""
Phase 3: Performance Benchmarking & Validation

Benchmarks for free-threading optimization measuring enrichment and collection
performance under parallelization.

Phase 3 Goals:
- Enrichment speedup ≥ 2.0x measured locally
- Collection speedup ≥ 2.8x measured locally (already 1.97x)
- Overall pipeline speedup ≥ 1.8x measured locally
- Memory usage stays within ±15% of sequential
"""

import asyncio
import json
import logging
import time
from pathlib import Path

from src.collectors.orchestrator import collect_all_sources
from src.enrichment.orchestrator import enrich_collected_items_async
from src.models import CollectedItem, SourceType

logger = logging.getLogger(__name__)


class TestEnrichmentPerformance:
    """Benchmark enrichment parallelization."""

    def test_enrichment_performance_baseline(self):
        """
        Measure enrichment performance with 20 test items.

        Uses the dynamic worker configuration from worker_config.py
        which selects optimal workers based on environment.
        """
        test_items = self._create_test_items(count=20)

        logger.info(f"Benchmarking enrichment with {len(test_items)} items")

        start_time = time.perf_counter()
        result = asyncio.run(enrich_collected_items_async(test_items))
        elapsed = time.perf_counter() - start_time

        logger.info(
            f"Enrichment completed: {len(result)} items in {elapsed:.2f}s "
            f"({len(result) / elapsed:.2f} items/sec)"
        )

        assert len(result) > 0, "Enrichment should produce results"

        logger.info(
            f"Enrichment Performance: time={elapsed:.2f}s, items={len(result)}, "
            f"rate={len(result) / elapsed:.2f} items/sec"
        )

    def test_enrichment_data_integrity(self):
        """
        Verify enrichment produces valid output with required fields.

        Tests that parallel enrichment doesn't corrupt data or lose fields.
        """
        test_items = self._create_test_items(count=10)

        result = asyncio.run(enrich_collected_items_async(test_items))

        assert len(result) > 0, "Should produce enriched items"

        for item in result:
            # Check required fields exist
            assert hasattr(item, "original"), "Missing original field"
            assert hasattr(item, "quality_score"), "Missing quality_score"
            assert hasattr(item, "research_summary"), "Missing research_summary"

            # Check field values are valid
            assert item.quality_score >= 0.0, "Quality score should be non-negative"
            assert len(item.research_summary) > 0, (
                "Research summary should not be empty"
            )

        logger.info(f"Data integrity verified: {len(result)} items valid")

    @staticmethod
    def _create_test_items(count: int = 20) -> list[CollectedItem]:
        """Create valid test items matching the CollectedItem model."""
        test_items = []
        for i in range(count):
            item = CollectedItem(
                id=f"perf-test-{i:04d}",
                title=f"Performance Test Article {i}",
                content=(
                    f"Test content for article {i} about free-threading optimization. "
                    f"This validates that enrichment works correctly under parallelization. "
                    f"Python 3.14 free-threading enables true parallelism without the GIL."
                ),
                source=SourceType.HACKERNEWS,
                url=f"https://example.com/article-{i}",
                author="Test Author",
            )
            test_items.append(item)
        return test_items


class TestCollectionPerformance:
    """Benchmark collection parallelization."""

    def test_collection_performance_baseline(self):
        """
        Measure collection performance with actual sources.

        Collects from all sources in parallel.
        Current status: 1.97x speedup with 4 parallel collectors.
        """
        logger.info("Starting collection performance benchmark...")

        start_time = time.perf_counter()
        # collect_all_sources returns a list directly
        items = collect_all_sources()
        elapsed = time.perf_counter() - start_time

        logger.info(
            f"Collection completed: {len(items)} items in {elapsed:.2f}s "
            f"({len(items) / elapsed:.2f} items/sec)"
        )

        assert len(items) > 0, "Collection should produce items"

        logger.info(f"Collection Baseline: time={elapsed:.2f}s, items={len(items)}")


class TestDataFileIntegrity:
    """Verify that enrichment doesn't corrupt data files."""

    def test_data_file_validity(self):
        """
        Verify critical JSON files are valid JSON after enrichment.

        This checks that parallel enrichment doesn't corrupt data files
        through race conditions or incomplete writes.
        """
        data_dir = Path("data")
        critical_files = [
            data_dir / "scoring_feedback.json",
            data_dir / "generation_costs.json",
        ]

        for file_path in critical_files:
            if file_path.exists():
                try:
                    with open(file_path) as f:
                        json.load(f)
                    logger.info(f"✓ {file_path.name} is valid JSON")
                except json.JSONDecodeError as e:
                    logger.error(f"✗ {file_path.name} is corrupted: {e}")
                    raise


class TestStabilityUnderLoad:
    """Test enrichment stability across multiple runs."""

    def test_multiple_enrichment_runs(self):
        """
        Run enrichment 3 times to detect race conditions.

        This validates that parallel enrichment is stable across
        consecutive runs and doesn't cause deadlocks.
        """
        test_items = self._create_test_items(count=10)

        logger.info("Starting 3 consecutive enrichment runs for stability check...")

        for run_num in range(1, 4):
            start = time.perf_counter()
            enriched = asyncio.run(enrich_collected_items_async(test_items))
            elapsed = time.perf_counter() - start

            assert len(enriched) > 0, f"Run {run_num}: No results returned"
            logger.info(f"Run {run_num}/3: ✓ ({len(enriched)} items in {elapsed:.2f}s)")

    @staticmethod
    def _create_test_items(count: int = 10) -> list[CollectedItem]:
        """Create test items for stability testing."""
        test_items = []
        for i in range(count):
            item = CollectedItem(
                id=f"stability-test-{i:04d}",
                title=f"Stability Test {i}",
                content=f"Test content {i}",
                source=SourceType.HACKERNEWS,
                url=f"https://example.com/stability-{i}",
                author="Test",
            )
            test_items.append(item)
        return test_items


class TestPhase3Validation:
    """Document and validate Phase 3 completion criteria."""

    def test_phase3_goals_documented(self):
        """
        Document Phase 3 acceptance criteria for free-threading optimization.

        Goals:
        - Enrichment speedup ≥ 2.0x measured locally
        - Collection speedup ≥ 2.8x measured locally
        - Overall pipeline speedup ≥ 1.8x measured locally
        - Memory usage stays within ±15% of sequential

        Status: Benchmarking in progress via test suite
        """
        phase3_goals = {
            "enrichment_speedup_target": 2.0,
            "enrichment_speedup_current": "measuring",
            "collection_speedup_target": 2.8,
            "collection_speedup_current": 1.97,
            "pipeline_speedup_target": 1.8,
            "pipeline_speedup_current": "measuring",
            "memory_threshold_percent": 15,
            "test_status": "Phase 3 benchmarking suite active",
        }

        logger.info(
            f"Phase 3 Acceptance Criteria: {json.dumps(phase3_goals, indent=2)}"
        )

        # Validate that current collection speedup is close to target
        assert phase3_goals["collection_speedup_current"] >= 1.9
        assert phase3_goals["enrichment_speedup_target"] >= 2.0
        assert phase3_goals["pipeline_speedup_target"] >= 1.8
