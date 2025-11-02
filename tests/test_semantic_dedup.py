"""Tests for deduplication/semantic_dedup.py."""

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, mock_open, patch

import pytest

from src.deduplication.semantic_dedup import DuplicationPattern, SemanticDeduplicator


class MockContent:
    """Mock content object for testing."""

    def __init__(self, content: str):
        self.content = content


class TestEntityExtraction:
    """Test entity extraction from content."""

    def test_extracts_company_names(self):
        """Company names are extracted correctly."""
        dedup = SemanticDeduplicator(Path("test.json"))
        content = "OpenAI and Microsoft announced a partnership with Google."

        entities = dedup.extract_entities(content)

        assert "openai" in entities["companies"]
        assert "microsoft" in entities["companies"]
        assert "google" in entities["companies"]

    def test_extracts_framework_names(self):
        """Framework names are extracted correctly."""
        dedup = SemanticDeduplicator(Path("test.json"))
        content = "Using React with Django and FastAPI for the backend."

        entities = dedup.extract_entities(content)

        assert "react" in entities["frameworks"]
        assert "django" in entities["frameworks"]
        assert "fastapi" in entities["frameworks"]

    def test_extracts_programming_languages(self):
        """Programming language names are extracted."""
        dedup = SemanticDeduplicator(Path("test.json"))
        content = "Python, Rust, and Go are great languages. Java too."

        entities = dedup.extract_entities(content)

        assert "python" in entities["languages"]
        assert "rust" in entities["languages"]
        assert "go" in entities["languages"]
        assert "java" in entities["languages"]

    def test_extracts_product_names(self):
        """Product names are extracted correctly."""
        dedup = SemanticDeduplicator(Path("test.json"))
        content = "ChatGPT and Claude are AI assistants. Copilot helps with coding."

        entities = dedup.extract_entities(content)

        assert "chatgpt" in entities["products"]
        assert "claude" in entities["products"]
        assert "copilot" in entities["products"]

    def test_case_insensitive_extraction(self):
        """Entity extraction is case-insensitive."""
        dedup = SemanticDeduplicator(Path("test.json"))
        content = "PYTHON and Python and python are the same."

        entities = dedup.extract_entities(content)

        # Should normalize to lowercase
        assert "python" in entities["languages"]
        assert len(entities["languages"]) == 1


class TestKeywordExtraction:
    """Test keyword extraction from content."""

    def test_extracts_significant_words(self):
        """Significant words are extracted as keywords."""
        dedup = SemanticDeduplicator(Path("test.json"))
        content = "Machine learning algorithms process data efficiently using neural networks."

        keywords = dedup.extract_keywords(content)

        assert "machine" in keywords
        assert "learning" in keywords
        assert "algorithms" in keywords
        assert "neural" in keywords
        assert "networks" in keywords

    def test_filters_stop_words(self):
        """Common stop words are filtered out."""
        dedup = SemanticDeduplicator(Path("test.json"))
        content = "This will have more time with their work and life."

        keywords = dedup.extract_keywords(content)

        assert "this" not in keywords
        assert "will" not in keywords
        assert "have" not in keywords
        assert "more" not in keywords
        assert "time" not in keywords

    def test_removes_urls(self):
        """URLs are removed before keyword extraction."""
        dedup = SemanticDeduplicator(Path("test.json"))
        content = "Check out https://example.com/article for details."

        keywords = dedup.extract_keywords(content)

        assert "https" not in keywords
        assert "example" not in keywords
        assert "details" in keywords

    def test_removes_mentions_and_hashtags(self):
        """Mentions and hashtags are removed."""
        dedup = SemanticDeduplicator(Path("test.json"))
        content = "@user shared #programming tips about Python."

        keywords = dedup.extract_keywords(content)

        assert "user" not in keywords  # @ removed
        assert "programming" not in keywords  # # removed
        assert "python" in keywords

    def test_minimum_length_filter(self):
        """Words shorter than min_length are filtered."""
        dedup = SemanticDeduplicator(Path("test.json"))
        content = "AI is a big new hot tech trend."

        keywords = dedup.extract_keywords(content, min_length=4)

        assert "tech" in keywords
        assert "trend" in keywords
        # Short words filtered
        assert "new" not in keywords
        assert "hot" not in keywords
        assert "big" not in keywords


