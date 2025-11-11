# Free-Threading Optimization Implementation Plan

**Status:** Python 3.14 ready, article generation parallelized  
**Target:** Parallelize collection and enrichment  
**Expected:** 1.7-2.4x speedup (11-12 min → 5-7 min)  
**⚠️ CRITICAL ISSUES:** Review findings identified major ScoringAdapter I/O contention and CostTracker thread-safety gaps - must be fixed before production

## Current Performance (Nov 10, 2025)

| Phase | Time | Parallelized? |
|-------|------|---------------|
| Collect & Enrich | 7m 44s | ❌ NO |
| Generate | 2m 25s | ✅ YES |
| Deploy | 30s | N/A |
| **Total** | **10m 53s** | **22%** |

## Critical Issues Found (From Code Review)

### 🔴 MAJOR: ScoringAdapter Loading Existing Data

**Problem:** Each thread creates a new `ScoringAdapter()` which loads from `data/scoring_feedback.json`

```python
# WRONG - loads disk file in every thread!
def enrich_wrapper(item: CollectedItem):
    adapter = ScoringAdapter()  # ← Reads 1000s of entries from disk!
```

**Impact:**
- Each of 8 threads reads the same large file independently
- Massive I/O contention and wasted memory
- Enrichment will likely be *slower* than sequential due to overhead
- Loading existing feedback defeats the purpose of thread-local instances

**Fix Applied:** 
- Option 1 (Recommended): Load once, share immutable reference
- Option 2: Create empty adapters for accumulation during run
- See detailed fix in Phase 0 implementation below

### 🟠 MODERATE: CostTracker.save() Not Thread-Safe for Reads

**Problem:** While appends are locked, concurrent reads aren't:

```python
def save(self):
    with self._lock:
        batch = self.entries + self._pending  # ← Race: entries could be read elsewhere
        self._pending = []
```

**Impact:** Potential data corruption if another thread reads `self.entries` during parallel generation

**Fix Applied:** Make entries immutable or lock all reads/writes (see Phase 0 implementation)

### 🟡 MINOR: No Progress Indication in Parallel Mode

**Problem:** Sequential mode shows progress, parallel mode is silent

**Impact:** User can't see progress during long enrichment runs  
**Workaround:** Add callback-based progress or periodic status logging

### 🟡 MINOR: asyncio.get_event_loop() Deprecated

**Problem:** `asyncio.get_event_loop()` is deprecated in Python 3.10+

**Fix:** Use `asyncio.get_running_loop()` instead (will be applied in Phase 1)

### 🟡 MINOR: Hardcoded max_workers=8

**Problem:** May not be optimal for all systems

**Fix:** Base on workload type:
```python
# I/O-bound: more workers than CPUs
max_workers = min(max_workers or (os.cpu_count() or 4) * 2, 16)
```

## Implementation Plan

### Phase 0: Lock-Free Architecture (REQUIRED FIRST) - 1-2 days

**PRINCIPLE: Avoid locks by eliminating shared mutable state**

#### Strategy: Thread-Local Instances + Sequential Merge

**Pattern:**
1. Parallel phase: Each thread gets isolated instances (no sharing)
2. Sequential phase: Merge results single-threaded (no locks needed)

#### 1. CostTracker - Batch Pattern (THREAD-SAFE)
```python
# src/api/costs.py
from threading import Lock
from typing import List
import json
from pathlib import Path

class CostTracker:
    def __init__(self, ...):
        self._pending = []  # Accumulate during run
        self._lock = Lock()  # Protect both reads and writes
        self.entries = []  # Cached entries from startup
        self.load()
    
    def record_successful_generation(self, title, filename, costs):
        entry = GenerationCostEntry(...)
        
        # Lock only for fast list append
        with self._lock:
            self._pending.append(entry)
    
    def save(self):
        # Lock once, copy batch atomically
        with self._lock:
            batch = self.entries.copy()  # Atomic copy
            batch.extend(self._pending)
            self._pending = []
            self.entries = batch  # Update under lock
        
        # Slow I/O outside lock
        with open(self.data_file, 'w', encoding='utf-8') as f:
            json.dump([asdict(e) for e in batch], f, indent=2)
    
    def get_entries(self) -> List:
        """Thread-safe read of entries."""
        with self._lock:
            return self.entries.copy()  # Return copy, not reference
```

