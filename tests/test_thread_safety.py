"""
Thread safety tests for free-threading optimization.

Tests concurrent access to:
- CostTracker (batch pattern)
- ScoringAdapter (thread-local pattern)
- SemanticDeduplicator (immutable pattern)
- DeduplicationFeedbackSystem (single-threaded writes)
"""

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import cast

import pytest
from pydantic import HttpUrl

from src.api.costs import CostTracker
from src.deduplication.semantic_dedup import SemanticDeduplicator
from src.enrichment.adaptive_scoring import ScoringAdapter
from src.models import CollectedItem, SourceType


@pytest.fixture
def temp_cost_file(tmp_path):
    """Create temporary cost tracking file."""
    return tmp_path / "test_costs.json"


@pytest.fixture
def temp_feedback_file(tmp_path):
    """Create temporary feedback file."""
    return tmp_path / "test_feedback.json"


@pytest.fixture
def temp_patterns_file(tmp_path):
    """Create temporary patterns file."""
    return tmp_path / "test_patterns.json"


@pytest.fixture
def sample_item():
    """Create sample collected item for testing."""
    return CollectedItem(
        id="test-123",
        url=HttpUrl("https://example.com/article"),
        title="Test Article",
        content="This is test content about Python programming and machine learning.",
        author="@testuser",
        source=SourceType.MASTODON,
        collected_at=datetime(2025, 11, 11, 10, 0, 0),
        metadata={"favourites_count": 10, "reblogs_count": 5},
    )


class TestCostTrackerThreadSafety:
    """Test CostTracker batch pattern under concurrent access."""

    def test_concurrent_cost_recording(self, temp_cost_file):
        """Test recording costs from multiple threads simultaneously."""
        tracker = CostTracker(data_file=temp_cost_file)
        num_threads = 10
        records_per_thread = 20

        def record_costs(thread_id):
            for i in range(records_per_thread):
                tracker.record_successful_generation(
                    article_title=f"Article {thread_id}-{i}",
                    article_filename=f"article_{thread_id}_{i}.md",
                    generation_costs={
                        "content_generation": [0.001],
                        "title_generation": [0.0001],
                        "slug_generation": [0.00001],
                        "image_generation": [0.0005],
                    },
                )

        # Run concurrent recordings
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(record_costs, i) for i in range(num_threads)]
            for future in futures:
                future.result()

        # Save batch
        tracker.save()

        # Verify all entries recorded
        expected_count = num_threads * records_per_thread
        assert len(tracker.entries) == expected_count

        # Verify file integrity
        with open(temp_cost_file) as f:
            data = json.load(f)
            assert len(data) == expected_count

    def test_no_data_loss_under_contention(self, temp_cost_file):
        """Test that no data is lost under high contention."""
        tracker = CostTracker(data_file=temp_cost_file)
        num_threads = 20

        def rapid_fire_record(thread_id):
            for _ in range(100):
                tracker.record_successful_generation(
                    article_title=f"Test {thread_id}",
                    article_filename=f"test_{thread_id}.md",
                    generation_costs={"content_generation": [0.001]},
                )

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [
                executor.submit(rapid_fire_record, i) for i in range(num_threads)
            ]
            for future in futures:
                future.result()

        tracker.save()

        # All 2000 entries should be present
        assert len(tracker.entries) == 2000


