# Feature 1: Multi-Source Image Selection

**Goal**: Replace gradient images with real photos from free sources  
**Effort**: 3-4 days  
**Cost Impact**: $0.00-0.020 per article (vs $0.020 current) = save 50-100%

---

## What to Build

Create a smart image selector that tries free sources first, then falls back to AI.

```
Try in order:
1. Wikimedia Commons (public domain) → FREE
2. Unsplash (stock photos) → FREE
3. Pexels (stock photos) → FREE
4. DALL-E 3 (AI fallback) → $0.020
```

---

## Files to Create

### `src/images/__init__.py`
```python
from .selector import CoverImageSelector
__all__ = ["CoverImageSelector"]
```

### `src/images/selector.py` (~250 lines)

```python
"""Multi-source image selector with LLM-generated queries."""
from dataclasses import dataclass
import json
import httpx
from openai import OpenAI
from rich.console import Console

console = Console()

@dataclass
class CoverImage:
    url: str
    alt_text: str
    source: str  # "wikimedia", "unsplash", "pexels", "dalle-3"
    cost: float
    quality_score: float  # 0-1, how confident we are in the match

class CoverImageSelector:
    def __init__(self, openai_client: OpenAI, config):
        self.client = openai_client
        self.config = config
    
    def select(self, title: str, topics: list[str]) -> CoverImage:
        """Select best image from free sources, fallback to AI."""
        
        # Step 1: Generate search queries via LLM
        # (Much better than deterministic rules)
        queries = self._generate_search_queries(title, topics)
        
        # Tier 1: Try Wikimedia (public domain)
        result = self._search_wikimedia(queries["wikimedia"])
        if result and result.quality_score >= 0.75:
            return result
        
        # Tier 2: Try Unsplash (free stock)
        result = self._search_unsplash(queries["unsplash"])
        if result and result.quality_score >= 0.70:
            return result
        
        # Tier 3: Try Pexels (free stock)
        result = self._search_pexels(queries["pexels"])
        if result and result.quality_score >= 0.65:
            return result
        
        # Tier 4: Generate AI image
        return self._generate_ai_image(queries["dalle"])
    
    def _generate_search_queries(self, title: str, topics: list[str]) -> dict[str, str]:
        """Use gpt-3.5-turbo to generate effective search queries.
        
        Why LLM? Deterministic rules produce generic, poor queries.
        LLM understands context and generates natural searches.
        Cost: ~$0.0005 per article
        """
        prompt = f"""Generate image search queries for this article.

Title: {title}
Topics: {", ".join(topics)}

Return JSON with these keys:
- "wikimedia": query for Wikimedia Commons (academic/scientific focus)
- "unsplash": query for Unsplash (high-quality natural photos)
- "pexels": query for Pexels (generic focus)
- "dalle": detailed prompt for DALL-E if no stock photo found

Make queries specific and natural."""

        response = self.client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=300
        )
        
        try:
            return json.loads(response.choices[0].message.content)
        except (json.JSONDecodeError, AttributeError):
            # Fallback if parsing fails
            return {
                "wikimedia": title,
                "unsplash": title,
                "pexels": title,
                "dalle": f"Professional article illustration for: {title}"
            }
    
    def _search_wikimedia(self, query: str) -> CoverImage | None:
        """Search Wikimedia Commons for public domain images."""
        try:
            response = httpx.get(
                "https://commons.wikimedia.org/w/api.php",
                params={
                    "action": "query",
                    "list": "search",
                    "srsearch": query,
                    "format": "json",
                    "srlimit": 1
                },
                timeout=self.config.image_source_timeout
            )
            data = response.json()
            
            if data.get("query", {}).get("search"):
                result = data["query"]["search"][0]
                # Wikimedia results are public domain
                return CoverImage(
                    url=f"https://commons.wikimedia.org/wiki/{result['title']}",
                    alt_text=result["title"],
                    source="wikimedia",
                    cost=0.0,
                    quality_score=0.75  # Conservative score
                )
        except Exception as e:
            console.print(f"[yellow]Wikimedia search failed: {e}[/yellow]")
        
        return None
    
    def _search_unsplash(self, query: str) -> CoverImage | None:
        """Search Unsplash for free stock photos."""
        try:
            response = httpx.get(
                "https://api.unsplash.com/search/photos",
                params={
                    "query": query,
                    "per_page": 1,
                    "orientation": "landscape"
                },
                headers={"Authorization": f"Client-ID {self.config.unsplash_api_key}"},
                timeout=self.config.image_source_timeout
            )
            data = response.json()
            
            if data.get("results"):
                result = data["results"][0]
                return CoverImage(
                    url=result["urls"]["regular"],
                    alt_text=result.get("description", query),
                    source="unsplash",
                    cost=0.0,
                    quality_score=0.80  # Unsplash is high quality
                )
        except Exception as e:
            console.print(f"[yellow]Unsplash search failed: {e}[/yellow]")
        
        return None
    
    def _search_pexels(self, query: str) -> CoverImage | None:
        """Search Pexels for free stock photos."""
        try:
            response = httpx.get(
                "https://api.pexels.com/v1/search",
                params={
                    "query": query,
                    "per_page": 1,
                    "orientation": "landscape"
                },
                headers={"Authorization": self.config.pexels_api_key},
                timeout=self.config.image_source_timeout
            )
            data = response.json()
            
            if data.get("photos"):
                result = data["photos"][0]
                return CoverImage(
                    url=result["src"]["large"],
                    alt_text=query,
                    source="pexels",
                    cost=0.0,
                    quality_score=0.75
                )
        except Exception as e:
            console.print(f"[yellow]Pexels search failed: {e}[/yellow]")
        
        return None
    
    def _generate_ai_image(self, prompt: str) -> CoverImage:
        """Generate image via DALL-E 3 (last resort)."""
        response = self.client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            size="1024x1024",
            quality="standard",
            n=1
        )
        
        return CoverImage(
            url=response.data[0].url,
            alt_text="Article hero image",
            source="dalle-3",
            cost=0.020,
            quality_score=0.85
        )
```