**Critical Changes:**
- Atomic copy under lock prevents data races
- `get_entries()` returns copy, not reference (prevents external mutations)
- All read/write access protected by lock

#### 2. ScoringAdapter - Thread-Local Pattern (WITH CRITICAL FIX)
```python
# src/enrichment/orchestrator.py
async def enrich_collected_items_async(items):
    """Each thread gets its own adapter - no sharing."""
    
    # CRITICAL FIX: Load once before parallel, don't load per-thread!
    # Option 1: Share immutable reference (preferred)
    base_patterns = load_patterns_once()  # Load outside thread pool
    
    def enrich_wrapper(item: CollectedItem) -> tuple[EnrichedItem | None, dict]:
        # Create per-thread adapter with empty feedback (accumulate during run)
        adapter = ScoringAdapter.__new__(ScoringAdapter)
        adapter.feedback_history = []  # Empty - accumulate from this run only
        adapter.learned_patterns = base_patterns  # Immutable, shared reference
        adapter.reference_quality = ReferenceQualityEvaluator()
        
        try:
            enriched = enrich_single_item(item, config, adapter)
            # Return both result and adapter state for merging
            return (enriched, adapter.get_feedback_data())
        except Exception as e:
            logger.error(f"Enrichment failed for {item.id}: {e}")
            return (None, {})
    
    # Parallel: isolated processing (no per-thread disk reads!)
    try:
        loop = asyncio.get_running_loop()  # Fixed: deprecated get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    max_workers = min(8, (os.cpu_count() or 4) * 2)  # Dynamic worker count
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            loop.run_in_executor(executor, enrich_wrapper, item)
            for item in items
        ]
        results = await asyncio.gather(*futures, return_exceptions=True)
    
    # Sequential: merge feedback (no locks needed)
    enriched_items = []
    final_adapter = ScoringAdapter()
    failed_count = 0
    
    for result in results:
        if isinstance(result, Exception):
            logger.error(f"Thread failed: {result}")
            failed_count += 1
            continue
        
        enriched, feedback_data = result
        if enriched:
            enriched_items.append(enriched)
            final_adapter.merge_feedback(feedback_data)
        else:
            failed_count += 1
    
    logger.info(f"Enrichment: {len(enriched_items)} succeeded, {failed_count} failed")
    
    # Single-threaded save
    final_adapter.update_learned_patterns()
    final_adapter.save_feedback()
    
    return enriched_items
```

**Critical Changes:**
- Load base patterns ONCE before thread pool (fixes major I/O contention)
- Create adapters with empty feedback (accumulate only from this run)
- Use immutable shared reference for learned patterns
- Fixed `asyncio.get_running_loop()` deprecation
- Dynamic worker count based on CPU count
- Better error handling with return_exceptions=True

#### 3. SemanticDeduplicator - Immutable Pattern
```python
# src/deduplication/semantic_dedup.py
class SemanticDeduplicator:
    def __init__(self, patterns_file=...):
        self.patterns_file = patterns_file
        # Load once at init - immutable during run
        self.patterns: list[DuplicationPattern] = self._load_patterns()
        # NO LOCK NEEDED - patterns are read-only
    
    def find_duplicates(self, items: list[CollectedItem]):
        """Read-only operation, no lock needed."""
        # Use self.patterns (immutable during this run)
        return self._find_with_patterns(items)
    
    def save_patterns(self):
        """Only called single-threaded at pipeline end."""
        atomic_write_json(self.patterns_file, 
                         [asdict(p) for p in self.patterns])
```

