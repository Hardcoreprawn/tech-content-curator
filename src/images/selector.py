"""Multi-source image selector with LLM-generated queries.

Smart image selection strategy:
1. Try Wikimedia Commons (public domain) → FREE
2. Try Unsplash (stock photos) → FREE
3. Try Pexels (stock photos) → FREE
4. Fall back to DALL-E 3 (AI) → $0.020

All search queries are generated via gpt-3.5-turbo for better context-aware results.
Cost: ~$0.0005 per article for LLM query generation.
"""

from ..utils.logging import get_logger

logger = get_logger(__name__)


import json
from dataclasses import dataclass

import frontmatter
import httpx
from openai import OpenAI
from rich.console import Console

from ..config import get_content_dir
from ..models import PipelineConfig

console = Console()


@dataclass
class CoverImage:
    """Represents a selected cover image with metadata."""

    url: str
    alt_text: str
    source: str  # "wikimedia", "unsplash", "pexels", "dalle-3"
    cost: float
    quality_score: float  # 0-1, how confident we are in the match


class CoverImageSelector:
    """Select best image from free sources, fall back to AI."""

    def __init__(self, openai_client: OpenAI, config: PipelineConfig):
        """Initialize selector with OpenAI client and configuration.

        Args:
            openai_client: OpenAI API client
            config: Pipeline configuration with API keys and timeouts
        """
        self.client = openai_client
        self.config = config
        self._recently_used_images = self._load_recent_images()

    def _load_recent_images(self, days_back: int = 3) -> set[str]:
        """Load image URLs from recent articles to avoid duplicates.

        Args:
            days_back: Number of days to look back

        Returns:
            Set of image URLs used in recent articles
        """
        from datetime import datetime, timedelta

        recent_images = set()
        try:
            content_dir = get_content_dir()
            cutoff_date = datetime.now() - timedelta(days=days_back)

            for article_file in content_dir.glob("*.md"):
                # Quick date check from filename (YYYY-MM-DD format)
                try:
                    date_str = article_file.name[:10]
                    article_date = datetime.strptime(date_str, "%Y-%m-%d")
                    if article_date < cutoff_date:
                        continue

                    # Load frontmatter and extract image
                    with open(article_file, encoding="utf-8") as f:
                        post = frontmatter.load(f)
                        if (
                            "cover" in post.metadata
                            and isinstance(post.metadata["cover"], dict)
                            and "image" in post.metadata["cover"]
                        ):
                            image_url = post.metadata["cover"]["image"]
                            if image_url:
                                # Extract the photo ID to handle different query parameters
                                if (
                                    "unsplash.com" in image_url
                                    and "photo-" in image_url
                                ):
                                    photo_id = image_url.split("photo-")[1].split("?")[
                                        0
                                    ]
                                    recent_images.add(f"unsplash:{photo_id}")
                                elif "pexels.com" in image_url:
                                    photo_id = (
                                        image_url.split("/photos/")[1].split("-")[0]
                                        if "/photos/" in image_url
                                        else None
                                    )
                                    if photo_id:
                                        recent_images.add(f"pexels:{photo_id}")
                                else:
                                    recent_images.add(image_url)
                except (ValueError, IndexError):
                    continue

        except Exception as e:
            console.print(f"[dim]Note: Could not load recent images: {e}[/dim]")

        if recent_images:
            console.print(
                f"[dim]Excluding {len(recent_images)} recently used images[/dim]"
            )

        return recent_images

    def select(self, title: str, topics: list[str]) -> CoverImage:
        """Select best image from free sources, fallback to AI.

        Strategy:
        1. Generate search queries via LLM (better than deterministic rules)
        2. Try free sources in order: Unsplash → Pexels
        3. Fall back to DALL-E 3 if all free sources fail or score too low

        Args:
            title: Article title
            topics: List of topic/tag keywords

        Returns:
            CoverImage with URL, source, cost, and quality score
        """
        logger.debug(f"Selecting cover image for article: {title}")
        console.print("[blue]🖼  Selecting cover image...[/blue]")

        # Step 1: Generate search queries via LLM
        queries = self._generate_search_queries(title, topics)
        logger.debug(f"Generated search queries: {queries}")
        console.print(f"[dim]Generated search queries: {queries}[/dim]")

        # Tier 1: Try Unsplash (free stock)
        if self.config.unsplash_api_key:
            result = self._search_unsplash(queries.get("unsplash", title))
            if result and result.quality_score >= 0.70:
                logger.info(f"Found Unsplash image (score: {result.quality_score})")
                console.print(
                    f"[green]✓ Found Unsplash image (score: {result.quality_score})[/green]"
                )
                return result

        # Tier 2: Try Pexels (free stock)
        if self.config.pexels_api_key:
            result = self._search_pexels(queries.get("pexels", title))
            if result and result.quality_score >= 0.65:
                logger.info(f"Found Pexels image (score: {result.quality_score})")
                console.print(
                    f"[green]✓ Found Pexels image (score: {result.quality_score})[/green]"
                )
                return result

        # Tier 3: Generate AI image (fallback)
        logger.warning("Free image sources unavailable, falling back to AI generation")
        console.print(
            "[yellow]⚠  Free sources unavailable, generating AI image...[/yellow]"
        )
        return self._generate_ai_image(
            queries.get("dalle", f"Professional article illustration for: {title}")
        )

    def _detect_vintage_tech_context(self, title: str, topics: list[str]) -> bool:
        """Detect if article is about vintage/historical technology.

        Args:
            title: Article title
            topics: List of topics

        Returns:
            True if vintage/historical tech context detected
        """
        vintage_keywords = {
            "unix",
            "v4",
            "v7",
            "vintage",
            "retro",
            "legacy",
            "historical",
            "tape",
            "punch card",
            "mainframe",
            "minicomputer",
            "bbs",
            "atari",
            "commodore",
            "amiga",
            "nes",
            "snes",
            "genesis",
            "floppy",
            "cassette",
            "reel-to-reel",
            "vax",
            "pdp",
            "1970s",
            "1980s",
            "1990s",
            "early computing",
            "computer history",
            "museum",
            "preservation",
            "archaeology",
            "recovery",
            "rediscovering",
        }

        text = f"{title} {' '.join(topics)}".lower()
        return any(keyword in text for keyword in vintage_keywords)

    def _generate_search_queries(self, title: str, topics: list[str]) -> dict[str, str]:
        """Use gpt-3.5-turbo to generate effective search queries.

        Why LLM? Deterministic rules produce generic, poor queries.
        LLM understands context and generates natural searches.
        Cost: ~$0.0005 per article

        Args:
            title: Article title
            topics: List of topics

        Returns:
            Dict with keys: unsplash, pexels, dalle
        """
        is_vintage = self._detect_vintage_tech_context(title, topics)
        vintage_hint = ""
        if is_vintage:
            vintage_hint = "\n\n**VINTAGE/HISTORICAL TECH DETECTED**: Use generic vintage computing imagery (old computer rooms, retro hardware, vintage tech equipment). Specific old models won't be on stock sites!"

        prompt = f"""Generate SPECIFIC image search queries for this article. Return ONLY valid JSON.

Title: {title}
Topics: {", ".join(topics) if topics else "general"}{vintage_hint}

Return JSON with these keys:
- "unsplash": query for Unsplash (high-quality natural photos, very specific)
- "pexels": query for Pexels (generic focus, very specific)
- "dalle": detailed prompt for DALL-E if no stock photo found

CRITICAL RULES:
1. For vintage/historical tech (Unix, old computers, tape drives, retro gaming, etc.), use GENERIC MODERN EQUIVALENTS
   - "unix v4 tape recovery" → "vintage computer data center" or "old mainframe computer"
   - "NES gaming history" → "retro game console" or "vintage video game"
   - "punch cards" → "vintage computer equipment" or "old data storage"
   - "legacy systems" → "server room equipment" or "computer hardware"

2. Stock photo sites rarely have specific historical tech items. Use broader concepts that capture the FEELING/ERA.

3. For modern tech, be SPECIFIC:
   - "quantum computing" → "quantum computer chip"
   - "AI development" → "machine learning code screen"

Each query should be 2-5 words and capture the subject matter realistically available on stock photo sites."""

        try:
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=300,
            )

            content = response.choices[0].message.content
            if content is None:
                raise ValueError("OpenAI returned empty content")
            return json.loads(content)
        except (json.JSONDecodeError, AttributeError, Exception) as e:
            console.print(
                f"[yellow]⚠  Query generation failed: {e}, using title as fallback[/yellow]"
            )
            # Fallback if parsing fails
            return {
                "unsplash": title,
                "pexels": title,
                "dalle": f"Professional article illustration for: {title}",
            }

    def _search_unsplash(self, query: str) -> CoverImage | None:
        """Search Unsplash for free stock photos, skipping recently used.

        Args:
            query: Search query

        Returns:
            CoverImage if found, None otherwise
        """
        logger.debug(f"Searching Unsplash for: {query}")
        try:
            response = httpx.get(
                "https://api.unsplash.com/search/photos",
                params={
                    "query": query,
                    "per_page": 5,  # Get multiple results to handle recent exclusions
                    "orientation": "landscape",
                },
                headers={"Authorization": f"Client-ID {self.config.unsplash_api_key}"},
                timeout=self.config.image_source_timeout,
            )
            response.raise_for_status()
            data = response.json()

            if data.get("results"):
                # Try each result until we find one that's not recently used
                for result in data["results"]:
                    photo_id = result["id"]
                    if f"unsplash:{photo_id}" not in self._recently_used_images:
                        return CoverImage(
                            url=result["urls"]["regular"],
                            alt_text=result.get("description", query) or query,
                            source="unsplash",
                            cost=0.0,
                            quality_score=0.80,  # Unsplash is high quality
                        )
                console.print("[dim]All Unsplash results were recently used[/dim]")
        except Exception as e:
            console.print(f"[dim]Unsplash search failed: {e}[/dim]")

        return None

    def _search_pexels(self, query: str) -> CoverImage | None:
        """Search Pexels for free stock photos, skipping recently used.

        Args:
            query: Search query

        Returns:
            CoverImage if found, None otherwise
        """
        logger.debug(f"Searching Pexels for: {query}")
        try:
            response = httpx.get(
                "https://api.pexels.com/v1/search",
                params={
                    "query": query,
                    "per_page": 5,  # Get multiple results to handle recent exclusions
                    "orientation": "landscape",
                },
                headers={"Authorization": self.config.pexels_api_key},
                timeout=self.config.image_source_timeout,
            )
            response.raise_for_status()
            data = response.json()

            if data.get("photos"):
                # Try each result until we find one that's not recently used
                for result in data["photos"]:
                    photo_id = str(result["id"])
                    if f"pexels:{photo_id}" not in self._recently_used_images:
                        return CoverImage(
                            url=result["src"]["large"],
                            alt_text=result.get("alt", query) or query,
                            source="pexels",
                            cost=0.0,
                            quality_score=0.75,
                        )
                console.print("[dim]All Pexels results were recently used[/dim]")
        except Exception as e:
            console.print(f"[dim]Pexels search failed: {e}[/dim]")

        return None

    def _generate_ai_image(self, prompt: str) -> CoverImage:
        """Generate image via DALL-E 3 (last resort).

        Args:
            prompt: Detailed prompt for DALL-E

        Returns:
            CoverImage with generated image URL
        """
        try:
            response = self.client.images.generate(
                model="dall-e-3",
                prompt=prompt,
                size="1024x1024",
                quality="standard",
                n=1,
            )

            if not response.data or not response.data[0].url:
                raise ValueError("DALL-E returned no image data")

            return CoverImage(
                url=response.data[0].url,
                alt_text="Article hero image",
                source="dalle-3",
                cost=0.020,
                quality_score=0.85,
            )
        except Exception as e:
            console.print(f"[red]✗ DALL-E generation failed: {e}[/red]")
            raise
