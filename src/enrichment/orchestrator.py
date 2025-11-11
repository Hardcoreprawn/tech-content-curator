"""Content enrichment pipeline orchestration.

This module coordinates the enrichment process, combining:
- Fast heuristic scoring (scorer.py)
- AI quality analysis (ai_analyzer.py)
- Adaptive learning (adaptive_scoring.py)

The orchestrator manages:
- Single item enrichment with combined scoring
- Parallel processing with thread-local adapters (with PYTHON_GIL=0)
- Sequential batch processing fallback for reliability
- Adaptive learning updates and feedback tracking
- Early exit optimization to save API costs

LOGGING & OBSERVABILITY:
========================

The enrichment pipeline includes comprehensive structured logging for tracking:

1. Timing Instrumentation:
   - Parallel enrichment phase (per-worker coordination time)
   - Merge phase (sequential result aggregation time)
   - Pattern loading and saving time
   - Total enrichment duration with phase breakdown

2. Structured Logging with Extras:
   All INFO logs include 'extra' dict with:
   - phase='enrichment' (consistent phase tag)
   - event='patterns_loaded' | 'workers_initialized' | 'parallel_phase_complete'
         | 'merge_complete' | 'patterns_saved' | 'complete'
   - Metrics: time_seconds, worker_count, items_processed, successful_items, etc.
   - Per-item: item_id, score, time_seconds for each enriched item
   - Errors: error_type, error_context for failures

3. Log Levels:
   - INFO: Major phases, timing summaries, completion status
   - DEBUG: Per-item processing timing and scores
   - WARNING: Failures, exceptions (with counts and context)
   - ERROR: Individual item enrichment failures

4. Parsing Logs:
   Structured logs can be parsed with:
   ```
   import json
   log_line = "[INFO] ... extra={'phase': 'enrichment', 'event': 'complete', ...}"
   # Extract metrics from 'extra' dict for analytics
   ```

Example Output:
  [INFO] src.enrichment.orchestrator - Parallel enrichment phase completed in 130.32s
    extra={...phase, event, time_seconds, items_processed...}
"""

import asyncio
import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

from rich.console import Console

from ..api.openai_error_handler import handle_openai_error, is_fatal
from ..config import get_config
from ..models import CollectedItem, EnrichedItem, PipelineConfig
from ..utils.clients import get_openai_client
from ..utils.logging import get_logger
from .adaptive_scoring import ScoringAdapter
from .ai_analyzer import (
    analyze_content_quality,
    extract_topics_and_themes,
    research_additional_context,
)
from .scorer import calculate_heuristic_score

console = Console()
logger = get_logger(__name__)


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
        with get_openai_client(config) as client:
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
                console.print(
                    "[dim]  Skipping AI analysis - heuristic score too low[/dim]"
                )
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
                console.print(
                    "[dim]  Skipping further analysis - AI score too low[/dim]"
                )
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
        error_type = handle_openai_error(
            e, context=f"enriching {item.id}", should_raise=False
        )

        # If it's a fatal error (quota, auth), propagate to stop pipeline
        if is_fatal(error_type):
            logger.critical(f"Fatal error enriching {item.id}: {e}", exc_info=True)
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
        except (ValueError, TypeError, AttributeError, KeyError) as e:
            console.print(f"\n[red]✗[/red] Item {i} failed: {e}")
            logger.error(
                f"Item {i} processing failed with validation error: {e}", exc_info=True
            )
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


