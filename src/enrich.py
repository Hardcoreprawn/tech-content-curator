"""Content enrichment using AI research and analysis.

This module takes raw collected items and enriches them with:
1. Quality assessment - is this worth turning into an article?
2. Topic extraction - what themes/subjects does this cover?
3. Research - find related sources and context
4. Scoring - rank items by potential article value

DESIGN DECISIONS:
- Use OpenAI API for analysis (reliable, good at reasoning tasks)
- Each enrichment step is a separate function (testable, clear)
- Store research results in structured format (easy to debug)
- Fail gracefully - if AI fails, we can still use basic content
- Parallel processing with rate limiting for faster enrichment
"""

import asyncio
import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

from openai import APIConnectionError, APITimeoutError, OpenAI, RateLimitError
from rich.console import Console
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from .adaptive_scoring import ScoringAdapter
from .config import get_config, get_data_dir
from .models import CollectedItem, EnrichedItem, PipelineConfig

console = Console()


# Configure tenacity retry logic for OpenAI API calls

# Set up a simple logger for tenacity
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def log_retry_attempt(retry_state):
    """Custom callback to log retry attempts with Rich console."""
    exception = retry_state.outcome.exception() if retry_state.outcome.failed else None
    attempt_num = retry_state.attempt_number
    if exception:
        console.print(
            f"[yellow]⏳ OpenAI API attempt {attempt_num} failed: {exception}. Retrying...[/yellow]"
        )


def log_final_failure(retry_state):
    """Custom callback to log final failure."""
    exception = retry_state.outcome.exception() if retry_state.outcome.failed else None
    if exception:
        console.print(
            f"[red]❌ OpenAI API failed after {retry_state.attempt_number} attempts: {exception}[/red]"
        )


openai_retry = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    retry=retry_if_exception_type(
        (APITimeoutError, APIConnectionError, RateLimitError)
    ),
    before_sleep=log_retry_attempt,
)


