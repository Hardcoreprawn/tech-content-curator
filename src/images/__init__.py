"""Image management package.

This package handles all image-related functionality for articles:
- Cover image selection with multi-source fallback
- Image catalog management
- Image library for reusable images
- Social preview image generation

Components:
- selector: Smart image selection with LLM-generated queries
- catalog: Image metadata and tracking (will move from image_catalog.py)
- library: Reusable image library management (will move from image_library.py)
- cover_image: Cover image utilities (will move from images.py)

Image Source Priority:
1. Wikimedia Commons (public domain, high quality)
2. Unsplash (free stock photos, modern aesthetic)
3. Pexels (free stock photos, diverse content)
4. DALL-E 3 (AI-generated fallback, always available)

Usage:
    from src.images import CoverImageSelector
    
    selector = CoverImageSelector()
    image = selector.select_cover_image(
        title="AI Breakthrough",
        topics=["AI", "Machine Learning"]
    )

Design Principles:
- Always succeed (fallback to DALL-E if needed)
- Smart query generation for better results
- Cache results to avoid duplicate API calls
- Track costs for generated images
- Validate image URLs before saving
"""

from .selector import CoverImage, CoverImageSelector

__all__ = ["CoverImage", "CoverImageSelector"]