#### 4. DeduplicationFeedbackSystem - Similar Pattern
```python
# src/deduplication/dedup_feedback.py
class DeduplicationFeedbackSystem:
    def __init__(self):
        self.feedback_file = Path("data/dedup_feedback.json")
        self.feedback = self._load_feedback()  # Immutable during run
        # NO LOCK NEEDED
    
    def record_deduplication_session(self, ...):
        """Only called single-threaded at pipeline end."""
        # Build new feedback entry
        new_entry = {...}
        self.feedback.append(new_entry)
        atomic_write_json(self.feedback_file, self.feedback)
```

#### 5. Test thread safety
```bash
export PYTHON_GIL=0
# Run 10 times - check for race conditions
for i in {1..10}; do
  uv run pytest tests/ -v -k "thread"
  echo "Run $i complete"
done
```

### Phase 1: Collection Parallelization - 2-3 hours

**Expected gain:** 7-8 min → 2-3 min (4x speedup)

**Lock-free:** Each collector independent I/O, no shared state

#### Implementation

Add to `src/collectors/orchestrator.py`:
```python
async def collect_all_sources_async() -> list[CollectedItem]:
    """Parallel collection - isolated threads, no sharing."""
    config = get_config()
    loop = asyncio.get_event_loop()
    
    # Each wrapper independent - no mutation of shared state
    def collect_mastodon():
        for instance in config.mastodon_instances[:]:  # Read-only
            try:
                instance_config = PipelineConfig(
                    openai_api_key=config.openai_api_key,
                    mastodon_instances=[instance],
                    articles_per_run=config.articles_per_run,
                )
                return collect_from_mastodon_trending(instance_config)
            except Exception as e:
                logger.error(f"Mastodon {instance} failed: {e}")
        return []
    
    def collect_reddit_wrapper():
        try:
            return collect_from_reddit(config, limit=20)
        except Exception as e:
            logger.error(f"Reddit failed: {e}")
            return []
    
    def collect_hn_wrapper():
        try:
            return collect_from_hackernews(limit=30)
        except Exception as e:
            logger.error(f"HN failed: {e}")
            return []
    
    def collect_github_wrapper():
        try:
            return collect_from_github_trending(limit=20)
        except Exception as e:
            logger.error(f"GitHub failed: {e}")
            return []
    
    # Parallel: each thread isolated
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [
            loop.run_in_executor(executor, collect_mastodon),
            loop.run_in_executor(executor, collect_reddit_wrapper),
            loop.run_in_executor(executor, collect_hn_wrapper),
            loop.run_in_executor(executor, collect_github_wrapper),
        ]
        results = await asyncio.gather(*futures, return_exceptions=True)
    
    # Sequential merge - no lock needed
    items = []
    for result in results:
        if isinstance(result, list):
            items.extend(result)
    
    # Dedup reads immutable patterns - no lock
    return deduplicate_items(items)
```

#### Update CLI entry point
```python
# src/collectors/__main__.py
import asyncio

if __name__ == "__main__":
    items = asyncio.run(collect_all_sources_async())
    save_collected_items(items)
```

#### Test
```bash
export PYTHON_GIL=0
time uv run python -m src.collectors
# Should see ~2-3 min vs 7-8 min
```

### Phase 2: Enrichment Parallelization - 3-4 hours

**Expected gain:** 2-3 min → 1 min (2-3x speedup)

**Lock-free:** Thread-local adapters, sequential merge at end

⚠️ **IMPORTANT:** This phase depends on fixing the ScoringAdapter loading issue in Phase 0. Without the fix, enrichment will likely be slower than sequential due to I/O contention.

#### Implementation

The implementation is specified in Phase 0 section above (with the critical fixes). See the ScoringAdapter - Thread-Local Pattern section for the corrected version that:
- Loads patterns once before thread pool starts
- Uses immutable shared references
- Creates empty adapters for accumulation
- Properly handles exceptions in parallel workers
- Uses dynamic worker count

**Key Points:**
1. **DO NOT create ScoringAdapter() in enrich_wrapper** - this causes per-thread disk loads
2. **Load patterns once** before the thread pool starts
3. **Pass immutable reference** to each thread's adapter
4. **Accumulate feedback locally** in each thread
5. **Merge sequentially** at the end

