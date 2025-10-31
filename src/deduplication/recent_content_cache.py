"""
Recent content cache for avoiding duplicate article generation.

This module maintains a cache of recently generated articles to prevent
generating similar content. It's used BEFORE article generation to save
API costs by rejecting candidates that are too similar to recent articles.

See: docs/ADR-004-ADAPTIVE-DEDUPLICATION.md
"""

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import NamedTuple

import frontmatter
from rich.console import Console

from .post_gen_dedup import calculate_tag_overlap, calculate_text_similarity

console = Console()


@dataclass
class CachedArticle:
    """Recently generated article metadata for dedup checking."""

    title: str
    summary: str
    tags: list[str]
    date: str
    filepath: str
    generated_at: datetime


class SimilarityMatch(NamedTuple):
    """A match between a candidate and cached article."""

    cached_article: CachedArticle
    title_similarity: float
    summary_similarity: float
    tag_overlap: float
    overall_score: float


class RecentContentCache:
    """
    Cache of recently generated articles for pre-generation dedup.
    
    This prevents wasting API credits on articles that will be rejected
    as duplicates after generation.
    """

    def __init__(
        self,
        content_dir: Path,
        cache_days: int = 14,
        similarity_threshold: float = 0.70,
    ):
        """
        Initialize recent content cache.
        
        Args:
            content_dir: Directory containing generated articles
            cache_days: How many days back to consider (default: 14)
            similarity_threshold: Min similarity to flag as duplicate (default: 0.70)
        """
        self.content_dir = content_dir
        self.cache_days = cache_days
        self.similarity_threshold = similarity_threshold
        self.cache: list[CachedArticle] = []
        self._load_recent_articles()

    def _load_recent_articles(self):
        """Load articles generated in the last N days."""
        cutoff_date = datetime.now(UTC) - timedelta(days=self.cache_days)
        
        for filepath in self.content_dir.glob("*.md"):
            try:
                post = frontmatter.load(str(filepath))
                meta = post.metadata or {}
                
                # Parse generation date
                generated_at_str = meta.get("generated_at") or meta.get("date")
                if not generated_at_str:
                    continue
                
                # Handle both ISO format and simple date strings
                try:
                    if isinstance(generated_at_str, str):
                        if "T" in generated_at_str:
                            generated_at = datetime.fromisoformat(
                                generated_at_str.replace("Z", "+00:00")
                            )
                        else:
                            generated_at = datetime.fromisoformat(generated_at_str).replace(
                                tzinfo=UTC
                            )
                    else:
                        continue
                except (ValueError, AttributeError):
                    continue
                
                # Only cache recent articles
                if generated_at < cutoff_date:
                    continue
                
                article = CachedArticle(
                    title=meta.get("title", ""),
                    summary=meta.get("summary", ""),
                    tags=meta.get("tags", []),
                    date=meta.get("date", ""),
                    filepath=str(filepath),
                    generated_at=generated_at,
                )
                self.cache.append(article)
                
            except Exception as e:
                console.print(
                    f"[dim yellow]Warning: Failed to load {filepath.name}: {e}[/dim yellow]"
                )
        
        console.print(
            f"[dim]Loaded {len(self.cache)} articles from last {self.cache_days} days into cache[/dim]"
        )

    def check_similarity(
        self, title: str, summary: str, tags: list[str]
    ) -> SimilarityMatch | None:
        """
        Check if candidate is similar to any recent article.
        
        Args:
            title: Candidate article title
            summary: Candidate article summary
            tags: Candidate article tags
            
        Returns:
            SimilarityMatch if similar article found, None otherwise
        """
        best_match = None
        best_score = 0.0
        
        for cached in self.cache:
            # Calculate similarities
            title_sim = calculate_text_similarity(title, cached.title)
            summary_sim = calculate_text_similarity(summary, cached.summary)
            tag_overlap = calculate_tag_overlap(tags, cached.tags)
            
            # Overall score (weighted average)
            overall_score = (
                title_sim * 0.4 + summary_sim * 0.4 + tag_overlap * 0.2
            )
            
            # Check if this is a potential duplicate
            if overall_score >= self.similarity_threshold:
                if overall_score > best_score:
                    best_score = overall_score
                    best_match = SimilarityMatch(
                        cached_article=cached,
                        title_similarity=title_sim,
                        summary_similarity=summary_sim,
                        tag_overlap=tag_overlap,
                        overall_score=overall_score,
                    )
        
        return best_match

    def is_duplicate_candidate(
        self, title: str, summary: str, tags: list[str]
    ) -> tuple[bool, SimilarityMatch | None]:
        """
        Check if a candidate would likely be a duplicate.
        
        Args:
            title: Candidate title
            summary: Candidate summary  
            tags: Candidate tags
            
        Returns:
            Tuple of (is_duplicate, match_details)
        """
        match = self.check_similarity(title, summary, tags)
        return (match is not None, match)

    def report_match(self, match: SimilarityMatch, candidate_title: str):
        """Pretty-print a similarity match for user visibility."""
        console.print(
            f"\n[yellow]⚠ Potential duplicate detected (pre-generation)[/yellow]"
        )
        console.print(f"  Candidate: {candidate_title[:60]}...")
        console.print(
            f"  Similar to: {match.cached_article.title[:60]}... (from {match.cached_article.date})"
        )
        console.print(f"  Overall similarity: {match.overall_score:.1%}")
        console.print(
            f"  Title: {match.title_similarity:.1%}, "
            f"Summary: {match.summary_similarity:.1%}, "
            f"Tags: {match.tag_overlap:.1%}"
        )

    def get_cache_stats(self) -> dict:
        """Get statistics about the cache."""
        if not self.cache:
            return {
                "cached_articles": 0,
                "oldest_date": None,
                "newest_date": None,
                "unique_tags": 0,
            }
        
        all_tags = set()
        for article in self.cache:
            all_tags.update(article.tags)
        
        dates = [a.generated_at for a in self.cache]
        
        return {
            "cached_articles": len(self.cache),
            "oldest_date": min(dates).date().isoformat() if dates else None,
            "newest_date": max(dates).date().isoformat() if dates else None,
            "unique_tags": len(all_tags),
            "cache_days": self.cache_days,
            "threshold": self.similarity_threshold,
        }
