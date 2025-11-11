# Logging & Observability Guide

## Overview

The free-threading optimization pipeline includes comprehensive structured logging to make it easy to understand what's happening during collection and enrichment operations.

## Key Principles

1. **Structured Logging**: All important logs include an `extra` dict with structured data
2. **Phase-Based Tracking**: Every log is tagged with `phase='collection'` or `phase='enrichment'`
3. **Event-Based Logging**: Major events are tracked via `event='event_name'` tags
4. **Timing Instrumentation**: All significant operations are timed with `time_seconds` fields
5. **Easy Parsing**: Logs can be easily parsed and analyzed programmatically

## Collection Pipeline Logging

### Overview

The parallel collection pipeline logs timing information for:
- Individual source collection (Mastodon, Reddit, HackerNews, GitHub)
- Parallel execution phase
- Deduplication (exact + semantic)
- Complete pipeline

### Key Log Events

```
[INFO] src.collectors.orchestrator - Launching parallel collection from 4 sources...
[INFO] src.collectors.orchestrator - Using 4 workers...
  extra={'phase': 'collection', 'event': 'workers_initialized', 'worker_count': 4}

[INFO] src.collectors.orchestrator - Mastodon collected 36 items in 11.10s
  extra={'phase': 'collection', 'source': 'Mastodon', 'count': 36, 'elapsed_seconds': 11.10}

[INFO] src.collectors.orchestrator - Parallel collection completed: 85 items in 9.64s...
  extra={'phase': 'collection', 'event': 'parallel_phase_complete', 'time_seconds': 9.64}
```

### Performance Metrics

To analyze collection performance:

```bash
# Show all collection timing logs
grep "phase.*collection" /var/log/app.log | grep "time_seconds"

# Extract source-specific timings
grep "src.*Mastodon collected" /var/log/app.log | sed 's/.*in \([0-9.]*\)s.*/\1/'
```

## Enrichment Pipeline Logging

### Overview

The parallel enrichment pipeline logs timing information for:
- Pattern loading (shared patterns for all threads)
- Worker initialization
- Parallel enrichment phase (per-worker coordination)
- Result merging (sequential phase)
- Pattern updates and saves
- Complete pipeline

### Key Log Events

```
[INFO] src.enrichment.orchestrator - Beginning parallel enrichment of 67 items
  extra={'phase': 'enrichment', 'mode': 'parallel', 'total_items': 67}

[INFO] src.enrichment.orchestrator - Loaded shared patterns in 0.00s: 8 keywords
  extra={'phase': 'enrichment', 'event': 'patterns_loaded', 'time_seconds': 0.00, ...}

[INFO] src.enrichment.orchestrator - Using 4 workers for parallel enrichment
  extra={'phase': 'enrichment', 'event': 'workers_initialized', 'worker_count': 4, ...}

[INFO] src.enrichment.orchestrator - Parallel enrichment phase completed in 130.32s
  extra={'phase': 'enrichment', 'event': 'parallel_phase_complete', 'time_seconds': 130.32, ...}

[INFO] src.enrichment.orchestrator - Merge phase complete: 67 items successfully enriched
  extra={'phase': 'enrichment', 'event': 'merge_complete', 'successful': 67, 'time_seconds': 0.02}

[INFO] src.enrichment.orchestrator - Complete enrichment finished: 67 items in 130.39s...
  extra={...'event': 'complete', 'total_time': 130.39, 'parallel_time': 130.32, ...}
```

### Debug-Level Logs

Per-item enrichment timing (DEBUG level):

```
[DEBUG] src.enrichment.orchestrator - Enriched item mastodon_123 in 2.45s (score: 0.60)
  extra={'phase': 'enrichment', 'event': 'item_enriched', 'item_id': 'mastodon_123', ...}
```

## Structured Logging Format

### Standard Extra Fields

Every structured log includes:

```python
extra = {
    'phase': 'collection' | 'enrichment',      # Pipeline phase
    'event': 'event_name',                     # Specific event
    'time_seconds': float,                     # Elapsed time
    # Additional context fields...
}
```

### Phase-Specific Extra Fields

**Collection:**
- `source`: 'Mastodon' | 'Reddit' | 'HackerNews' | 'GitHub'
- `count`: Number of items from source
- `items_processed`: Total items in batch
- `unique_items`: After deduplication