**Alternate Implementation (if need more code detail):**

Add to `src/enrichment/orchestrator.py`:
```python
async def enrich_collected_items_async(
    items: list[CollectedItem]
) -> list[EnrichedItem]:
    """Parallel enrichment - per-thread adapters, no sharing."""
    config = get_config()
    
    def enrich_wrapper(item: CollectedItem) -> tuple[EnrichedItem | None, dict]:
        # Thread-local adapter - no sharing
        adapter = ScoringAdapter()
        
        try:
            enriched = enrich_single_item(item, config, adapter)
            # Return feedback data for sequential merge
            return (enriched, adapter.get_feedback_data())
        except Exception as e:
            logger.error(f"Enrichment failed for {item.id}: {e}")
            return (None, {})
    
    # Parallel: isolated processing
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor(max_workers=min(8, os.cpu_count() or 4)) as executor:
        futures = [
            loop.run_in_executor(executor, enrich_wrapper, item)
            for item in items
        ]
        results = await asyncio.gather(*futures)
    
    # Sequential: merge results (no lock needed)
    enriched_items = []
    final_adapter = ScoringAdapter()
    
    for enriched, feedback_data in results:
        if enriched:
            enriched_items.append(enriched)
            final_adapter.merge_feedback(feedback_data)
    
    # Single-threaded save
    final_adapter.update_learned_patterns()
    final_adapter.save_feedback()
    
    return enriched_items
```

**Required:** Add `get_feedback_data()` and `merge_feedback()` to ScoringAdapter:
```python
# src/enrichment/adaptive_scoring.py
class ScoringAdapter:
    def get_feedback_data(self) -> dict:
        """Export feedback for merging."""
        return {
            'feedback': self.feedback[:],  # Copy
            'patterns': self.patterns[:],
        }
    
    def merge_feedback(self, data: dict):
        """Merge feedback from thread-local adapter."""
        self.feedback.extend(data.get('feedback', []))
        self.patterns.extend(data.get('patterns', []))
```

#### Update CLI entry point
```python
# src/enrichment/__main__.py
import asyncio

if __name__ == "__main__":
    items = load_collected_items()
    enriched = asyncio.run(enrich_collected_items_async(items))
    save_enriched_items(enriched)
```

#### Test
```bash
export PYTHON_GIL=0
time uv run python -m src.enrichment
# Verify no race conditions, files intact

# Run 10 times to catch race conditions
for i in {1..10}; do
  export PYTHON_GIL=0
  uv run python -m src.enrichment
  if [ $? -ne 0 ]; then
    echo "Run $i FAILED"
    break
  fi
  echo "Run $i succeeded"
done
```

### Phase 3: Benchmarking & Metrics - 1 day

**CRITICAL:** Validate that free-threading actually helps. Add timing instrumentation:

```python
# src/utils/timing.py
import time
from contextlib import contextmanager
import logging

logger = logging.getLogger(__name__)

@contextmanager
def time_operation(name: str):
    """Context manager to measure operation duration."""
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed = time.perf_counter() - start
        logger.info(f"{name} took {elapsed:.2f}s")

# Usage in enrichment:
with time_operation("Enrichment (parallel)"):
    enriched = await enrich_collected_items_async(items)
```

#### Benchmarking Tests
```python
# tests/test_threading_performance.py
def test_parallel_speedup():
    """Verify parallel is actually faster."""
    items = load_test_items(50)
    
    start = time.perf_counter()
    seq_result = enrich_collected_items(items)  # Sequential
    seq_time = time.perf_counter() - start
    
    start = time.perf_counter()
    async_result = asyncio.run(enrich_collected_items_async(items))  # Parallel
    async_time = time.perf_counter() - start
    
    speedup = seq_time / async_time
    logger.info(f"Speedup: {speedup:.2f}x (seq: {seq_time:.2f}s, async: {async_time:.2f}s)")
    
    # Should be significantly faster
    assert speedup > 1.3, f"Expected >1.3x speedup, got {speedup:.2f}x"

def test_no_race_conditions():
    """Run enrichment 10 times to catch race conditions."""
    items = load_test_items(50)
    
    for i in range(10):
        result = asyncio.run(enrich_collected_items_async(items))
        assert len(result) > 0, f"Run {i}: No results returned"
        # Verify output files are valid
        assert verify_json_integrity("data/scoring_feedback.json")
        assert verify_json_integrity("data/generation_costs.json")
```