def calculate_heuristic_score(
    item: CollectedItem, adapter: ScoringAdapter | None = None
) -> tuple[float, str]:
    """Calculate quality score using fast heuristics with adaptive improvements.

    This provides a baseline score using measurable factors:
    - Content length and structure
    - Technical keywords and indicators
    - Engagement metrics from source platform
    - Language and formatting quality
    - Adaptive adjustments learned from AI feedback

    Args:
        item: The collected item to analyze
        adapter: Optional scoring adapter for learned improvements

    Returns:
        Tuple of (heuristic_score, explanation)
    """
    score = 0.0
    factors = []

    content = item.content.lower()
    original_content = item.content

    # Length factors (sweet spot: 100-800 chars)
    length = len(original_content)
    if length < 50:
        factors.append("too short")
    elif length < 100:
        score += 0.1
        factors.append("short but viable")
    elif 100 <= length <= 400:
        score += 0.3
        factors.append("good length")
    elif 400 < length <= 800:
        score += 0.2
        factors.append("substantial length")
    else:
        score += 0.1
        factors.append("very long")

    # Technical keyword indicators
    tech_keywords = [
        "python",
        "javascript",
        "rust",
        "go",
        "docker",
        "kubernetes",
        "aws",
        "azure",
        "algorithm",
        "database",
        "api",
        "framework",
        "library",
        "open source",
        "machine learning",
        "ai",
        "devops",
        "cloud",
        "architecture",
        "performance",
        "security",
        "blockchain",
        "web3",
        "git",
        "linux",
        "unix",
        "programming",
        "software",
        "hardware",
        "network",
        "protocol",
        "stack",
        "backend",
        "frontend",
    ]

    tech_count = sum(1 for keyword in tech_keywords if keyword in content)
    if tech_count >= 3:
        score += 0.3
        factors.append(f"{tech_count} tech keywords")
    elif tech_count >= 1:
        score += 0.2
        factors.append(f"{tech_count} tech keyword(s)")

    # Structure indicators (links, code blocks, lists)
    if "http" in content:
        score += 0.1
        factors.append("includes links")

    if any(marker in original_content for marker in ["```", "`", "    "]):
        score += 0.2
        factors.append("includes code")

    if original_content.count("\n") >= 2:
        score += 0.1
        factors.append("structured text")

    # Engagement metrics (if available) - MUCH MORE IMPORTANT
    if hasattr(item, "metadata") and item.metadata:
        likes = item.metadata.get("favourites_count", 0)
        shares = item.metadata.get("reblogs_count", 0)
        replies = item.metadata.get("replies_count", 0)

        # Calculate weighted engagement (replies = discussion depth)
        engagement = likes + (shares * 2) + (replies * 3)

        # More granular engagement scoring
        if engagement >= 1000:
            score += 0.35
            factors.append(f"viral engagement ({engagement})")
        elif engagement >= 500:
            score += 0.30
            factors.append(f"very high engagement ({engagement})")
        elif engagement >= 100:
            score += 0.25
            factors.append(f"high engagement ({engagement})")
        elif engagement >= 50:
            score += 0.15
            factors.append(f"good engagement ({engagement})")
        elif engagement >= 10:
            score += 0.10
            factors.append(f"some engagement ({engagement})")

        # Discussion depth bonus (high replies relative to likes)
        if replies > 20 and replies > likes * 0.05:
            score += 0.1
            factors.append("active discussion")

    # Authority signals - official/known accounts
    author = item.author.lower() if hasattr(item, "author") and item.author else ""
    authority_accounts = [
        "psf",
        "thepsf",
        "python",
        "github",
        "gitlab",
        "microsoft",
        "mozilla",
        "rust",
        "golang",
        "docker",
        "kubernetes",
        "linuxfoundation",
        "torvalds",
        "gvanrossum",
        "dhh",
        "kentcdodds",
        "dan_abramov",
        "bagder",
        "nixcraft",
        "climagic",
        "b0rk",
        "jezenthomas",
    ]

    if any(auth in author for auth in authority_accounts):
        score += 0.15
        factors.append("authority account")

    # Project/organization accounts (often have more valuable content)
    org_indicators = ["foundation", "project", "team", "official", "core"]
    if any(ind in author for ind in org_indicators):
        score += 0.10
        factors.append("organization account")

    # Negative indicators
    personal_indicators = [
        "i feel",
        "my day",
        "my life",
        "personally",
        "imo",
        "just me",
    ]
    if any(indicator in content for indicator in personal_indicators):
        score -= 0.2
        factors.append("personal content")

    # News/announcement indicators (timely, important)
    news_indicators = [
        "announcing",
        "released",
        "launched",
        "new version",
        "breaking",
        "vulnerability",
        "security",
        "critical",
        "update",
        "available now",
        "just released",
        "today",
        "major",
        "important",
    ]
    news_count = sum(1 for indicator in news_indicators if indicator in content)
    if news_count >= 2:
        score += 0.20
        factors.append("newsworthy announcement")
    elif news_count >= 1:
        score += 0.10
        factors.append("announcement content")

    # Educational/tutorial indicators
    educational_indicators = [
        "how to",
        "tutorial",
        "guide",
        "learn",
        "explained",
        "introduction",
        "getting started",
        "step by step",
        "walkthrough",
        "best practices",
        "tips",
        "tricks",
        "examples",
    ]
    edu_count = sum(1 for indicator in educational_indicators if indicator in content)
    if edu_count >= 2:
        score += 0.15
        factors.append("educational content")
    elif edu_count >= 1:
        score += 0.08
        factors.append("somewhat educational")

    # Technical depth indicators
    depth_indicators = [
        "architecture",
        "implementation",
        "performance",
        "benchmark",
        "optimization",
        "analysis",
        "deep dive",
        "internals",
        "how it works",
        "under the hood",
        "technical details",
        "design",
        "algorithm",
    ]
    depth_count = sum(1 for indicator in depth_indicators if indicator in content)
    if depth_count >= 2:
        score += 0.15
        factors.append("technical depth")
    elif depth_count >= 1:
        score += 0.08
        factors.append("some depth")

    # Excessive emoji/symbols (but be less harsh)
    emoji_count = sum(1 for char in original_content if ord(char) > 127)
    if emoji_count > 20:
        score -= 0.15
        factors.append("emoji heavy")
    elif emoji_count > 10:
        score -= 0.05
        factors.append("some emoji")

    # Content richness penalties - what's MISSING matters
    # No code examples in a tech post?
    has_code = any(
        marker in original_content
        for marker in ["```", "`", "    ", "def ", "function ", "class ", "import "]
    )
    if not has_code and tech_count >= 2:
        score -= 0.10
        factors.append("no code examples")

    # Shallow content - just links without substance
    link_count = content.count("http")
    word_count = len(original_content.split())
    if link_count > 0 and word_count < 50:
        score -= 0.15
        factors.append("link-only, shallow")

    # Missing multiple sources (single link posts are weaker)
    if link_count == 1:
        score -= 0.08
        factors.append("single source")
    elif link_count == 0 and word_count > 100:
        score -= 0.12
        factors.append("no sources cited")

    # Lack of actionable content
    action_indicators = [
        "try",
        "use",
        "install",
        "download",
        "check out",
        "see",
        "read",
        "should",
        "can",
        "how",
        "step",
        "guide",
        "tutorial",
    ]
    action_count = sum(1 for indicator in action_indicators if indicator in content)
    if action_count == 0 and word_count > 50:
        score -= 0.08
        factors.append("not actionable")

    # Vague or clickbait language (diminishes quality)
    vague_indicators = [
        "amazing",
        "incredible",
        "mind-blowing",
        "insane",
        "crazy",
        "wow",
        "omg",
    ]
    vague_count = sum(1 for indicator in vague_indicators if indicator in content)
    if vague_count >= 2:
        score -= 0.10
        factors.append("vague/clickbait language")

    # Thread/continuation posts often lack context
    if "🧵" in original_content or "1/" in original_content or "thread" in content:
        score -= 0.05
        factors.append("thread post (may lack context)")

    # ALL CAPS or excessive punctuation (be acronym-aware)
    # Normalize common acronyms so they don't count against caps ratio
    KNOWN_ACRONYMS = {
        "RISC-V",
        "CPU",
        "GPU",
        "API",
        "HTTP",
        "HTTPS",
        "SQL",
        "NoSQL",
        "AWS",
        "GCP",
        "GDPR",
        "CLI",
        "LLM",
        "AI",
        "ML",
        "NLP",
        "KVM",
        "SSH",
        "TCP",
        "UDP",
        "TLS",
        "SSL",
        "JSON",
        "YAML",
        "CSV",
        "OCR",
        "IDE",
        "CI",
        "CD",
        "CI/CD",
        "SRE",
        "DNS",
        "K8S",
        "CUDA",
    }

    def _lowercase_acronyms(text: str) -> str:
        # Replace known acronyms first
        for ac in KNOWN_ACRONYMS:
            text = re.sub(rf"\b{re.escape(ac)}\b", ac.lower(), text)

        # Replace generic acronym-like tokens (2-8 chars of A-Z/0-9 possibly with hyphens)
        def repl(m: re.Match) -> str:
            token = m.group(0)
            # Allow hyphenated/digit-containing short tokens commonly used as acronyms
            if 2 <= len(token) <= 8 and re.fullmatch(r"[A-Z0-9-]+", token):
                return token.lower()
            return token

        return re.sub(r"\b[A-Z0-9-]{2,10}\b", repl, text)

    normalized_for_caps = _lowercase_acronyms(original_content)
    caps_ratio = sum(1 for c in normalized_for_caps if c.isupper()) / max(
        1, len(normalized_for_caps)
    )
    # Also detect shouting: long runs of uppercase letters excluding acronyms
    has_shouting = bool(re.search(r"[A-Z]{6,}", normalized_for_caps))
    if caps_ratio > 0.35 or has_shouting:
        score -= 0.10
        factors.append("excessive caps")

    exclamation_count = original_content.count("!")
    if exclamation_count > 3:
        score -= 0.08
        factors.append("excessive punctuation")
        factors.append("excessive emojis")

    # Penalize low-effort curated lists (e.g., GitHub "awesome" repositories)
    source_name = (
        item.metadata.get("source_name", "") if item.metadata else ""
    ).lower()
    repo_context = (item.title + " " + item.content).lower()
    topics_text = (
        " ".join(item.metadata.get("topics", [])).lower()
        if (item.metadata and item.metadata.get("topics"))
        else ""
    )
    awesome_indicators = [
        "awesome-",
        "awesome ",
        "awesome\n",
        "free-programming-books",
        "awesome-selfhosted",
        "awesome selfhosted",
    ]
    if "github" in source_name and (
        any(ind in repo_context for ind in awesome_indicators)
        or "awesome" in topics_text
    ):
        score -= 0.15
        factors.append("curated list repository")

    # Apply adaptive adjustments based on learned patterns
    adaptive_adjustment = 0.0
    adaptive_reasons = []

    if adapter:
        adaptive_adjustment, adaptive_reasons = adapter.get_adaptive_adjustments(item)
        score += adaptive_adjustment
        factors.extend(adaptive_reasons)

    # Ensure score doesn't go negative (but allow > 1.0 for exceptional content)
    score = max(0.0, score)

    explanation = (
        f"Heuristic: {', '.join(factors)}" if factors else "Basic heuristic analysis"
    )
    if adaptive_adjustment > 0:
        explanation += f" (+{adaptive_adjustment:.2f} adaptive)"

    return score, explanation