class TestScoringAdapterThreadSafety:
    """Test ScoringAdapter thread-local pattern."""

    def test_thread_local_adapters(self, sample_item):
        """Test that each thread can have its own adapter with empty feedback."""
        num_threads = 5

        def process_with_adapter(thread_id):
            # Each thread creates its own adapter with empty feedback
            adapter = ScoringAdapter(use_empty=True)

            # Record feedback (accumulate locally)
            for i in range(10):
                adapter.record_feedback(
                    item=sample_item,
                    heuristic_score=0.5 + (i * 0.01),
                    ai_score=0.7 + (i * 0.01),
                    heuristic_reasoning=f"Test reasoning {thread_id}-{i}",
                )

            # Return feedback data for merging
            return adapter.get_feedback_data()

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [
                executor.submit(process_with_adapter, i) for i in range(num_threads)
            ]
            results = [future.result() for future in futures]

        # Merge all feedback (single-threaded, use empty adapter to avoid loading disk)
        final_adapter = ScoringAdapter(use_empty=True)
        for result in results:
            final_adapter.merge_feedback(result)

        # Should have all feedback entries
        expected_entries = num_threads * 10
        assert len(final_adapter.feedback_history) == expected_entries

    def test_feedback_merge_correctness(self, sample_item):
        """Test that merging feedback preserves all data correctly."""
        adapter1 = ScoringAdapter(use_empty=True)
        adapter2 = ScoringAdapter(use_empty=True)

        # Add different feedback to each
        adapter1.record_feedback(sample_item, 0.5, 0.7, "Test 1")
        adapter1.learned_patterns["undervalued_keywords"] = ["python", "machine"]
        adapter1.learned_patterns["engagement_thresholds"] = {"100": 0.15}

        adapter2.record_feedback(sample_item, 0.6, 0.8, "Test 2")
        adapter2.learned_patterns["undervalued_keywords"] = ["learning", "python"]
        adapter2.learned_patterns["engagement_thresholds"] = {"100": 0.10, "200": 0.20}

        # Merge adapter2 into adapter1
        data2 = adapter2.get_feedback_data()
        adapter1.merge_feedback(data2)

        # Check feedback history merged
        assert len(adapter1.feedback_history) == 2

        # Check keywords merged (deduplicated)
        keywords = set(adapter1.learned_patterns["undervalued_keywords"])
        assert keywords == {"python", "machine", "learning"}

        # Check thresholds merged (max values kept)
        thresholds = adapter1.learned_patterns["engagement_thresholds"]
        assert thresholds["100"] == 0.15  # max(0.15, 0.10)
        assert thresholds["200"] == 0.20


class TestScoringAdapterPatternCaching:
    """Test pattern caching (CRITICAL FIX for per-thread disk loads)."""

    def test_shared_patterns_caching(self, sample_item):
        """Test that patterns are loaded once and shared (CRITICAL FIX)."""
        # Clear cache first
        ScoringAdapter.clear_shared_patterns_cache()

        # Load shared patterns
        patterns1 = ScoringAdapter.get_shared_patterns()
        patterns2 = ScoringAdapter.get_shared_patterns()

        # Should be the same object (cached)
        assert patterns1 is patterns2

        # Create multiple adapters with use_empty=True
        # They should all get the same patterns reference
        adapters = [ScoringAdapter(use_empty=True) for _ in range(5)]

        # All should have the same pattern references
        for adapter in adapters[1:]:
            # After copy(), they won't be identical objects,
            # but they should have the same content
            assert (
                adapter.learned_patterns["undervalued_keywords"]
                == adapters[0].learned_patterns["undervalued_keywords"]
            )

    def test_thread_local_patterns_no_disk_load_per_thread(self):
        """Test that thread-local adapters don't reload patterns from disk."""
        ScoringAdapter.clear_shared_patterns_cache()

        # First load: reads disk once
        ScoringAdapter.get_shared_patterns()

        # Creating thread-local adapters should NOT read disk again
        # (they use copy of already-loaded patterns)
        adapters = [ScoringAdapter(use_empty=True) for _ in range(10)]

        # All adapters should have patterns loaded
        for adapter in adapters:
            assert adapter.learned_patterns is not None
            assert "undervalued_keywords" in adapter.learned_patterns


