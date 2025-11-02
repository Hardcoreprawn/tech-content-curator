"""
Adaptive feedback system for improving deduplication.

This module creates a feedback loop:
1. Post-generation duplicates are detected
2. Patterns are extracted from those duplicates
3. Patterns are fed to pre-generation filters
4. Future similar candidates are rejected earlier (saving costs)

See: docs/ADR-004-ADAPTIVE-DEDUPLICATION.md
"""

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from rich.console import Console

console = Console()


@dataclass
class DuplicatePattern:
    """A learned pattern from detected duplicates."""

    topic_keywords: set[str]  # Common keywords in duplicate pairs
    common_tags: set[str]  # Tags that appear in both articles
    title_patterns: list[str]  # Common title phrases
    detected_count: int  # How many times we've seen this pattern
    first_seen: str  # ISO timestamp
    last_seen: str  # ISO timestamp
    example_titles: list[str]  # Example titles that matched
    avg_similarity: float  # Average similarity score of matches


class AdaptiveDedupFeedback:
    """
    Learn from post-generation duplicates to improve pre-generation filtering.

    This is the "learning" component that reduces wasted API costs over time.
    """

    def __init__(self, patterns_file: Path = Path("data/adaptive_dedup_patterns.json")):
        """
        Initialize adaptive feedback system.

        Args:
            patterns_file: Path to patterns JSON file
        """
        self.patterns_file = patterns_file
        self.patterns_file.parent.mkdir(parents=True, exist_ok=True)
        self.patterns: list[DuplicatePattern] = []
        self.load()

    def load(self):
        """Load learned patterns from disk."""
        if self.patterns_file.exists():
            try:
                with open(self.patterns_file, encoding="utf-8") as f:
                    data = json.load(f)
                    self.patterns = []
                    for item in data:
                        # Convert sets back from lists
                        pattern = DuplicatePattern(
                            topic_keywords=set(item["topic_keywords"]),
                            common_tags=set(item["common_tags"]),
                            title_patterns=item["title_patterns"],
                            detected_count=item["detected_count"],
                            first_seen=item["first_seen"],
                            last_seen=item["last_seen"],
                            example_titles=item["example_titles"],
                            avg_similarity=item["avg_similarity"],
                        )
                        self.patterns.append(pattern)
                console.print(
                    f"[dim]Loaded {len(self.patterns)} learned dedup patterns[/dim]"
                )
            except Exception as e:
                console.print(f"[yellow]Warning: Could not load patterns: {e}[/yellow]")
                self.patterns = []

    def save(self):
        """Save learned patterns to disk."""
        try:
            # Convert sets to lists for JSON serialization
            data = []
            for pattern in self.patterns:
                pattern_dict = asdict(pattern)
                pattern_dict["topic_keywords"] = list(pattern.topic_keywords)
                pattern_dict["common_tags"] = list(pattern.common_tags)
                data.append(pattern_dict)

            with open(self.patterns_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            console.print(f"[red]Error saving patterns: {e}[/red]")

    def learn_from_duplicate(
        self,
        article1_title: str,
        article1_tags: list[str],
        article2_title: str,
        article2_tags: list[str],
        similarity_score: float,
    ):
        """
        Learn from a detected duplicate pair.

        Extracts patterns and updates the knowledge base.

        Args:
            article1_title: Title of first article
            article1_tags: Tags of first article
            article2_title: Title of second article
            article2_tags: Tags of second article
            similarity_score: How similar they were (0.0-1.0)
        """
        # Extract common patterns
        common_tags = set(article1_tags) & set(article2_tags)

        # Extract common keywords from titles (simple word overlap)
        words1 = set(article1_title.lower().split())
        words2 = set(article2_title.lower().split())
        common_keywords = words1 & words2

        # Remove common stopwords
        stopwords = {
            "the",
            "a",
            "an",
            "and",
            "or",
            "but",
            "in",
            "on",
            "at",
            "to",
            "for",
            "of",
            "with",
            "by",
            "from",
            "as",
            "is",
            "was",
            "are",
            "be",
        }
        common_keywords = {
            w for w in common_keywords if w not in stopwords and len(w) > 3
        }

        # Check if we already have a similar pattern
        existing_pattern = None
        for pattern in self.patterns:
            # Match if significant overlap in tags or keywords
            tag_overlap = len(common_tags & pattern.common_tags)
            keyword_overlap = len(common_keywords & pattern.topic_keywords)

            if tag_overlap >= 2 or keyword_overlap >= 2:
                existing_pattern = pattern
                break

        if existing_pattern:
            # Update existing pattern
            existing_pattern.detected_count += 1
            existing_pattern.last_seen = datetime.now(UTC).isoformat()
            existing_pattern.topic_keywords.update(common_keywords)
            existing_pattern.common_tags.update(common_tags)
            existing_pattern.example_titles.append(article1_title)
            existing_pattern.example_titles.append(article2_title)
            # Keep only last 5 examples
            existing_pattern.example_titles = existing_pattern.example_titles[-5:]
            # Update avg similarity
            n = existing_pattern.detected_count
            existing_pattern.avg_similarity = (
                existing_pattern.avg_similarity * (n - 1) + similarity_score
            ) / n
        else:
            # Create new pattern
            new_pattern = DuplicatePattern(
                topic_keywords=common_keywords,
                common_tags=common_tags,
                title_patterns=[],  # Could add phrase extraction here
                detected_count=1,
                first_seen=datetime.now(UTC).isoformat(),
                last_seen=datetime.now(UTC).isoformat(),
                example_titles=[article1_title, article2_title],
                avg_similarity=similarity_score,
            )
            self.patterns.append(new_pattern)

        self.save()

    def check_against_patterns(
        self, title: str, tags: list[str], threshold: float = 0.6
    ) -> tuple[bool, DuplicatePattern | None]:
        """
        Check if a candidate matches learned duplicate patterns.

        This is used PRE-GENERATION to reject likely duplicates early.

        Args:
            title: Candidate article title
            tags: Candidate article tags
            threshold: Minimum match score to flag (default: 0.6)

        Returns:
            Tuple of (is_likely_duplicate, matching_pattern)
        """
        title_words = set(title.lower().split())
        title_words = {w for w in title_words if len(w) > 3}  # Filter short words

        best_match = None
        best_score = 0.0

        for pattern in self.patterns:
            # Calculate match score
            keyword_match = len(title_words & pattern.topic_keywords) / max(
                len(pattern.topic_keywords), 1
            )
            tag_match = len(set(tags) & pattern.common_tags) / max(
                len(pattern.common_tags), 1
            )

            # Weight by how many times we've seen this pattern
            confidence = min(pattern.detected_count / 3.0, 1.0)  # Cap at 3

            # Overall match score
            match_score = (keyword_match * 0.5 + tag_match * 0.5) * confidence

            if match_score >= threshold and match_score > best_score:
                best_score = match_score
                best_match = pattern

        return (best_match is not None, best_match)

    def get_pattern_stats(self) -> dict:
        """Get statistics about learned patterns."""
        if not self.patterns:
            return {
                "total_patterns": 0,
                "total_detections": 0,
                "avg_similarity": 0.0,
                "most_common_tags": [],
                "most_common_keywords": [],
            }

        return {
            "total_patterns": len(self.patterns),
            "total_detections": sum(p.detected_count for p in self.patterns),
            "avg_similarity": sum(p.avg_similarity for p in self.patterns)
            / len(self.patterns),
            "most_common_tags": self._get_most_common_tags(top_n=5),
            "most_common_keywords": self._get_most_common_keywords(top_n=5),
        }

    def _get_most_common_tags(self, top_n: int = 5) -> list[tuple[str, int]]:
        """Get most frequently appearing tags in duplicate patterns."""
        from collections import Counter

        all_tags = []
        for pattern in self.patterns:
            all_tags.extend(list(pattern.common_tags) * pattern.detected_count)

        return Counter(all_tags).most_common(top_n)

    def _get_most_common_keywords(self, top_n: int = 5) -> list[tuple[str, int]]:
        """Get most frequently appearing keywords in duplicate patterns."""
        from collections import Counter

        all_keywords = []
        for pattern in self.patterns:
            all_keywords.extend(list(pattern.topic_keywords) * pattern.detected_count)

        return Counter(all_keywords).most_common(top_n)

    def print_stats(self):
        """Print formatted statistics about learned patterns."""
        stats = self.get_pattern_stats()

        console.print("\n[bold cyan]🧠 Adaptive Dedup Learning Stats[/bold cyan]\n")
        console.print(f"Total patterns learned: {stats['total_patterns']}")
        console.print(f"Total duplicates detected: {stats['total_detections']}")
        console.print(f"Average similarity: {stats['avg_similarity']:.1%}")

        if stats["most_common_tags"]:
            console.print("\n[bold]Most common duplicate tags:[/bold]")
            for tag, count in stats["most_common_tags"]:
                console.print(f"  • {tag}: {count} occurrences")

        if stats["most_common_keywords"]:
            console.print("\n[bold]Most common keywords in duplicates:[/bold]")
            for keyword, count in stats["most_common_keywords"]:
                console.print(f"  • {keyword}: {count} occurrences")