@openai_retry
def analyze_content_quality(item: CollectedItem, client: OpenAI) -> tuple[float, str]:
    """Analyze content quality with more selective, realistic scoring.

    This uses a more discriminating scale that better reflects the reality
    that most social media content isn't article-worthy.

    Args:
        item: The collected item to analyze
        client: OpenAI client instance

    Returns:
        Tuple of (quality_score, explanation)
        Score is 0.0-1.0 with more realistic distribution
    """
    # Create a more specific prompt that forces the AI to actually analyze the content
    prompt = f"""
    Analyze this social media post and give it a realistic quality score for a tech blog.

    POST CONTENT: "{item.content[:500]}"

    First, identify what this post is actually about:
    - Is it technical content (programming, systems, tools, science)?
    - Is it personal/social content (life updates, opinions, politics)?
    - Is it entitled whining or first-world problems disguised as insights?
    - Does it contain actionable insights or just commentary?
    - Is there enough technical depth to expand into an article?

    Consider these factors:
    - Technical depth and actionability
    - Broader applicability vs niche concerns
    - Whether it provides useful insights vs just complaints
    - Signal-to-noise ratio for a general tech audience

    Then score it:
    - 0.8-1.0: Major technical breakthrough or deep insight
    - 0.6-0.7: Solid technical content with practical value
    - 0.4-0.5: Some technical merit, basic but useful
    - 0.2-0.3: Minimal technical value, niche, or mostly commentary
    - 0.0-0.1: Not technical, purely personal, or no actionable value

    Be realistic but fair. Consider if the content would be useful to a meaningful portion of readers.

    Respond ONLY with JSON:
    {{"score": 0.X, "explanation": "Specific reason based on actual content analysis"}}
    """

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",  # Cheaper for quality assessment
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,  # Slightly higher for more variation
            max_tokens=150,
        )

        content = response.choices[0].message.content
        if not content:
            raise ValueError("Empty response from OpenAI")

        result_text = content.strip()
        result = json.loads(result_text)

        return float(result["score"]), str(result["explanation"])

    except Exception as e:
        console.print(f"[yellow]⚠[/yellow] Quality analysis failed for {item.id}: {e}")
        # Default to medium quality if AI fails
        return 0.5, f"Analysis failed: {e}"


