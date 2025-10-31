"""Multi-source image selection package.

Provides smart image selection with LLM-generated queries and graceful fallback:
1. Wikimedia Commons (public domain)
2. Unsplash (free stock photos)
3. Pexels (free stock photos)
4. DALL-E 3 (AI fallback)
"""

from .selector import CoverImage, CoverImageSelector

__all__ = ["CoverImage", "CoverImageSelector"]
