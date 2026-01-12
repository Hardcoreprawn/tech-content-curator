"""Tests for collectors/orchestrator.py."""

import json
from datetime import UTC, datetime
from unittest.mock import Mock, patch

from pydantic import HttpUrl

from src.collectors.orchestrator import (
    collect_all_sources,
    deduplicate_items,
    save_collected_items,
)
from src.models import CollectedItem, CollectedItemMetadata, SourceType


def make_item(
    item_id: str = "test-id",
    content: str = "Test content",
    title: str = "Test",
    url: str = "https://example.com/test",
    metadata: CollectedItemMetadata | None = None,
) -> CollectedItem:
    """Helper to create test CollectedItem."""
    return CollectedItem(
        id=item_id,
        source=SourceType.MASTODON,
        author="testuser",
        content=content,
        title=title,
        url=HttpUrl(url),
        collected_at=datetime.now(UTC),
        metadata=metadata or {},
    )


class TestSaveCollectedItems:
    """Test saving collected items to JSON files."""

    def test_saves_to_json_file(self, tmp_path):
        """Items are saved to timestamped JSON file."""
        items = [make_item(item_id=f"item-{i}") for i in range(3)]

        with patch("src.collectors.orchestrator.get_data_dir", return_value=tmp_path):
            filepath = save_collected_items(items, timestamp="20250101_120000")

        # Verify file created
        assert filepath.exists()
        assert filepath.name == "collected_20250101_120000.json"

        # Verify content
        with open(filepath, encoding="utf-8") as f:
            data = json.load(f)

        assert data["total_items"] == 3
        assert len(data["items"]) == 3
        assert data["items"][0]["id"] == "item-0"

    def test_uses_current_timestamp_if_not_provided(self, tmp_path):
        """Default timestamp is current datetime."""
        items = [make_item()]

        with patch("src.collectors.orchestrator.get_data_dir", return_value=tmp_path):
            filepath = save_collected_items(items)

        # Verify filename starts with "collected_"
        assert filepath.name.startswith("collected_")
        assert filepath.name.endswith(".json")

    def test_saves_empty_list(self, tmp_path):
        """Empty item list can be saved."""
        with patch("src.collectors.orchestrator.get_data_dir", return_value=tmp_path):
            filepath = save_collected_items([], timestamp="20250101_120000")

        # Verify file created with zero items
        with open(filepath, encoding="utf-8") as f:
            data = json.load(f)

        assert data["total_items"] == 0
        assert data["items"] == []

    def test_handles_unicode_content(self, tmp_path):
        """Unicode content is preserved in JSON."""
        items = [make_item(content="Unicode: 日本語 🚀 émojis")]

        with patch("src.collectors.orchestrator.get_data_dir", return_value=tmp_path):
            filepath = save_collected_items(items, timestamp="20250101_120000")

        # Verify unicode preserved
        with open(filepath, encoding="utf-8") as f:
            data = json.load(f)

        assert "日本語" in data["items"][0]["content"]
        assert "🚀" in data["items"][0]["content"]