@openai_retry
def extract_topics_and_themes(item: CollectedItem, client: OpenAI) -> list[str]:
    """Extract main topics and themes from content.

    This identifies what the post is actually about so we can:
    - Group related content together
    - Find additional research sources
    - Generate appropriate tags for articles

    Args:
        item: The collected item to analyze
        client: OpenAI client instance

    Returns:
        List of topic strings (e.g., ["machine learning", "python", "data science"])
    """
    prompt = f"""
    Extract the main technical topics and themes from this social media post.

    Content: "{item.content}"

    Identify 3-7 specific topics that this post covers. Focus on:
    - Programming languages and technologies
    - Technical concepts and methodologies
    - Tools and frameworks
    - Industry trends and practices

    Return topics as a simple JSON array of strings:
    ["topic1", "topic2", "topic3"]

    Examples:
    - ["python", "web scraping", "data analysis"]
    - ["kubernetes", "devops", "container orchestration"]
    - ["machine learning", "neural networks", "pytorch"]

    Be specific but not overly narrow. "python web development" is better than just "programming".
    """

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=150,
        )

        content = response.choices[0].message.content
        if not content:
            raise ValueError("Empty response from OpenAI")

        result_text = content.strip()
        topics = json.loads(result_text)

        # Validate and clean up topics
        if isinstance(topics, list) and all(isinstance(t, str) for t in topics):
            return [topic.lower().strip() for topic in topics if topic.strip()]
        else:
            console.print(f"[yellow]⚠[/yellow] Invalid topics format for {item.id}")
            return []

    except Exception as e:
        console.print(f"[yellow]⚠[/yellow] Topic extraction failed for {item.id}: {e}")
        return []


