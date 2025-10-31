"""Cache citation resolutions to avoid repeated API queries.

Implements a JSON-based cache with 30-day TTL (time-to-live).
Stores resolved DOIs and URLs keyed by "author_year" combination.

Cache is stored in data/citations_cache.json and automatically:
- Loads on initialization
- Saves after each new resolution
- Validates freshness (30-day TTL)
"""

import json
from datetime import datetime, timedelta
from pathlib import Path


class CitationCache:
    """JSON-based cache for citation resolutions with 30-day TTL.
    
    Prevents duplicate API calls for the same author/year combination.
    Automatically manages cache file on disk.
    """

    TTL_DAYS = 30

    def __init__(self, cache_file: str = "data/citations_cache.json") -> None:
        """Initialize the cache.
        
        Creates data directory if needed and loads existing cache.
        
        Args:
            cache_file: Path to cache file (relative to project root)
        """
        self.cache_file = Path(cache_file)
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)
        self.data: dict[str, dict] = {}
        self._load()

    def get(self, authors: str, year: int) -> dict | None:
        """Get cached resolution for author/year pair.
        
        Checks cache freshness (30-day TTL) and returns None if expired.
        
        Args:
            authors: Author string (e.g., "Smith et al.")
            year: Publication year
            
        Returns:
            Dict with doi/url/timestamp if cached and fresh, None otherwise
        """
        key = self._make_key(authors, year)

        if key in self.data:
            entry = self.data[key]
            # Check if cache entry is still fresh
            if self._is_fresh(entry["timestamp"]):
                return entry
            else:
                # Expired, remove from cache
                del self.data[key]
                self._save()

        return None

    def put(
        self, authors: str, year: int, doi: str | None, url: str | None
    ) -> None:
        """Cache a citation resolution.
        
        Stores the resolution with current timestamp for TTL tracking.
        Automatically persists to disk.
        
        Args:
            authors: Author string
            year: Publication year
            doi: Digital Object Identifier (if found)
            url: Full URL to paper (if found)
        """
        key = self._make_key(authors, year)
        self.data[key] = {
            "authors": authors,
            "year": year,
            "doi": doi,
            "url": url,
            "timestamp": datetime.now().isoformat(),
        }
        self._save()

    def clear(self) -> None:
        """Clear all cache entries and remove cache file."""
        self.data = {}
        if self.cache_file.exists():
            self.cache_file.unlink()

    def _load(self) -> None:
        """Load cache from disk.
        
        If cache file doesn't exist, initializes empty cache.
        """
        if self.cache_file.exists():
            try:
                with open(self.cache_file, encoding="utf-8") as f:
                    self.data = json.load(f)
            except (json.JSONDecodeError, IOError):
                # Corrupted or unreadable cache, start fresh
                self.data = {}

    def _save(self) -> None:
        """Persist cache to disk as formatted JSON."""
        with open(self.cache_file, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2)

    def _is_fresh(self, timestamp_str: str) -> bool:
        """Check if timestamp is within TTL window.
        
        Args:
            timestamp_str: ISO format timestamp string
            
        Returns:
            True if less than 30 days old
        """
        try:
            cached_time = datetime.fromisoformat(timestamp_str)
            age = datetime.now() - cached_time
            return age < timedelta(days=self.TTL_DAYS)
        except (ValueError, TypeError):
            # Invalid timestamp, treat as expired
            return False

    @staticmethod
    def _make_key(authors: str, year: int) -> str:
        """Generate cache key from author and year.
        
        Args:
            authors: Author string
            year: Publication year
            
        Returns:
            Cache key string
        """
        return f"{authors}_{year}"