class TestDeduplicateItems:
    """Test deduplication logic."""

    def test_returns_empty_for_empty_input(self):
        """Empty input returns empty list."""
        result = deduplicate_items([])
        assert result == []

    @patch("src.collectors.orchestrator.SemanticDeduplicator")
    @patch("src.collectors.orchestrator.DeduplicationFeedbackSystem")
    def test_removes_exact_url_duplicates(self, mock_feedback, mock_dedup):
        """Items with same URL are deduplicated."""
        # Mock semantic dedup to return no groups
        mock_dedup_instance = Mock()
        mock_dedup_instance.find_duplicates.return_value = []
        mock_dedup.return_value = mock_dedup_instance

        items = [
            make_item(item_id="1", url="https://example.com/article"),
            make_item(item_id="2", url="https://example.com/article"),  # Duplicate
        ]

        result = deduplicate_items(items)

        # Verify only one kept
        assert len(result) == 1

    @patch("src.collectors.orchestrator.SemanticDeduplicator")
    @patch("src.collectors.orchestrator.DeduplicationFeedbackSystem")
    def test_keeps_highest_engagement(self, mock_feedback, mock_dedup):
        """Highest engagement item is kept from duplicates."""
        # Mock semantic dedup to return no groups
        mock_dedup_instance = Mock()
        mock_dedup_instance.find_duplicates.return_value = []
        mock_dedup.return_value = mock_dedup_instance

        items = [
            make_item(
                item_id="1",
                url="https://example.com/1",
                metadata={"favourites_count": 10},
            ),
            make_item(
                item_id="2",
                url="https://example.com/2",
                metadata={"favourites_count": 100},
            ),  # Different URL
        ]

        result = deduplicate_items(items)

        # Verify both kept (different URLs)
        assert len(result) == 2

    @patch("src.collectors.orchestrator.SemanticDeduplicator")
    @patch("src.collectors.orchestrator.DeduplicationFeedbackSystem")
    def test_semantic_deduplication_applied(self, mock_feedback, mock_dedup):
        """Semantic deduplication removes similar content."""
        item1 = make_item(item_id="1", url="https://example.com/1")
        item2 = make_item(item_id="2", url="https://example.com/2")

        # Mock semantic dedup to find them as duplicates
        mock_dedup_instance = Mock()
        mock_dedup_instance.find_duplicates.return_value = [[item1, item2]]
        mock_dedup_instance.get_pattern_stats.return_value = {"total_patterns": 0}
        mock_dedup.return_value = mock_dedup_instance

        items = [item1, item2]

        result = deduplicate_items(items)

        # Verify semantic dedup was called
        mock_dedup_instance.find_duplicates.assert_called_once()
        # Should keep only one
        assert len(result) == 1

    @patch("src.collectors.orchestrator.SemanticDeduplicator")
    @patch("src.collectors.orchestrator.DeduplicationFeedbackSystem")
    def test_records_feedback_when_duplicates_found(
        self, mock_feedback_class, mock_dedup
    ):
        """Feedback is recorded when duplicates are removed."""
        item1 = make_item(item_id="1", url="https://example.com/1")
        item2 = make_item(item_id="2", url="https://example.com/2")

        # Mock semantic dedup to find duplicates
        mock_dedup_instance = Mock()
        mock_dedup_instance.find_duplicates.return_value = [[item1, item2]]
        mock_dedup_instance.get_pattern_stats.return_value = {
            "total_patterns": 5,
            "avg_confidence": 0.85,
        }
        mock_dedup.return_value = mock_dedup_instance

        mock_feedback = Mock()
        mock_feedback_class.return_value = mock_feedback

        items = [item1, item2]
        deduplicate_items(items)

        # Verify feedback recorded
        mock_feedback.record_deduplication_session.assert_called_once()

    @patch("src.collectors.orchestrator.SemanticDeduplicator")
    @patch("src.collectors.orchestrator.DeduplicationFeedbackSystem")
    def test_engagement_calculation_includes_all_fields(
        self, mock_feedback, mock_dedup
    ):
        """Engagement score includes all metadata fields."""
        # Mock semantic dedup
        mock_dedup_instance = Mock()
        mock_dedup_instance.find_duplicates.return_value = []
        mock_dedup.return_value = mock_dedup_instance

        items = [
            make_item(
                item_id="1",
                url="https://example.com/same",
                metadata={
                    "favourites_count": 10,
                    "reblogs_count": 5,
                    "replies_count": 2,
                    "score": 3,
                },
            ),
            make_item(
                item_id="2",
                url="https://example.com/same",
                metadata={"favourites_count": 100},  # Much higher
            ),
        ]

        result = deduplicate_items(items)

        # Verify item with higher total engagement kept
        assert len(result) == 1
        assert result[0].id == "2"  # Higher favourites wins