@openai_retry
def research_additional_context(
    item: CollectedItem, topics: list[str], client: OpenAI
) -> str:
    """Generate research summary and context for the content.

    This creates additional context that would be useful for turning
    the social media post into a full article.

    Args:
        item: The collected item
        topics: Extracted topics for context
        client: OpenAI client instance

    Returns:
        Research summary string
    """
    prompt = f"""
    You are researching background for a tech blog article based on this social media post.

    Original Content: "{item.content}"
    Topics: {", ".join(topics)}

    Provide a research summary that would help expand this into a full blog article. Include:

    1. **Background Context**: What background knowledge would readers need?
    2. **Current State**: Where does this topic stand in the current tech landscape?
    3. **Key Questions**: What questions would readers have about this topic?
    4. **Related Concepts**: What related technologies or concepts should be covered?

    Write 2-3 paragraphs that would serve as research notes for article writing.
    Focus on factual, technical information rather than opinions.
    """

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",  # Better for research and reasoning
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
            max_tokens=400,
        )

        content = response.choices[0].message.content
        if not content:
            raise ValueError("Empty response from OpenAI")
        return content.strip()

    except Exception as e:
        console.print(f"[yellow]⚠[/yellow] Research failed for {item.id}: {e}")
        return f"Research unavailable: {e}"


def enrich_single_item(
    item: CollectedItem, config: PipelineConfig, adapter: ScoringAdapter | None = None
) -> EnrichedItem | None:
    """Enrich a single collected item with AI analysis and adaptive scoring.

    This is the main enrichment function that coordinates all the AI analysis.

    Args:
        item: The collected item to enrich
        config: Pipeline configuration with API keys
        adapter: Optional scoring adapter for learning improvements

    Returns:
        EnrichedItem if successful, None if enrichment fails
    """
    console.print(f"[blue]Enriching:[/blue] {item.title[:50]}...")

    try:
        client = OpenAI(
            api_key=config.openai_api_key,
            timeout=60.0,  # 60 second timeout for API calls
            max_retries=0,  # Let tenacity handle retries instead
        )

        # Step 1a: Fast heuristic scoring with adaptive improvements (no API cost)
        heuristic_score, heuristic_explanation = calculate_heuristic_score(
            item, adapter
        )
        console.print(
            f"  Heuristic: {heuristic_score:.2f} - {heuristic_explanation[:50]}..."
        )

        # Early exit for very low heuristic scores (save API costs)
        if heuristic_score < 0.15:
            console.print("[dim]  Skipping AI analysis - heuristic score too low[/dim]")
            return EnrichedItem(
                original=item,
                research_summary="Heuristic score too low for AI analysis",
                related_sources=[],
                topics=[],
                quality_score=heuristic_score,
                enriched_at=datetime.now(UTC),
            )

        # Step 1b: AI quality analysis (only for promising content)
        ai_score, ai_explanation = analyze_content_quality(item, client)
        console.print(f"  AI Quality: {ai_score:.2f} - {ai_explanation[:50]}...")

        # Record feedback for adaptive learning
        if adapter:
            adapter.record_feedback(
                item, heuristic_score, ai_score, heuristic_explanation
            )

        # Combine scores (weighted average: 30% heuristic, 70% AI)
        final_score = (heuristic_score * 0.3) + (ai_score * 0.7)
        console.print(f"  Final: {final_score:.2f}")

        # Early exit for low combined scores
        if final_score < 0.2:
            console.print(
                "[dim]  Skipping further analysis - combined score too low[/dim]"
            )
            return EnrichedItem(
                original=item,
                research_summary="Combined score too low for further analysis",
                related_sources=[],
                topics=[],
                quality_score=final_score,
                enriched_at=datetime.now(UTC),
            )

        # Step 2: Extract topics (only for items that passed scoring)
        topics = extract_topics_and_themes(item, client)
        console.print(
            f"  Topics: {', '.join(topics[:3])}{'...' if len(topics) > 3 else ''}"
        )

        # Step 3: Research context (only for decent quality items to save API costs)
        if final_score >= 0.4:
            research_summary = research_additional_context(item, topics, client)
        else:
            research_summary = "Score below threshold for detailed research."

        # Create enriched item
        enriched = EnrichedItem(
            original=item,
            research_summary=research_summary,
            related_sources=[],  # We'll add web search in a future iteration
            topics=topics,
            quality_score=final_score,
            enriched_at=datetime.now(UTC),
        )

        console.print(
            f"[green]✓[/green] Enriched: {item.title[:30]}... (score: {final_score:.2f})"
        )
        return enriched

    except Exception as e:
        console.print(f"[red]✗[/red] Enrichment failed for {item.id}: {e}")
        return None