### Phase 4: Integration Testing - 1 day

#### Full pipeline test
```bash
export PYTHON_GIL=0
echo "Sequential vs Parallel comparison:"
echo ""
echo "=== RUN 1: Baseline (sequential mode) ==="
USE_PARALLEL=false time uv run python -m src.collectors
USE_PARALLEL=false time uv run python -m src.enrichment  
time uv run python -m src.generate --max-articles 3

echo ""
echo "=== RUN 2: Optimized (parallel mode) ==="
USE_PARALLEL=true time uv run python -m src.collectors
USE_PARALLEL=true time uv run python -m src.enrichment  
time uv run python -m src.generate --max-articles 3
```

#### Stress test (10 consecutive runs)
```bash
# Catch race conditions and data corruption
for i in {1..10}; do
  echo "=== Integration Test Run $i ==="
  export PYTHON_GIL=0
  
  uv run python -m src.collectors || { echo "Collection failed"; break; }
  uv run python -m src.enrichment || { echo "Enrichment failed"; break; }
  
  # Verify data integrity
  python3 -c "import json; json.load(open('data/scoring_feedback.json'))" || { echo "Corrupted feedback file"; break; }
  python3 -c "import json; json.load(open('data/generation_costs.json'))" || { echo "Corrupted costs file"; break; }
  
  echo "Run $i: ✓ Success"
  echo ""
done
```

#### Verify outputs
- Check for corrupted JSON files
- Verify no duplicate articles
- Check cost tracking accuracy
- Monitor memory usage

## Expected Results

### Best Case (All fixes applied perfectly)
- Collect: 7-8 min → 2-3 min (3.5-4x)
- Enrich: 2-3 min → 45s (3-4x)
- Generate: 2-3 min (unchanged)
- **Total: ~11-12 min → ~4-5 min (2.4-3x speedup)**

### Realistic Case (Production-ready with all mitigations)
- Collect: 7-8 min → 2.5 min (2.8-3.2x) 
- Enrich: 2-3 min → 1 min (2-3x)
- Generate: 2-3 min (unchanged)
- **Total: ~11-12 min → ~5.5-6.5 min (1.8-2x speedup)**

### Current Status (with ScoringAdapter bug)
- Collect: Measured 1.54x speedup ✓
- Enrich: Likely *slower* due to per-thread disk loads ✗
- **Total: Probably only 1.2-1.3x speedup**

⚠️ **Critical:** Enrichment speedup depends entirely on fixing the ScoringAdapter loading issue

## Rollback Plan

If issues arise:
1. Keep `collect_all_sources()` and `enrich_collected_items()` as fallbacks
2. Add feature flag: `USE_PARALLEL=false` to disable (default: false until Phase 3 passes)
3. Monitor for 1 week before removing sequential code
4. Automated fallback: If more than 20% of items fail in parallel, auto-switch to sequential

### Feature Flag Implementation
```python
# src/config.py or environment
import os

USE_PARALLEL = os.getenv('USE_PARALLEL', 'false').lower() == 'true'
PARALLEL_MIN_ITEMS = 20  # Only use parallel if >= 20 items
PARALLEL_MAX_WORKERS = int(os.getenv('PARALLEL_MAX_WORKERS', '8'))

# src/enrichment/orchestrator.py
def enrich_collected_items(items, use_parallel=None):
    if use_parallel is None:
        use_parallel = USE_PARALLEL and len(items) >= PARALLEL_MIN_ITEMS
    
    if use_parallel:
        logger.info(f"Using parallel enrichment with {PARALLEL_MAX_WORKERS} workers")
        return asyncio.run(enrich_collected_items_async(items))
    else:
        logger.info("Using sequential enrichment")
        return enrich_collected_items_sequential(items)
```