async def enrich_collected_items_async(
    items: list[CollectedItem], max_workers: int = 4
) -> list[EnrichedItem]:
    """Enrich items in parallel using free-threading with thread-local adapters.

    Uses ThreadPoolExecutor for true parallel enrichment when running with
    PYTHON_GIL=0. Each thread gets its own ScoringAdapter with shared patterns
    loaded once before the thread pool starts.

    CRITICAL FIX: Patterns are loaded ONCE before threading starts, preventing
    per-thread disk I/O which would cause massive contention.

    Note: Limited to 4 workers by default to avoid OpenAI rate limits.
    Adjust based on your rate limit tier.

    Args:
        items: List of collected items to enrich
        max_workers: Number of parallel workers (default: 4, max recommended: 8)

    Returns:
        List of successfully enriched items
    """
    config = get_config()
    enrichment_start = time.perf_counter()

    console.print(
        f"[bold blue]⚡ Starting parallel enrichment of {len(items)} items...[/bold blue]"
    )
    logger.info(
        f"Beginning parallel enrichment of {len(items)} collected items",
        extra={"phase": "enrichment", "mode": "parallel", "total_items": len(items)},
    )

    # CRITICAL FIX: Load patterns ONCE before thread pool starts
    # This prevents per-thread disk reads (major I/O contention)
    patterns_start = time.perf_counter()
    base_patterns = ScoringAdapter.get_shared_patterns()
    patterns_time = time.perf_counter() - patterns_start
    logger.info(
        f"Loaded shared patterns in {patterns_time:.2f}s: {len(base_patterns.get('undervalued_keywords', []))} keywords",
        extra={
            "phase": "enrichment",
            "event": "patterns_loaded",
            "time_seconds": patterns_time,
            "keywords_count": len(base_patterns.get("undervalued_keywords", [])),
        },
    )

    def enrich_wrapper(item: CollectedItem) -> tuple[EnrichedItem | None, dict]:
        """Wrapper that enriches item with thread-local adapter.

        Each thread gets an isolated ScoringAdapter with:
        - Empty feedback_history (accumulate from this run only)
        - Shared reference to base_patterns (immutable, already loaded)
        """
        # Create per-thread adapter with empty feedback
        adapter = ScoringAdapter(use_empty=True)
        item_start = time.perf_counter()

        try:
            enriched = enrich_single_item(item, config, adapter)
            item_time = time.perf_counter() - item_start

            # Log successful enrichment with timing
            logger.debug(
                f"Enriched item {item.id} in {item_time:.2f}s (score: {enriched.quality_score if enriched else 'N/A'})",
                extra={
                    "phase": "enrichment",
                    "event": "item_enriched",
                    "item_id": item.id,
                    "time_seconds": item_time,
                    "score": enriched.quality_score if enriched else None,
                },
            )
            # Return both result and adapter state for merging
            return (enriched, adapter.get_feedback_data())
        except Exception as e:
            item_time = time.perf_counter() - item_start
            logger.error(
                f"Enrichment failed for item {item.id} after {item_time:.2f}s: {e}",
                exc_info=True,
                extra={
                    "phase": "enrichment",
                    "event": "item_failed",
                    "item_id": item.id,
                    "time_seconds": item_time,
                    "error": str(e),
                },
            )
            return (None, {})

    # Parallel phase: isolated processing (no per-thread disk reads!)
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # No running loop, create one
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    # Dynamic worker count based on CPU count and rate limits
    optimal_workers = min(max_workers, (os.cpu_count() or 4) * 2, 8)
    logger.info(
        f"Using {optimal_workers} workers for parallel enrichment (CPU count: {os.cpu_count()})",
        extra={
            "phase": "enrichment",
            "event": "workers_initialized",
            "worker_count": optimal_workers,
            "cpu_count": os.cpu_count(),
        },
    )

    # Execute parallel enrichment
    parallel_start = time.perf_counter()
    console.print(
        f"[dim]Launching {optimal_workers} parallel enrichment workers...[/dim]"
    )

    with ThreadPoolExecutor(max_workers=optimal_workers) as executor:
        futures = [
            loop.run_in_executor(executor, enrich_wrapper, item) for item in items
        ]
        results = await asyncio.gather(*futures, return_exceptions=True)

    parallel_time = time.perf_counter() - parallel_start
    logger.info(
        f"Parallel enrichment phase completed in {parallel_time:.2f}s",
        extra={
            "phase": "enrichment",
            "event": "parallel_phase_complete",
            "time_seconds": parallel_time,
            "items_processed": len(results),
        },
    )

    # Sequential merge: no locks needed
    merge_start = time.perf_counter()
    enriched_items = []
    final_adapter = ScoringAdapter()
    rejected_items = []
    failed_count = 0
    exception_count = 0

    for result in results:
        if isinstance(result, Exception):
            logger.error(
                f"Thread execution failed: {result}",
                extra={
                    "phase": "enrichment",
                    "event": "thread_exception",
                    "error": str(result),
                },
            )
            exception_count += 1
            rejected_items.append(("Unknown", 0.0, "thread_exception"))
            continue

        enriched, feedback_data = result
        if enriched:
            # Track if item was rejected (returned but with low score)
            if enriched.quality_score < 0.2:
                rejected_items.append(
                    (
                        enriched.original.title[:50],
                        enriched.quality_score,
                        "combined_score_too_low",
                    )
                )
            enriched_items.append(enriched)
            final_adapter.merge_feedback(feedback_data)
        else:
            failed_count += 1
            rejected_items.append(("Unknown", 0.0, "enrichment_failed"))

    merge_time = time.perf_counter() - merge_start

    if exception_count > 0 or failed_count > 0:
        console.print(
            f"[yellow]⚠ {exception_count} thread exceptions, {failed_count} enrichment failures[/yellow]"
        )
        logger.warning(
            f"Enrichment: {exception_count} thread exceptions, {failed_count} enrichment failures",
            extra={
                "phase": "enrichment",
                "event": "merge_complete",
                "thread_exceptions": exception_count,
                "enrichment_failures": failed_count,
                "successful": len(enriched_items),
                "time_seconds": merge_time,
            },
        )
    else:
        logger.info(
            f"Merge phase complete: {len(enriched_items)} items successfully enriched",
            extra={
                "phase": "enrichment",
                "event": "merge_complete",
                "successful": len(enriched_items),
                "time_seconds": merge_time,
            },
        )

    # Single-threaded save
    console.print("[blue]Updating adaptive scoring patterns...[/blue]")
    save_start = time.perf_counter()
    final_adapter.update_learned_patterns()
    final_adapter.save_feedback()
    save_time = time.perf_counter() - save_start

    logger.info(
        f"Patterns and feedback saved in {save_time:.2f}s",
        extra={
            "phase": "enrichment",
            "event": "patterns_saved",
            "time_seconds": save_time,
        },
    )

    # Print analysis report
    final_adapter.print_analysis_report()

    # Total timing summary
    total_time = time.perf_counter() - enrichment_start
    logger.info(
        f"Complete enrichment finished: {len(enriched_items)} items in {total_time:.2f}s "
        f"(parallel: {parallel_time:.2f}s, merge: {merge_time:.2f}s, save: {save_time:.2f}s)",
        extra={
            "phase": "enrichment",
            "event": "complete",
            "total_time": total_time,
            "parallel_time": parallel_time,
            "merge_time": merge_time,
            "save_time": save_time,
            "successful_items": len(enriched_items),
            "rejected_items": len(rejected_items),
        },
    )
    console.print(f"[dim]Total enrichment time: {total_time:.2f}s[/dim]")

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
        f"\n[bold green]✓ Parallel enrichment complete: {len(enriched_items)}/{len(items)} items enriched[/bold green]"
    )
    logger.info(
        f"Parallel enrichment complete: {len(enriched_items)}/{len(items)} items (rejected: {len(rejected_items)}, failed: {failed_count})"
    )
    return enriched_items