def enrich_collected_items(items: list[CollectedItem], max_workers: int = 5) -> list[EnrichedItem]:
    """Enrich all collected items with AI analysis and adaptive scoring.

    This processes items in parallel with rate limiting to avoid API throttling.

    Args:
        items: List of collected items to enrich
        max_workers: Maximum number of concurrent enrichment tasks (default: 5)

    Returns:
        List of successfully enriched items
    """
    config = get_config()
    enriched_items = []

    # Initialize adaptive scoring system
    adapter = ScoringAdapter()

    console.print(
        f"[bold blue]Starting parallel enrichment of {len(items)} items (max {max_workers} concurrent)...[/bold blue]"
    )

    # Process items in parallel with ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        futures = []
        for i, item in enumerate(items, 1):
            future = executor.submit(enrich_single_item, item, config, adapter)
            futures.append((i, future))
        
        # Collect results as they complete
        for i, future in futures:
            try:
                console.print(f"\r[dim]Progress: {i}/{len(items)}[/dim]", end="")
                enriched = future.result()
                if enriched:
                    enriched_items.append(enriched)
            except Exception as e:
                console.print(f"\n[yellow]⚠[/yellow] Item {i} failed: {e}")
    
    console.print()  # New line after progress

    # Update learned patterns and save feedback
    console.print("[blue]Updating adaptive scoring patterns...[/blue]")
    adapter.update_learned_patterns()
    adapter.save_feedback()

    # Print analysis report
    adapter.print_analysis_report()

    console.print(
        f"\n[bold green]✓ Enrichment complete: {len(enriched_items)}/{len(items)} items successfully enriched[/bold green]"
    )
    return enriched_items


def save_enriched_items(
    items: list[EnrichedItem], timestamp: str | None = None
) -> Path:
    """Save enriched items to JSON file.

    Args:
        items: List of enriched items to save
        timestamp: Optional timestamp for filename

    Returns:
        Path to saved file
    """
    if not timestamp:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    filename = f"enriched_{timestamp}.json"
    filepath = get_data_dir() / filename

    # Convert to dict for JSON serialization
    data = {
        "enriched_at": datetime.now(UTC).isoformat(),
        "total_items": len(items),
        "items": [item.model_dump() for item in items],
    }

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)

    console.print(f"[green]✓[/green] Saved {len(items)} enriched items to {filename}")
    return filepath


def load_collected_items(filepath: Path) -> list[CollectedItem]:
    """Load collected items from a JSON file.

    Args:
        filepath: Path to the collected items JSON file

    Returns:
        List of CollectedItem objects
    """
    with open(filepath, encoding="utf-8") as f:
        data = json.load(f)

    items = []
    for item_data in data["items"]:
        try:
            item = CollectedItem(**item_data)
            items.append(item)
        except Exception as e:
            console.print(f"[yellow]⚠[/yellow] Failed to load item: {e}")
            continue

    console.print(
        f"[green]✓[/green] Loaded {len(items)} collected items from {filepath.name}"
    )
    return items


if __name__ == "__main__":
    """Run enrichment on the most recent collected data."""
    data_dir = get_data_dir()

    # Find the most recent collected file
    collected_files = list(data_dir.glob("collected_*.json"))
    if not collected_files:
        console.print("[red]No collected data files found. Run collection first.[/red]")
        exit(1)

    latest_file = max(collected_files, key=lambda f: f.stat().st_mtime)
    console.print(f"[blue]Loading items from {latest_file.name}...[/blue]")

    # Load and enrich items
    items = load_collected_items(latest_file)
    enriched = enrich_collected_items(items)

    # Save results
    if enriched:
        save_enriched_items(enriched)
        console.print(
            f"\n[bold green]🎉 Enrichment complete! {len(enriched)} items ready for article generation.[/bold green]"
        )
    else:
        console.print("[red]No items were successfully enriched.[/red]")