---

## Files to Modify

### `src/config.py`

Add to `PipelineConfig`:
```python
unsplash_api_key: str = ""
pexels_api_key: str = ""
image_source_timeout: int = 10
```

### `src/generate.py`

Around line 811 (where images are selected):
```python
from src.images import CoverImageSelector

# In generate_article():
if config.unsplash_api_key:  # Only if we have API keys
    selector = CoverImageSelector(client, config)
    image = selector.select(article.title, article.tags)
    hero_url = image.url
    costs["image_generation"] = image.cost
else:
    # Fall back to existing gradient library
    hero_url, icon_url = select_or_create_cover_image(article.tags, slug)
    costs["image_generation"] = 0.0
```

### `.env.example`

```bash
# Image Selection
UNSPLASH_API_KEY=your_api_key_here
PEXELS_API_KEY=your_api_key_here
```

---

## How to Get API Keys

**Unsplash**: https://unsplash.com/developers (5 min)
- Sign up, create application, copy "Access Key"
- Free tier: 50 requests/hour (plenty)

**Pexels**: https://www.pexels.com/api (5 min)
- Sign up, create API key, copy it
- Free tier: unlimited

**Wikimedia**: No API key needed ✓

---

## Tests to Write

```python
# tests/test_image_selector.py

def test_unsplash_search_returns_image():
    """Mock Unsplash, verify image selected."""
    
def test_wikimedia_fallback():
    """If Unsplash fails, try Wikimedia."""
    
def test_dalle_fallback_when_all_free_fail():
    """If all free sources timeout, use AI."""
    
def test_cost_tracked():
    """Free sources = $0.00, AI = $0.020."""
```

---

## Success Criteria

- ✅ Owl article uses real photo (Unsplash or Wikimedia)
- ✅ No cost increase (stock photos are FREE)
- ✅ Falls back gracefully if API times out
- ✅ Image quality rated 4+/5 by editor

---

## Time Breakdown

- Setup API keys: 10 min
- Write `src/images/selector.py`: 90 min
- Write tests: 30 min
- Integration in `generate.py`: 20 min
- Testing: 30 min
- **Total: 3-4 hours**