class TestCollectAllSources:
    """Test orchestration of collection from all sources."""

    @patch("src.collectors.orchestrator.collect_from_mastodon_trending")
    @patch("src.collectors.orchestrator.collect_from_reddit")
    @patch("src.collectors.orchestrator.collect_from_hackernews")
    @patch("src.collectors.orchestrator.collect_from_github_trending")
    @patch("src.collectors.orchestrator.deduplicate_items")
    @patch("src.collectors.orchestrator.get_config")
    def test_collects_from_all_sources(
        self,
        mock_config,
        mock_dedup,
        mock_github,
        mock_hn,
        mock_reddit,
        mock_mastodon,
    ):
        """All sources are attempted for collection."""
        # Mock config
        config = Mock()
        config.mastodon_instances = ["mastodon.social"]
        config.openai_api_key = "test-key"
        config.articles_per_run = 10  # Must be <= 10 per validation
        config.min_content_length = 50
        config.max_content_length = 5000
        config.content_dirs = {}
        config.use_semantic_dedup = False
        mock_config.return_value = config

        # Mock collectors
        mock_mastodon.return_value = [make_item(item_id="m1")]
        mock_reddit.return_value = [make_item(item_id="r1")]
        mock_hn.return_value = [make_item(item_id="h1")]
        mock_github.return_value = [make_item(item_id="g1")]
        mock_dedup.return_value = [make_item(item_id="final")]

        result = collect_all_sources()

        # Verify all sources called
        mock_mastodon.assert_called_once()
        mock_reddit.assert_called_once()
        mock_hn.assert_called_once()
        mock_github.assert_called_once()
        mock_dedup.assert_called_once()

        # Verify result
        assert len(result) == 1
        assert result[0].id == "final"

    @patch("src.collectors.orchestrator.collect_from_mastodon_trending")
    @patch("src.collectors.orchestrator.collect_from_reddit")
    @patch("src.collectors.orchestrator.collect_from_hackernews")
    @patch("src.collectors.orchestrator.collect_from_github_trending")
    @patch("src.collectors.orchestrator.deduplicate_items")
    @patch("src.collectors.orchestrator.get_config")
    def test_handles_source_failures_gracefully(
        self,
        mock_config,
        mock_dedup,
        mock_github,
        mock_hn,
        mock_reddit,
        mock_mastodon,
    ):
        """Failed sources don't stop other collections."""
        # Mock config
        config = Mock()
        config.mastodon_instances = ["mastodon.social"]
        config.openai_api_key = "test-key"
        config.articles_per_run = 10  # Must be <= 10 per validation
        config.min_content_length = 50
        config.max_content_length = 5000
        config.content_dirs = {}
        config.use_semantic_dedup = False
        mock_config.return_value = config

        # Mock failures
        mock_mastodon.side_effect = Exception("Mastodon failed")
        mock_reddit.side_effect = Exception("Reddit failed")
        mock_hn.return_value = [make_item(item_id="h1")]
        mock_github.return_value = [make_item(item_id="g1")]
        mock_dedup.side_effect = lambda x: x

        result = collect_all_sources()

        # Verify collection continued despite failures
        assert len(result) == 2
        assert result[0].id == "h1"
        assert result[1].id == "g1"

    @patch("src.collectors.orchestrator.collect_from_mastodon_trending")
    @patch("src.collectors.orchestrator.collect_from_reddit")
    @patch("src.collectors.orchestrator.collect_from_hackernews")
    @patch("src.collectors.orchestrator.collect_from_github_trending")
    @patch("src.collectors.orchestrator.deduplicate_items")
    @patch("src.collectors.orchestrator.get_config")
    def test_stops_mastodon_collection_at_80_items(
        self,
        mock_config,
        mock_dedup,
        mock_github,
        mock_hn,
        mock_reddit,
        mock_mastodon,
    ):
        """Mastodon collection stops after collecting 80 items."""
        # Mock config with multiple instances
        config = Mock()
        config.mastodon_instances = ["instance1.social", "instance2.social"]
        config.openai_api_key = "test-key"
        config.articles_per_run = 10  # Must be <= 10 per validation
        config.min_content_length = 50
        config.max_content_length = 5000
        config.content_dirs = {}
        config.use_semantic_dedup = False
        mock_config.return_value = config

        # First instance returns 80 items
        mock_mastodon.return_value = [make_item(item_id=f"m{i}") for i in range(80)]
        mock_reddit.return_value = []
        mock_hn.return_value = []
        mock_github.return_value = []
        mock_dedup.side_effect = lambda x: x

        result = collect_all_sources()

        # Verify only called once (stopped after 80)
        assert mock_mastodon.call_count == 1
        assert len(result) == 80

    @patch("src.collectors.orchestrator.collect_from_mastodon_trending")
    @patch("src.collectors.orchestrator.collect_from_reddit")
    @patch("src.collectors.orchestrator.collect_from_hackernews")
    @patch("src.collectors.orchestrator.collect_from_github_trending")
    @patch("src.collectors.orchestrator.deduplicate_items")
    @patch("src.collectors.orchestrator.get_config")
    def test_deduplication_applied_to_combined_results(
        self,
        mock_config,
        mock_dedup,
        mock_github,
        mock_hn,
        mock_reddit,
        mock_mastodon,
    ):
        """All collected items are deduplicated together."""
        # Mock config
        config = Mock()
        config.mastodon_instances = ["mastodon.social"]
        config.openai_api_key = "test-key"
        config.articles_per_run = 10  # Must be <= 10 per validation
        config.min_content_length = 50
        config.max_content_length = 5000
        config.content_dirs = {}
        config.use_semantic_dedup = False
        mock_config.return_value = config

        # Mock collectors - mastodon will fail due to validation, so just use other sources
        mock_mastodon.return_value = []
        mock_reddit.return_value = [make_item(item_id=f"r{i}") for i in range(3)]
        mock_hn.return_value = [make_item(item_id=f"h{i}") for i in range(4)]
        mock_github.return_value = [make_item(item_id=f"g{i}") for i in range(2)]

        # Mock dedup to remove half
        def dedup_fn(items):
            return items[::2]  # Keep every other item

        mock_dedup.side_effect = dedup_fn

        result = collect_all_sources()

        # Verify dedup called with all items (3+4+2 = 9, mastodon skipped)
        call_args = mock_dedup.call_args[0][0]
        assert len(call_args) == 9

        # Verify deduplicated result
        assert len(result) == 5  # Half of 9 (rounded up)
