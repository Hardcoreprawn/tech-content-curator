"""Multi-source image selector with LLM-generated queries.

Smart image selection strategy:
1. Try Wikimedia Commons (public domain) → FREE
2. Try Unsplash (stock photos) → FREE
3. Try Pexels (stock photos) → FREE
4. Fall back to DALL-E 3 (AI) → $0.020

All search queries are generated via gpt-3.5-turbo for better context-aware results.
Cost: ~$0.0005 per article for LLM query generation.
"""

import json
from dataclasses import dataclass

import httpx
from openai import OpenAI
from rich.console import Console

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
        console.print("[blue]🖼  Selecting cover image...[/blue]")

        # Step 1: Generate search queries via LLM
        queries = self._generate_search_queries(title, topics)
        console.print(f"[dim]Generated search queries: {queries}[/dim]")

        # Tier 1: Try Unsplash (free stock)
        if self.config.unsplash_api_key:
            result = self._search_unsplash(queries.get("unsplash", title))
            if result and result.quality_score >= 0.70:
                console.print(
                    f"[green]✓ Found Unsplash image (score: {result.quality_score})[/green]"
                )
                return result

        # Tier 2: Try Pexels (free stock)
        if self.config.pexels_api_key:
            result = self._search_pexels(queries.get("pexels", title))
            if result and result.quality_score >= 0.65:
                console.print(
                    f"[green]✓ Found Pexels image (score: {result.quality_score})[/green]"
                )
                return result

        # Tier 3: Generate AI image (fallback)
        console.print(
            "[yellow]⚠  Free sources unavailable, generating AI image...[/yellow]"
        )
        return self._generate_ai_image(
            queries.get("dalle", f"Professional article illustration for: {title}")
        )

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
        prompt = f"""Generate SPECIFIC image search queries for this article. Return ONLY valid JSON.

Title: {title}
Topics: {", ".join(topics) if topics else "general"}

Return JSON with these keys:
- "unsplash": query for Unsplash (high-quality natural photos, very specific)
- "pexels": query for Pexels (generic focus, very specific)
- "dalle": detailed prompt for DALL-E if no stock photo found

IMPORTANT: Make queries as SPECIFIC as possible to the article topic.
For "Bird Flight" topics, search for "owl in flight" not just "bird"
For "quantum computing", search for "quantum computer chip" not just "technology"
Each query should be 2-5 words and capture the SPECIFIC subject matter."""

        try:
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=300,
            )

            content = response.choices[0].message.content
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
        """Search Unsplash for free stock photos.

        Args:
            query: Search query

        Returns:
            CoverImage if found, None otherwise
        """
        try:
            response = httpx.get(
                "https://api.unsplash.com/search/photos",
                params={
                    "query": query,
                    "per_page": 1,
                    "orientation": "landscape",
                },
                headers={"Authorization": f"Client-ID {self.config.unsplash_api_key}"},
                timeout=self.config.image_source_timeout,
            )
            response.raise_for_status()
            data = response.json()

            if data.get("results"):
                result = data["results"][0]
                return CoverImage(
                    url=result["urls"]["regular"],
                    alt_text=result.get("description", query) or query,
                    source="unsplash",
                    cost=0.0,
                    quality_score=0.80,  # Unsplash is high quality
                )
        except Exception as e:
            console.print(f"[dim]Unsplash search failed: {e}[/dim]")

        return None

    def _search_pexels(self, query: str) -> CoverImage | None:
        """Search Pexels for free stock photos.

        Args:
            query: Search query

        Returns:
            CoverImage if found, None otherwise
        """
        try:
            response = httpx.get(
                "https://api.pexels.com/v1/search",
                params={
                    "query": query,
                    "per_page": 1,
                    "orientation": "landscape",
                },
                headers={"Authorization": self.config.pexels_api_key},
                timeout=self.config.image_source_timeout,
            )
            response.raise_for_status()
            data = response.json()

            if data.get("photos"):
                result = data["photos"][0]
                return CoverImage(
                    url=result["src"]["large"],
                    alt_text=result.get("alt", query) or query,
                    source="pexels",
                    cost=0.0,
                    quality_score=0.75,
                )
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