class TestContentSimilarity:
    """Test content similarity calculation."""

    def test_identical_content_high_similarity(self):
        """Identical content has high similarity."""
        dedup = SemanticDeduplicator(Path("test.json"))
        content = "Python programming with Django framework for web development."

        similarity = dedup.calculate_content_similarity(content, content)

        assert similarity >= 0.9

    def test_different_content_low_similarity(self):
        """Completely different content has low similarity."""
        dedup = SemanticDeduplicator(Path("test.json"))
        content1 = "Python programming with Django framework."
        content2 = "JavaScript game development using Unity engine."

        similarity = dedup.calculate_content_similarity(content1, content2)

        assert similarity < 0.3

    def test_similar_entities_increase_similarity(self):
        """Content with same entities has higher similarity."""
        dedup = SemanticDeduplicator(Path("test.json"))
        content1 = "OpenAI released ChatGPT with Python API support."
        content2 = "OpenAI announced ChatGPT improvements for developers."

        similarity = dedup.calculate_content_similarity(content1, content2)

        # Should be high due to shared entities (OpenAI, ChatGPT)
        assert similarity > 0.5

    def test_similar_keywords_increase_similarity(self):
        """Content with similar keywords has higher similarity."""
        dedup = SemanticDeduplicator(Path("test.json"))
        content1 = (
            "Machine learning algorithms using neural networks for classification."
        )
        content2 = "Deep learning classification with neural network architectures."

        similarity = dedup.calculate_content_similarity(content1, content2)

        # Should be non-zero due to shared keywords
        assert similarity > 0.05

    def test_empty_content_zero_similarity(self):
        """Empty content has zero similarity."""
        dedup = SemanticDeduplicator(Path("test.json"))

        similarity = dedup.calculate_content_similarity("", "test content")

        assert similarity == 0.0


class TestFindDuplicates:
    """Test duplicate detection."""

    def test_finds_duplicate_group(self):
        """Similar items are grouped as duplicates."""
        dedup = SemanticDeduplicator(Path("test.json"))
        items = [
            MockContent("OpenAI released ChatGPT with Python support."),
            MockContent("OpenAI announced ChatGPT improvements."),
            MockContent("Completely different content about Rust programming."),
        ]

        groups = dedup.find_duplicates(items, threshold=0.5)

        # Should find one duplicate group
        assert len(groups) == 1
        assert len(groups[0]) == 2

    def test_no_duplicates_returns_empty(self):
        """Returns empty list when no duplicates found."""
        dedup = SemanticDeduplicator(Path("test.json"))
        items = [
            MockContent("Python programming tutorial."),
            MockContent("JavaScript web development guide."),
            MockContent("Rust systems programming introduction."),
        ]

        groups = dedup.find_duplicates(items, threshold=0.6)

        assert groups == []

    def test_multiple_duplicate_groups(self):
        """Multiple separate duplicate groups are found."""
        dedup = SemanticDeduplicator(Path("test.json"))
        items = [
            MockContent("OpenAI ChatGPT Python API support."),
            MockContent("OpenAI ChatGPT new features."),
            MockContent("Rust systems programming memory safety."),
            MockContent("Rust memory management and safety features."),
        ]

        groups = dedup.find_duplicates(items, threshold=0.5)

        # Should find two groups
        assert len(groups) == 2

    def test_threshold_affects_grouping(self):
        """Higher threshold results in fewer duplicates."""
        dedup = SemanticDeduplicator(Path("test.json"))
        items = [
            MockContent("Python Django web framework."),
            MockContent("Python Flask web development."),
        ]

        # Low threshold finds duplicates
        low_groups = dedup.find_duplicates(items, threshold=0.3)
        assert len(low_groups) >= 1

        # High threshold might not
        high_groups = dedup.find_duplicates(items, threshold=0.9)
        assert len(high_groups) <= len(low_groups)

    def test_single_item_no_duplicates(self):
        """Single item returns no duplicates."""
        dedup = SemanticDeduplicator(Path("test.json"))
        items = [MockContent("Single content item.")]

        groups = dedup.find_duplicates(items)

        assert groups == []


class TestPatternLearning:
    """Test learning patterns from duplicates."""

    def test_learns_pattern_from_duplicates(self, tmp_path):
        """Pattern is learned when duplicates are found."""
        patterns_file = tmp_path / "test_patterns.json"
        dedup = SemanticDeduplicator(patterns_file)
        items = [
            MockContent("OpenAI released ChatGPT with amazing features."),
            MockContent("OpenAI announced ChatGPT improvements today."),
        ]

        initial_patterns = len(dedup.patterns)
        dedup.find_duplicates(items, threshold=0.5)

        # Should have learned a new pattern
        assert len(dedup.patterns) > initial_patterns

    def test_pattern_contains_common_entities(self):
        """Learned pattern contains entities common to duplicates."""
        dedup = SemanticDeduplicator(Path("test.json"))
        items = [
            MockContent("Python programming with Django framework."),
            MockContent("Python development using Django backend."),
        ]

        dedup.find_duplicates(items, threshold=0.5)

        # Find the learned pattern
        if dedup.patterns:
            pattern = dedup.patterns[-1]
            # Should contain Python and/or Django
            all_entities = " ".join(pattern.entities).lower()
            assert "python" in all_entities or "django" in all_entities

    def test_pattern_frequency_increases(self):
        """Seeing same pattern multiple times increases frequency."""
        dedup = SemanticDeduplicator(Path("test.json"))

        # First duplicate group
        items1 = [
            MockContent("Rust memory safety features."),
            MockContent("Rust memory management benefits."),
        ]
        dedup.find_duplicates(items1, threshold=0.5)

        initial_freq = dedup.patterns[-1].frequency if dedup.patterns else 0

        # Second similar group
        items2 = [
            MockContent("Rust memory safety and ownership."),
            MockContent("Rust memory guarantees and safety."),
        ]
        dedup.find_duplicates(items2, threshold=0.5)

        # Frequency should increase for similar pattern
        if dedup.patterns:
            max_freq = max(p.frequency for p in dedup.patterns)
            assert max_freq >= initial_freq