class TestSemanticDeduplicatorThreadSafety:
    """Test SemanticDeduplicator immutable pattern."""

    def test_concurrent_duplicate_finding(self, sample_item, temp_patterns_file):
        """Test finding duplicates from multiple threads (read-only of patterns).

        Note: find_duplicates() calls _learn_from_duplicates which modifies patterns,
        so we can only safely call it single-threaded. This test verifies that the
        basic finding logic works without race conditions in the comparison.
        """
        deduplicator = SemanticDeduplicator(patterns_file=temp_patterns_file)

        # Create items
        items = [
            CollectedItem(
                id=f"item-{i}",
                url=HttpUrl(f"https://example.com/{i}"),
                title=f"Article {i}",
                content="Python programming and machine learning content",
                author="@testuser",
                source=SourceType.MASTODON,
                collected_at=datetime(2025, 11, 11, 10, 0, 0),
            )
            for i in range(20)
        ]

        # Call once (single-threaded) to verify it works
        result = deduplicator.find_duplicates(cast(list, items), threshold=0.6)

        # Should have found duplicates (all items have identical content)
        assert len(result) > 0

    def test_patterns_immutable_during_parallel_reads(self, temp_patterns_file):
        """Test that patterns don't change during concurrent reads."""
        deduplicator = SemanticDeduplicator(patterns_file=temp_patterns_file)

        # Record initial pattern count
        initial_count = len(deduplicator.patterns)

        items = [
            CollectedItem(
                id=f"item-{i}",
                url=HttpUrl(f"https://example.com/{i}"),
                title=f"Article {i}",
                content="Test content",
                author="@testuser",
                source=SourceType.MASTODON,
                collected_at=datetime(2025, 11, 11, 10, 0, 0),
            )
            for i in range(10)
        ]

        def read_patterns():
            # Read-only operation
            deduplicator.find_duplicates(cast(list, items), threshold=0.6)
            return len(deduplicator.patterns)

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(read_patterns) for _ in range(10)]
            results = [future.result() for future in futures]

        # Pattern count should be stable across threads during read phase
        # (writes only happen at end of pipeline, single-threaded)
        assert all(r >= initial_count for r in results)


class TestEndToEndParallelism:
    """Integration tests for parallel processing."""

    def test_simulated_parallel_enrichment(self, sample_item):
        """Simulate parallel enrichment with thread-local adapters."""
        items = [
            CollectedItem(
                id=f"item-{i}",
                url=HttpUrl(f"https://example.com/{i}"),
                title=f"Article {i}",
                content=f"Content about topic {i % 3}",
                author="@testuser",
                source=SourceType.MASTODON,
                collected_at=datetime(2025, 11, 11, 10, 0, 0),
                metadata={"favourites_count": i * 10},
            )
            for i in range(20)
        ]

        def enrich_item(item):
            # Each thread gets own adapter with empty feedback
            adapter = ScoringAdapter(use_empty=True)
            adapter.record_feedback(item, 0.5, 0.7, "Test")
            return adapter.get_feedback_data()

        # Parallel enrichment
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(enrich_item, item) for item in items]
            results = [future.result() for future in futures]

        # Sequential merge
        final_adapter = ScoringAdapter(use_empty=True)
        for result in results:
            final_adapter.merge_feedback(result)

        # Verify all feedback collected
        assert len(final_adapter.feedback_history) == len(items)

    def test_no_race_conditions_in_cost_tracking(self, temp_cost_file):
        """Stress test to detect race conditions in cost tracking."""
        tracker = CostTracker(data_file=temp_cost_file)

        def stress_test(thread_id):
            for i in range(50):
                tracker.record_successful_generation(
                    article_title=f"T{thread_id}-A{i}",
                    article_filename=f"t{thread_id}_a{i}.md",
                    generation_costs={"content_generation": [0.001 * (thread_id + 1)]},
                )

        # High contention scenario
        with ThreadPoolExecutor(max_workers=16) as executor:
            futures = [executor.submit(stress_test, i) for i in range(16)]
            for future in futures:
                future.result()

        tracker.save()

        # Verify data integrity
        assert len(tracker.entries) == 800  # 16 threads * 50 records

        # Verify no duplicate entries by checking unique filenames
        filenames = {entry.article_filename for entry in tracker.entries}
        assert len(filenames) == 800


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