**Enrichment:**
- `worker_count`: Number of parallel workers
- `cpu_count`: Available CPU cores
- `successful_items`: Items enriched successfully
- `thread_exceptions`: Number of thread failures
- `enrichment_failures`: Items that failed to enrich
- `item_id`: ID of specific item (per-item logs)
- `score`: Quality score (per-item logs)

## Parsing Logs Programmatically

### Python Example

```python
import logging
import json

# Configure to capture structured logs
logging.basicConfig(level=logging.INFO)

# In your log handler:
class StructuredLogHandler(logging.Handler):
    def emit(self, record):
        log_data = {
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'extras': record.__dict__.get('extra', {})
        }
        # Send to analytics, store, etc.
        print(json.dumps(log_data))

# Filter logs by phase
for record in logs:
    if record.extra.get('phase') == 'enrichment':
        print(f"Enrichment event: {record.extra.get('event')}")
```

### Bash Example

```bash
# Show all enrichment timing events
grep "\[INFO\].*enrichment.*event" app.log | grep -oP "time_seconds['\"]:\s*\K[^,}]*"

# Calculate average enrichment time per item
grep "item_enriched" app.log | sed 's/.*time_seconds": \([0-9.]*\).*/\1/' | awk '{sum+=$1; count++} END {print "Average:", sum/count}'

# Find failures
grep -E "thread_exceptions|enrichment_failures" app.log | grep -v "0"
```

## Timing Breakdown

### Collection Pipeline (Parallel)

```
Sequential: ~19 seconds
Parallel:   ~9.6 seconds (1.97x speedup)

Phases:
- Pattern loading: ~0.00s
- Worker init: <0.01s
- Parallel collection: ~9.6s
- Deduplication: ~0.2s
- Save: <0.01s
```

### Enrichment Pipeline (Parallel)

```
Phases:
- Pattern loading: ~0.00s
- Worker init: <0.01s
- Parallel enrichment: ~130.3s (4 workers × 67 items)
- Result merge: ~0.02s
- Pattern update & save: ~0.03s
- Total: ~130.4s
```

## Debugging Tips

### Find Slow Items
```bash
# Find items taking > 5 seconds to enrich
grep "item_enriched" app.log | awk -F'time_seconds' '{print $2}' | awk '$1 > 5'
```

### Detect Worker Imbalance
```bash
# Check if some workers finish much faster than others
# (Would show in item completion order in logs)
grep "Successfully enriched" app.log | head -20 | tail -20
```

### Identify Failures
```bash
# Show all failures with context
grep -B2 -A2 "thread_exceptions\|enrichment_failures\|item_failed" app.log
```

## Logging Levels

- **DEBUG**: Per-item processing, detailed state changes
- **INFO**: Phase transitions, timing summaries, completion status
- **WARNING**: Failures with counts, recoverable issues
- **ERROR**: Individual item failures, exceptions
- **CRITICAL**: Fatal system errors

## Best Practices

1. **Always use structured logging** for new operations
2. **Include timing for all I/O operations** (disk, network, API)
3. **Use phase and event tags** for consistency
4. **Log error context** (item ID, source, etc.)
5. **Include counts** for batch operations
6. **Use appropriate log level** (don't use INFO for debug data)
7. **Keep extra dict flat** (no nested structures, for easier parsing)

## Configuration

### Enable Debug Logging

```bash
# Via environment variable
export LOG_LEVEL=DEBUG
python -m src.enrichment

# Or in code
from src.utils.logging import configure_root_logger
import logging
configure_root_logger(logging.DEBUG)
```

### Custom Log Format

Edit `src/utils/logging.py` to customize:

```python
LOG_FORMAT = "[%(levelname)s] %(name)s - %(message)s"
# Add timestamp:
LOG_FORMAT = "[%(asctime)s] [%(levelname)s] %(name)s - %(message)s"
# Add process ID:
LOG_FORMAT = "[%(levelname)s] [PID:%(process)d] %(name)s - %(message)s"
```

## See Also

- [Phase 0: Lock-Free Architecture](FREE-THREADING-OPTIMIZATION.md#phase-0-completion-summary)
- [Phase 1: Collection Parallelization](FREE-THREADING-OPTIMIZATION.md#phase-1-completion-summary)
- [Setup Guide](SETUP.md#free-threading-environment-setup)