## Success Criteria

### Phase 0 (Architecture)
- [ ] ScoringAdapter loads patterns once, not per-thread
- [ ] CostTracker all read/write operations thread-safe
- [ ] No locks held during slow I/O operations
- [ ] Asyncio uses `get_running_loop()` instead of deprecated `get_event_loop()`

### Phase 1-2 (Implementation)
- [ ] No race conditions in 10 consecutive runs
- [ ] No corrupted data files (JSON integrity checks)
- [ ] No duplicate articles generated
- [ ] Cost tracking accurate (±5%)

### Phase 3 (Benchmarking)
- [ ] Enrichment speedup ≥ 2.0x measured locally
- [ ] Collection speedup ≥ 2.8x measured locally
- [ ] Overall pipeline speedup ≥ 1.8x measured locally
- [ ] Memory usage stays within ±15% of sequential

### Phase 4 (Production)
- [ ] 10 consecutive integration tests all pass
- [ ] No data corruption detected
- [ ] GitHub Actions workflow completes successfully
- [ ] Feature flag `USE_PARALLEL=true` works correctly
- [ ] Seamless fallback to sequential mode works

## Architecture Summary

**Lock-Free Concurrency Pattern:**

```
┌─────────────────────────────────────────────────┐
│  Phase 1: Parallel Processing (NO LOCKS)       │
├─────────────────────────────────────────────────┤
│  Thread 1: collect_mastodon()                   │
│    └─> Returns list[CollectedItem]             │
│  Thread 2: collect_reddit()                     │
│    └─> Returns list[CollectedItem]             │
│  Thread 3: collect_hn()                         │
│    └─> Returns list[CollectedItem]             │
│  Thread 4: collect_github()                     │
│    └─> Returns list[CollectedItem]             │
│                                                  │
│  No shared state - each thread isolated         │
└─────────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────┐
│  Phase 2: Sequential Merge (NO LOCKS NEEDED)   │
├─────────────────────────────────────────────────┤
│  all_items = []                                 │
│  for result in results:                         │
│      all_items.extend(result)                   │
│                                                  │
│  Single-threaded - inherently safe              │
└─────────────────────────────────────────────────┘
```

**Key Principles Applied:**

1. **Immutable Config** - Read-only during parallel phase
2. **Load Once, Share Immutable** - Patterns loaded before thread pool (FIX for ScoringAdapter)
3. **Thread-Local Accumulation** - Each thread accumulates feedback locally, not reading shared state
4. **Sequential Merge** - Combine results single-threaded
5. **Atomic Batch Writes** - Copy under lock, I/O outside lock
6. **No Shared Mutable State** - Eliminate race conditions by design

**Locks Only For:**
- CostTracker list operations (< 1ms hold time)
- All copy/update operations atomic
- Everything else is lock-free

**Why This Works:**
- Collection: Pure I/O, independent sources, no shared state
- Enrichment: Per-item processing, thread-local adapters, immutable patterns
- Merge: Single-threaded, no contention
- Writes: Batched at end, minimal lock time
- **Critical Fix**: Patterns loaded once prevents per-thread disk I/O

**Known Issues & Mitigations:**

| Issue | Severity | Mitigation | Status |
|-------|----------|-----------|--------|
| ScoringAdapter per-thread loads | 🔴 MAJOR | Load once, share immutable | Phase 0 |
| CostTracker race conditions | 🟠 MODERATE | Atomic operations under lock | Phase 0 |
| No progress indication | 🟡 MINOR | Add timing callbacks | Phase 3 |
| Deprecated asyncio API | 🟡 MINOR | Use get_running_loop() | Phase 1-2 |
| Code duplication | 🟡 MINOR | Extract common logic | Phase 3 |
| No benchmarking | 🟡 MINOR | Add perf tests | Phase 3 |
