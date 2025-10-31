"""
Semantic deduplication with adaptive learning.
"""

import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol


class ContentProtocol(Protocol):
    """Protocol for content items that have a content attribute."""

    content: str


@dataclass
class DuplicationPattern:
    """A learned pattern for identifying duplicate content."""

    entities: set[str]
    keywords: set[str]
    confidence: float
    examples: list[str]  # Example content that matched this pattern
    created_at: datetime
    last_seen: datetime
    frequency: int = 1


class SemanticDeduplicator:
    """Learns patterns for semantic deduplication."""

    def __init__(self, patterns_file: Path = Path("data/dedup_patterns.json")):
        self.patterns_file = patterns_file
        self.patterns: list[DuplicationPattern] = []
        self.entity_extractors = self._build_entity_extractors()
        self.load_patterns()

    def _build_entity_extractors(self) -> dict[str, re.Pattern]:
        """Build regex patterns for common tech entities."""
        return {
            "companies": re.compile(
                r"\b(openai|microsoft|google|amazon|meta|apple|nvidia|intel|amd|twitter|reddit|github|stackoverflow|docker|kubernetes)\b",
                re.IGNORECASE,
            ),
            "frameworks": re.compile(
                r"\b(react|vue|angular|django|flask|fastapi|tensorflow|pytorch|scikit-learn|pandas|numpy)\b",
                re.IGNORECASE,
            ),
            "languages": re.compile(
                r"\b(python|javascript|typescript|java|c\+\+|rust|go|kotlin|swift|ruby|php)\b",
                re.IGNORECASE,
            ),
            "organizations": re.compile(
                r"\b(python software foundation|psf|mozilla|apache|linux foundation|cncf|w3c)\b",
                re.IGNORECASE,
            ),
            "products": re.compile(
                r"\b(chatgpt|claude|gemini|copilot|kubernetes|docker|vscode|jupyter|anaconda)\b",
                re.IGNORECASE,
            ),
        }

    def extract_entities(self, content: str) -> dict[str, set[str]]:
        """Extract entities from content."""
        entities = {}
        for category, pattern in self.entity_extractors.items():
            matches = pattern.findall(content)
            entities[category] = {match.lower() for match in matches}
        return entities

    def extract_keywords(self, content: str, min_length: int = 4) -> set[str]:
        """Extract significant keywords from content."""
        # Remove URLs, mentions, hashtags
        clean_content = re.sub(r"http\S+|@\w+|#\w+", "", content)

        # Extract words
        words = re.findall(
            r"\b[a-zA-Z]{" + str(min_length) + r",}\b", clean_content.lower()
        )

        # Filter out common words
        stop_words = {
            "this",
            "that",
            "with",
            "have",
            "will",
            "from",
            "they",
            "been",
            "were",
            "said",
            "each",
            "which",
            "their",
            "time",
            "more",
            "very",
            "what",
            "know",
            "just",
            "first",
            "into",
            "over",
            "think",
            "also",
            "your",
            "work",
            "life",
            "only",
            "can",
            "still",
            "should",
            "after",
            "being",
            "now",
            "made",
            "before",
            "here",
            "through",
            "when",
            "where",
        }
        return {word for word in words if word not in stop_words}

    def calculate_content_similarity(self, content1: str, content2: str) -> float:
        """Calculate semantic similarity between two pieces of content."""
        # Extract entities and keywords for both
        entities1 = self.extract_entities(content1)
        entities2 = self.extract_entities(content2)
        keywords1 = self.extract_keywords(content1)
        keywords2 = self.extract_keywords(content2)

        # Calculate entity overlap
        entity_scores = []
        for category in entities1:
            if entities1[category] and entities2[category]:
                overlap = len(entities1[category] & entities2[category])
                total = len(entities1[category] | entities2[category])
                entity_scores.append(overlap / total)

        entity_similarity = (
            sum(entity_scores) / len(entity_scores) if entity_scores else 0
        )

        # Calculate keyword overlap
        if keywords1 and keywords2:
            keyword_overlap = len(keywords1 & keywords2)
            keyword_total = len(keywords1 | keywords2)
            keyword_similarity = keyword_overlap / keyword_total
        else:
            keyword_similarity = 0

        # Weighted combination
        return (entity_similarity * 0.7) + (keyword_similarity * 0.3)

    def find_duplicates(
        self, items: list[ContentProtocol], threshold: float = 0.6
    ) -> list[list[ContentProtocol]]:
        """Find groups of duplicate items using learned patterns and similarity."""
        duplicate_groups = []
        processed = set()

        for i, item1 in enumerate(items):
            if i in processed:
                continue

            current_group = [item1]
            processed.add(i)

            for j, item2 in enumerate(items[i + 1 :], i + 1):
                if j in processed:
                    continue

                similarity = self.calculate_content_similarity(
                    item1.content, item2.content
                )

                if similarity >= threshold:
                    current_group.append(item2)
                    processed.add(j)

            if len(current_group) > 1:
                duplicate_groups.append(current_group)
                # Learn from this duplication pattern
                self._learn_from_duplicates(current_group)

        return duplicate_groups

    def _learn_from_duplicates(self, duplicate_group: list[ContentProtocol]):
        """Learn patterns from confirmed duplicates."""
        # Extract common entities and keywords
        all_entities = defaultdict(set)
        all_keywords = set()

        for item in duplicate_group:
            entities = self.extract_entities(item.content)
            keywords = self.extract_keywords(item.content)

            for category, entity_set in entities.items():
                all_entities[category].update(entity_set)
            all_keywords.update(keywords)

        # Find entities common to all items
        common_entities = set()
        for category, _entity_set in all_entities.items():
            # Entities that appear in most items
            entity_counts = Counter()
            for item in duplicate_group:
                item_entities = self.extract_entities(item.content)
                entity_counts.update(item_entities.get(category, set()))

            # Consider entities that appear in at least half the items
            min_appearances = len(duplicate_group) // 2 + 1
            for entity, count in entity_counts.items():
                if count >= min_appearances:
                    common_entities.add(entity)

        # Find keywords common to most items
        common_keywords = set()
        keyword_counts = Counter()
        for item in duplicate_group:
            keywords = self.extract_keywords(item.content)
            keyword_counts.update(keywords)

        min_appearances = len(duplicate_group) // 2 + 1
        for keyword, count in keyword_counts.items():
            if count >= min_appearances:
                common_keywords.add(keyword)

        # Create or update pattern
        if common_entities or common_keywords:
            pattern = DuplicationPattern(
                entities=common_entities,
                keywords=common_keywords,
                confidence=0.8,  # Start with high confidence for learned patterns
                examples=[item.content[:100] for item in duplicate_group[:3]],
                created_at=datetime.now(),
                last_seen=datetime.now(),
            )

            # Check if similar pattern exists
            existing_pattern = self._find_similar_pattern(pattern)
            if existing_pattern:
                # Update existing pattern
                existing_pattern.entities.update(pattern.entities)
                existing_pattern.keywords.update(pattern.keywords)
                existing_pattern.frequency += 1
                existing_pattern.last_seen = datetime.now()
                existing_pattern.confidence = min(
                    0.95, existing_pattern.confidence + 0.05
                )
            else:
                # Add new pattern
                self.patterns.append(pattern)

        self.save_patterns()

    def _find_similar_pattern(
        self, new_pattern: DuplicationPattern
    ) -> DuplicationPattern | None:
        """Find existing pattern similar to the new one."""
        for pattern in self.patterns:
            entity_overlap = len(pattern.entities & new_pattern.entities)
            keyword_overlap = len(pattern.keywords & new_pattern.keywords)

            if entity_overlap >= 2 or (entity_overlap >= 1 and keyword_overlap >= 3):
                return pattern
        return None

    def save_patterns(self):
        """Save learned patterns to file."""
        self.patterns_file.parent.mkdir(exist_ok=True)

        patterns_data = []
        for pattern in self.patterns:
            patterns_data.append(
                {
                    "entities": list(pattern.entities),
                    "keywords": list(pattern.keywords),
                    "confidence": pattern.confidence,
                    "examples": pattern.examples,
                    "created_at": pattern.created_at.isoformat(),
                    "last_seen": pattern.last_seen.isoformat(),
                    "frequency": pattern.frequency,
                }
            )

        with open(self.patterns_file, "w") as f:
            json.dump(patterns_data, f, indent=2)

    def load_patterns(self):
        """Load learned patterns from file."""
        if not self.patterns_file.exists():
            return

        try:
            with open(self.patterns_file) as f:
                patterns_data = json.load(f)

            self.patterns = []
            for data in patterns_data:
                pattern = DuplicationPattern(
                    entities=set(data["entities"]),
                    keywords=set(data["keywords"]),
                    confidence=data["confidence"],
                    examples=data["examples"],
                    created_at=datetime.fromisoformat(data["created_at"]),
                    last_seen=datetime.fromisoformat(data["last_seen"]),
                    frequency=data.get("frequency", 1),
                )
                self.patterns.append(pattern)

        except Exception as e:
            print(f"Error loading deduplication patterns: {e}")
            self.patterns = []

    def get_pattern_stats(self) -> dict:
        """Get statistics about learned patterns."""
        if not self.patterns:
            return {"total_patterns": 0}

        return {
            "total_patterns": len(self.patterns),
            "avg_confidence": sum(p.confidence for p in self.patterns)
            / len(self.patterns),
            "most_frequent": max(self.patterns, key=lambda p: p.frequency).frequency,
            "entity_categories": len(set().union(*[p.entities for p in self.patterns])),
            "keyword_vocabulary": len(
                set().union(*[p.keywords for p in self.patterns])
            ),
        }
