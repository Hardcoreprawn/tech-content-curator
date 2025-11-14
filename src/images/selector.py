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
from ..utils.openai_client import create_chat_completion

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

    def _detect_vintage_tech_context(self, title: str, topics: list[str]) -> bool:
        """Detect if article is about vintage/historical technology.

        Args:
            title: Article title
            topics: List of topic keywords

        Returns:
            True if vintage tech context detected, False otherwise
        """
        vintage_keywords = {
            "vintage", "retro", "historical", "legacy", "old", "classic",
            "1970s", "1980s", "1990s", "early computing", "punch card",
            "mainframe", "commodore", "atari", "ibm pc", "apple ii",
            "unix", "dos", "analog", "mechanical", "obsolete"
        }

        combined_text = (title + " " + " ".join(topics)).lower()
        return any(keyword in combined_text for keyword in vintage_keywords)

    def _extract_key_entities(self, title: str, content: str, topics: list[str]) -> list[str]:
        """Extract key entities from article title and content.

        Args:
            title: Article title
            content: Article content
            topics: List of topic keywords

        Returns:
            List of key entities
        """
        entities = set(topics) if topics else set()

        # Add title words (except common stop words)
        stop_words = {"the", "a", "an", "and", "or", "in", "on", "at", "to", "for", "of", "is", "are", "was", "were"}
        title_words = [word.lower() for word in title.split() if word.lower() not in stop_words and len(word) > 3]
        entities.update(title_words)

        # Extract key terms from content (simple heuristic: capitalized words)
        if content:
            import re
            # Find capitalized sequences (potential proper nouns)
            capitalized = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', content)
            entities.update([e.lower() for e in capitalized[:10]])  # Limit to top 10

        return list(entities)[:15]  # Return top 15 entities

    def select(self, title: str, topics: list[str], content: str = "") -> CoverImage:
        """Select best image from free sources, fallback to AI.

        Strategy:
        1. Generate content-aware search queries via LLM
        2. Try free sources: Unsplash → Pexels
        3. Validate relevance with AI, retry with refined query if needed
        4. Fall back to DALL-E 3 if all attempts fail

        Args:
            title: Article title
            topics: List of topic/tag keywords
            content: Article content (first ~500 words used for context)

        Returns:
            CoverImage with URL, source, cost, and quality score
        """
        logger.debug(f"Selecting cover image for article: {title}")
        console.print("[blue]🖼  Selecting cover image...[/blue]")

        max_attempts = 3
        tried_queries = []

        for attempt in range(1, max_attempts + 1):
            # Generate search queries with content context
            queries = self._generate_search_queries(
                title, topics, content, attempt, tried_queries
            )
            tried_queries.append(queries)

            logger.debug(f"Attempt {attempt}/{max_attempts} - Queries: {queries}")
            console.print(f"[dim]Attempt {attempt}: {queries.get('unsplash', 'N/A')}[/dim]")

            # Tier 1: Try Unsplash (free stock)
            if self.config.unsplash_api_key:
                result = self._search_unsplash(queries.get("unsplash", title))
                if result:
                    is_relevant = self._validate_image_relevance(
                        result.url, title, content[:500]
                    )
                    if is_relevant:
                        logger.info(f"Found Unsplash image (attempt {attempt}, validated)")
                        console.print("[green]✓ Found Unsplash image (validated)[/green]")
                        return result
                    else:
                        console.print("[dim]Unsplash image not relevant, retrying...[/dim]")
                        continue  # Try next attempt

            # Tier 2: Try Pexels (free stock)
            if self.config.pexels_api_key:
                result = self._search_pexels(queries.get("pexels", title))
                if result:
                    is_relevant = self._validate_image_relevance(
                        result.url, title, content[:500]
                    )
                    if is_relevant:
                        logger.info(f"Found Pexels image (attempt {attempt}, validated)")
                        console.print("[green]✓ Found Pexels image (validated)[/green]")
                        return result
                    else:
                        console.print("[dim]Pexels image not relevant, retrying...[/dim]")
                        continue  # Try next attempt

        # Tier 3: Generate AI image (fallback after all attempts)
        logger.warning(f"No relevant free images found after {max_attempts} attempts, using AI")
        console.print(
            "[yellow]⚠  No relevant free images found, generating AI image...[/yellow]"
        )
        return self._generate_ai_image(
            tried_queries[-1].get("dalle", f"Professional article illustration for: {title}")
        )

    def _generate_search_queries(
        self,
        title: str,
        topics: list[str],
        content: str,
        attempt: int = 1,
        previous_queries: list[dict[str, str]] | None = None
    ) -> dict[str, str]:
        """Use LLM to generate content-aware search queries.

        Analyzes article content to identify specific subjects and generate
        targeted search queries. On retry attempts, generates alternative queries.

        Cost: ~$0.0005 per article

        Args:
            title: Article title
            topics: List of topics
            content: Article content (first ~500 words)
            attempt: Current attempt number (1-3)
            previous_queries: Previously tried queries to avoid

        Returns:
            Dict with keys: unsplash, pexels, dalle
        """
        is_vintage = self._detect_vintage_tech_context(title, topics)

        retry_context = ""
        if attempt > 1 and previous_queries:
            prev = previous_queries[-1]
            retry_context = f"\n\nPREVIOUS ATTEMPT {attempt-1} FAILED - tried: '{prev.get('unsplash', 'N/A')}'. Generate a DIFFERENT query (broader or more specific)."

        content_excerpt = content[:500] if content else ""

        prompt = f"""Generate image search queries by analyzing this article content. Return ONLY valid JSON.

Title: {title}
Topics: {", ".join(topics) if topics else "general"}
Content: {content_excerpt}{retry_context}

Return JSON with these keys:
- "unsplash": query for Unsplash (2-6 words)
- "pexels": query for Pexels (2-6 words)
- "dalle": detailed DALL-E prompt (if stock photos fail)

CRITICAL: Read the CONTENT and identify the MAIN SUBJECT.

EXAMPLES:
- Content mentions "Intel 4004 microprocessor" → unsplash: "Intel 4004 chip", pexels: "vintage microprocessor"
- Content mentions "Busicom calculator" → unsplash: "Busicom calculator", pexels: "vintage electronic calculator"
- Content about "React hooks" → unsplash: "React code screen", pexels: "JavaScript programming"
- Content about "quantum computing" → unsplash: "quantum computer", pexels: "quantum processor"

STRATEGY:
1. FIRST: Look for specific products, people, technologies, or objects mentioned in the content
2. Use those EXACT names in queries ("Intel 4004", "Busicom", "React", etc.)
3. For stock sites: be specific but searchable ("Intel 4004 chip" not just "Intel 4004")
4. For DALL-E: be detailed and descriptive
5. Vintage tech{' (detected)' if is_vintage else ''}: Prefer specific products over generic terms

Be SPECIFIC. Use ACTUAL subject matter from the content."""

        try:
            response = create_chat_completion(
                client=self.client,
                model=self.config.enrichment_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=300,
            )

            response_content = response.choices[0].message.content
            if response_content is None:
                raise ValueError("OpenAI returned empty content")
            return json.loads(response_content)
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

    def _validate_image_relevance(
        self, image_url: str, title: str, content: str
    ) -> bool:
        """Validate if image is relevant to article content using AI.

        Args:
            image_url: URL of the image to validate
            title: Article title
            content: Article content excerpt (first ~500 words)

        Returns:
            True if image is relevant, False otherwise
        """
        try:
            prompt = f"""Does this image match the article subject?

Article: {title}
Content: {content[:300]}
Image URL: {image_url}

Analyze the URL keywords (filename, path). Does it suggest relevance to the article's main subject?
Respond ONLY "yes" or "no"."""

            response = create_chat_completion(
                client=self.client,
                model=self.config.enrichment_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=10,
            )

            response_content = response.choices[0].message.content
            if response_content is None:
                return True  # Default to accepting if validation is unclear
            return "yes" in response_content.lower()
        except Exception as e:
            logger.debug(f"Image validation failed: {e}, defaulting to accept")
            return True  # Default to accepting on error

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
