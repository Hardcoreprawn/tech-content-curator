"""Utility functions package.

This package provides shared utility functions used across the application.

Components:
- url_tools: URL normalization, validation, and parsing
- rate_limit: Rate limiting for API calls
- text_processing: Text cleaning and normalization (future)
- date_utils: Date parsing and formatting (future)

Usage:
    from src.utils import normalize_url, RateLimiter

    clean_url = normalize_url("https://example.com/path?utm=123")
    limiter = RateLimiter(requests_per_second=2)
    await limiter.acquire()

Design Principles:
- Pure functions where possible
- No side effects
- Well tested
- Clear documentation
- Reusable across modules
"""

from .rate_limit import RateLimiter
from .url_tools import normalize_url

__all__ = ["normalize_url", "RateLimiter"]
