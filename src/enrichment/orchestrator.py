"""Content enrichment pipeline orchestration.

This module coordinates the enrichment process, combining:
- Fast heuristic scoring (scorer.py)
- AI quality analysis (ai_analyzer.py)
- Adaptive learning (adaptive_scoring.py)

The orchestrator manages:
- Single item enrichment with combined scoring
- Sequential batch processing for reliability
- Adaptive learning updates and feedback tracking
- Early exit optimization to save API costs
"""

from datetime import UTC, datetime

from openai import OpenAI
from rich.console import Console

from ..config import get_config
from ..models import CollectedItem, EnrichedItem, PipelineConfig
from .adaptive_scoring import ScoringAdapter
from .ai_analyzer import (
    analyze_content_quality,
    extract_topics_and_themes,
    research_additional_context,
)
from .scorer import calculate_heuristic_score

console = Console()


def enrich_single_item(
    item: CollectedItem, config: PipelineConfig, adapter: ScoringAdapter | None = None
) -> EnrichedItem | None:
    """Enrich a single collected item with AI analysis and adaptive scoring.

    This is the main enrichment function that coordinates all the AI analysis.

    The enrichment process:
    1. Fast heuristic scoring (no API cost)
    2. Early exit if heuristic score too low
    3. AI quality analysis (API call)
    4. Record feedback for adaptive learning
    5. Combine scores (30% heuristic, 70% AI)
    6. Extract topics (only for promising content)
    7. Research context (only for high-quality content)

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


def enrich_collected_items(
    items: list[CollectedItem], max_workers: int = 5
) -> list[EnrichedItem]:
    """Enrich all collected items with AI analysis and adaptive scoring.

    Processes items sequentially for reliability and easier debugging.
    The max_workers parameter is kept for API compatibility but not used.

    Args:
        items: List of collected items to enrich
        max_workers: Kept for compatibility, not used in sequential mode

    Returns:
        List of successfully enriched items
    """
    config = get_config()
    enriched_items = []

    # Initialize adaptive scoring system
    adapter = ScoringAdapter()

    console.print(
        f"[bold blue]Starting enrichment of {len(items)} items (sequential processing)...[/bold blue]"
    )

    # Process items sequentially
    for i, item in enumerate(items, 1):
        try:
            console.print(f"\r[dim]Progress: {i}/{len(items)}[/dim]", end="")
            enriched = enrich_single_item(item, config, adapter)
            if enriched:
                enriched_items.append(enriched)
        except Exception as e:
            console.print(f"\n[red]✗[/red] Item {i} failed: {e}")
            continue

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
