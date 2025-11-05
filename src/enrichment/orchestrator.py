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

import logging
from datetime import UTC, datetime

from openai import OpenAI
from rich.console import Console

from ..api.openai_error_handler import handle_openai_error, is_fatal
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
logger = logging.getLogger(__name__)


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
    logger.info(f"Starting enrichment for item: {item.id} | title: {item.title[:60]}")

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
        logger.debug(
            f"Heuristic score: {heuristic_score:.3f} | reason: {heuristic_explanation}"
        )

        # Early exit for very low heuristic scores (save API costs)
        if heuristic_score < 0.15:
            console.print("[dim]  Skipping AI analysis - heuristic score too low[/dim]")
            logger.info(
                f"Rejected at heuristic stage: {item.id} (score: {heuristic_score:.3f} < 0.15)"
            )
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
        logger.debug(f"AI quality score: {ai_score:.3f} | reason: {ai_explanation}")

        # Record feedback for adaptive learning
        if adapter:
            adapter.record_feedback(
                item, heuristic_score, ai_score, heuristic_explanation
            )

        # NEW APPROACH: Use AI as primary score, keep heuristic for pre-filtering analysis
        # The heuristic and AI are uncorrelated, so we use AI for quality judgment
        # and keep heuristic for cost-analysis purposes only
        final_score = ai_score  # Trust AI for quality judgment
        console.print(f"  Final (AI-based): {final_score:.2f}")
        logger.info(
            f"Scoring analysis - Heuristic: {heuristic_score:.3f} | AI: {ai_score:.3f} | Using: {final_score:.3f} (AI-based)"
        )

        # Step 2: Extract topics (always extract for metadata, even if score is low)
        topics = extract_topics_and_themes(item, client)
        console.print(
            f"  Topics: {', '.join(topics[:3])}{'...' if len(topics) > 3 else ''}"
        )
        logger.debug(f"Extracted {len(topics)} topics: {topics}")

        # Early exit for very low AI scores (after topic extraction)
        # Note: We use 0.3 as the absolute minimum (below this, don't even research)
        if final_score < 0.3:
            console.print("[dim]  Skipping further analysis - AI score too low[/dim]")
            logger.info(
                f"Rejected at AI score stage: {item.id} (score: {final_score:.3f} < 0.3)"
            )
            return EnrichedItem(
                original=item,
                research_summary="Score below threshold for further analysis.",
                related_sources=[],
                topics=topics,
                quality_score=final_score,
                heuristic_score=heuristic_score,
                ai_score=ai_score,
                enriched_at=datetime.now(UTC),
            )

        # Step 3: Research context (for all items >= 0.3 to gather rich metadata)
        # This allows us to include educational content and do full analysis
        logger.debug(f"Running deep research for item {item.id} (score >= 0.3)")
        research_summary = research_additional_context(item, topics, client)

        # Create enriched item with both scores for analysis
        enriched = EnrichedItem(
            original=item,
            research_summary=research_summary,
            related_sources=[],  # We'll add web search in a future iteration
            topics=topics,
            quality_score=final_score,
            heuristic_score=heuristic_score,
            ai_score=ai_score,
            enriched_at=datetime.now(UTC),
        )

        console.print(
            f"[green]✓[/green] Enriched: {item.title[:30]}... (score: {final_score:.2f})"
        )
        logger.info(
            f"Successfully enriched item {item.id} with score {final_score:.3f}"
        )
        return enriched

    except Exception as e:
        # Classify error and log with context
        error_type = handle_openai_error(e, context=f"enriching {item.id}", should_raise=False)

        # If it's a fatal error (quota, auth), propagate to stop pipeline
        if is_fatal(error_type):
            raise

        # Otherwise, log and return None to skip this item
        console.print(f"[red]✗[/red] Enrichment failed for {item.id}")
        logger.error(f"Enrichment failed for item {item.id}: {e}", exc_info=True)
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
    logger.info(f"Beginning enrichment of {len(items)} collected items")

    # Process items sequentially
    rejected_items = []
    for i, item in enumerate(items, 1):
        try:
            console.print(f"\r[dim]Progress: {i}/{len(items)}[/dim]", end="")
            enriched = enrich_single_item(item, config, adapter)
            if enriched:
                # Track if item was rejected (returned but with low score)
                if enriched.quality_score < 0.2:
                    rejected_items.append(
                        (
                            item.title[:50],
                            enriched.quality_score,
                            "combined_score_too_low",
                        )
                    )
                enriched_items.append(enriched)
            else:
                rejected_items.append((item.title[:50], 0.0, "enrichment_failed"))
        except Exception as e:
            console.print(f"\n[red]✗[/red] Item {i} failed: {e}")
            logger.error(f"Item {i} processing failed: {e}")
            rejected_items.append((item.title[:50], 0.0, f"exception: {str(e)[:40]}"))
            continue

    console.print()  # New line after progress

    # Update learned patterns and save feedback
    console.print("[blue]Updating adaptive scoring patterns...[/blue]")
    adapter.update_learned_patterns()
    adapter.save_feedback()

    # Print analysis report
    adapter.print_analysis_report()

    # Quality score distribution
    if enriched_items:
        scores = [e.quality_score for e in enriched_items]
        above_threshold = sum(1 for s in scores if s >= 0.5)
        console.print("\n[cyan]📊 Quality Score Distribution:[/cyan]")
        console.print(f"  Total enriched: {len(enriched_items)}")
        console.print(f"  >= 0.5 (article ready): {above_threshold}")
        console.print(f"  < 0.5: {len(enriched_items) - above_threshold}")
        console.print(f"  Score range: {min(scores):.2f} - {max(scores):.2f}")
        logger.info(
            f"Quality distribution: {above_threshold}/{len(enriched_items)} items >= 0.5 threshold"
        )

    # Rejection analysis
    if rejected_items:
        console.print(
            f"\n[yellow]⚠️ Rejection Analysis ({len(rejected_items)} items):[/yellow]"
        )
        rejection_reasons = {}
        for title, score, reason in rejected_items:
            rejection_reasons[reason] = rejection_reasons.get(reason, 0) + 1
            logger.debug(f"Rejected: '{title}' | score: {score:.3f} | reason: {reason}")

        for reason, count in sorted(
            rejection_reasons.items(), key=lambda x: x[1], reverse=True
        ):
            console.print(f"  {reason}: {count}")

    console.print(
        f"\n[bold green]✓ Enrichment complete: {len(enriched_items)}/{len(items)} items enriched[/bold green]"
    )
    logger.info(
        f"Enrichment complete: {len(enriched_items)}/{len(items)} items (rejected: {len(rejected_items)})"
    )
    return enriched_items