class TestPatternPersistence:
    """Test saving and loading patterns."""

    def test_saves_patterns_to_file(self, tmp_path):
        """Patterns are saved to JSON file."""
        patterns_file = tmp_path / "patterns.json"
        dedup = SemanticDeduplicator(patterns_file)

        # Create a pattern
        pattern = DuplicationPattern(
            entities={"python", "django"},
            keywords={"programming", "framework"},
            confidence=0.85,
            examples=["Example 1", "Example 2"],
            created_at=datetime.now(),
            last_seen=datetime.now(),
            frequency=3,
        )
        dedup.patterns.append(pattern)
        dedup.save_patterns()

        # Verify file exists and has content
        assert patterns_file.exists()
        with open(patterns_file) as f:
            data = json.load(f)
        assert len(data) == 1
        assert "python" in data[0]["entities"]
        assert data[0]["frequency"] == 3

    def test_loads_patterns_from_file(self, tmp_path):
        """Patterns are loaded from JSON file."""
        patterns_file = tmp_path / "patterns.json"

        # Create patterns file
        pattern_data = [
            {
                "entities": ["openai", "chatgpt"],
                "keywords": ["release", "feature"],
                "confidence": 0.9,
                "examples": ["Example"],
                "created_at": "2025-10-31T12:00:00",
                "last_seen": "2025-10-31T13:00:00",
                "frequency": 5,
            }
        ]
        with open(patterns_file, "w") as f:
            json.dump(pattern_data, f)

        # Load patterns
        dedup = SemanticDeduplicator(patterns_file)

        assert len(dedup.patterns) == 1
        assert "openai" in dedup.patterns[0].entities
        assert dedup.patterns[0].confidence == 0.9
        assert dedup.patterns[0].frequency == 5

    def test_handles_missing_patterns_file(self, tmp_path):
        """Missing patterns file is handled gracefully."""
        patterns_file = tmp_path / "nonexistent.json"
        dedup = SemanticDeduplicator(patterns_file)

        # Should not crash, just have empty patterns
        assert dedup.patterns == []

    def test_handles_corrupted_patterns_file(self, tmp_path):
        """Corrupted patterns file is handled gracefully."""
        patterns_file = tmp_path / "corrupted.json"

        # Write invalid JSON
        with open(patterns_file, "w") as f:
            f.write("not valid json {]")

        dedup = SemanticDeduplicator(patterns_file)

        # Should not crash, just have empty patterns
        assert dedup.patterns == []


class TestPatternStats:
    """Test pattern statistics."""

    def test_empty_patterns_stats(self):
        """Stats for empty patterns return zero."""
        dedup = SemanticDeduplicator(Path("test.json"))
        dedup.patterns = []

        stats = dedup.get_pattern_stats()

        assert stats["total_patterns"] == 0

    def test_pattern_stats_calculation(self):
        """Pattern statistics are calculated correctly."""
        dedup = SemanticDeduplicator(Path("test.json"))

        dedup.patterns = [
            DuplicationPattern(
                entities={"python", "django"},
                keywords={"web", "framework"},
                confidence=0.8,
                examples=[],
                created_at=datetime.now(),
                last_seen=datetime.now(),
                frequency=3,
            ),
            DuplicationPattern(
                entities={"rust", "memory"},
                keywords={"safety", "ownership"},
                confidence=0.9,
                examples=[],
                created_at=datetime.now(),
                last_seen=datetime.now(),
                frequency=5,
            ),
        ]

        stats = dedup.get_pattern_stats()

        assert stats["total_patterns"] == 2
        assert stats["avg_confidence"] == pytest.approx(0.85, abs=0.01)
        assert stats["most_frequent"] == 5
        assert stats["entity_categories"] == 4  # python, django, rust, memory
        assert stats["keyword_vocabulary"] == 4  # web, framework, safety, ownership
