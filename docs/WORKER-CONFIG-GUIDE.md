# Dynamic Worker Configuration Guide

## Overview

The `worker_config.py` module implements intelligent worker count selection based on environment, CPU availability, and API rate limits. This allows the pipeline to maximize parallelism on powerful local machines while being conservative in resource-constrained CI environments.

## Quick Start

The worker configuration is **automatic** and requires no changes to your workflow:

```bash
# Local machine (16-core): Uses 8 workers for collection, 4 for enrichment
python -m src.main

# GitHub Actions (2-core): Automatically uses 2 workers (conservative)
python -m src.main

# Override for testing (force 16 workers): 
WORKER_COUNT=16 python -m src.main
```

## How It Works

### Priority Order

Worker count is determined using this priority order:

1. **Explicit Override**: `WORKER_COUNT` environment variable
   - Highest priority - allows testing/tuning without code changes
   - Example: `WORKER_COUNT=12 python -m src.main`

2. **Use Case Limits**: Pipeline-specific constraints
   - **Enrichment**: Max 4 workers (limited by OpenAI API rate limit of 3-4 concurrent requests)
   - **Collection**: Max 4 workers per source limit (but can go higher due to I/O-bound nature)

3. **Environment Detection**: `is_ci_environment()`
   - **GitHub Actions**: Conservative 2 workers (typical 2-4 core limit)
   - **Local**: Aggressive (cpu_count // 2, then capped by API limits)

4. **CPU Count**: `os.cpu_count()`
   - Local: `min(cpu_count // 2, use_case_limit)`
   - CI: `min(2, cpu_count, use_case_limit)`

5. **Sensible Defaults**: Fallback to 4 if all else fails

### Use Case Logic

#### Enrichment Pipeline
```python
optimal_workers = get_optimal_worker_count(use_case="enrichment", max_limit=max_workers)
```

- **Local (16-core)**: 4 workers (API-limited)
- **CI (2-core)**: 2 workers (conservative)
- **Override**: `WORKER_COUNT=8` forces 8 workers

#### Collection Pipeline
```python
optimal_workers = get_optimal_worker_count(use_case="collection", max_limit=4)
```

- **Local (16-core)**: 8 workers (I/O-bound, no API limit)
- **CI (2-core)**: 2 workers (conservative)
- **Override**: `WORKER_COUNT=4` forces 4 workers

## Environment Detection

The module detects CI environments via the `GITHUB_ACTIONS` environment variable:

```python
def is_ci_environment() -> bool:
    return os.getenv("GITHUB_ACTIONS", "false").lower() == "true"
```

This is automatically set by GitHub Actions. For other CI systems, you can manually set `GITHUB_ACTIONS=true`.

## Logging

Worker configuration is logged at startup with structured metrics:

```
[INFO] src.enrichment.orchestrator - Enrichment phase starting
  phase=enrichment
  event=orchestration_start
  worker_count=4
  environment=local
  cpu_count=16
  reason=api_rate_limited
```

## Configuration in Code

### Enrichment Orchestrator
```python
from ..utils.worker_config import get_optimal_worker_count, log_worker_config

optimal_workers = get_optimal_worker_count(use_case="enrichment", max_limit=max_workers)
logger.info(
    "Enrichment phase starting",
    extra=log_worker_config("enrichment", optimal_workers),
)

with ThreadPoolExecutor(max_workers=optimal_workers) as executor:
    # ... enrichment logic
```

### Collection Orchestrator
```python
from ..utils.worker_config import get_optimal_worker_count, log_worker_config

optimal_workers = get_optimal_worker_count(use_case="collection", max_limit=4)
logger.info(
    "Parallel collection starting with optimal worker configuration",
    extra=log_worker_config("collection", optimal_workers),
)

with ThreadPoolExecutor(max_workers=optimal_workers) as executor:
    # ... collection logic
```

## Testing Worker Configuration

### Test Local Performance
```bash
# Default: Use smart detection (8 workers for collection on 16-core)
time python -m src.main

# Force single-threaded for comparison
WORKER_COUNT=1 time python -m src.main

# Force maximum parallelism
WORKER_COUNT=16 time python -m src.main
```

### Test CI Behavior Locally
```bash
# Simulate GitHub Actions (2 workers)
GITHUB_ACTIONS=true python -m src.main

# Override CI detection for testing
GITHUB_ACTIONS=true WORKER_COUNT=8 python -m src.main
```

### View Worker Configuration
The logs will show the determined worker count:
```
[INFO] src.collectors.orchestrator - Parallel collection starting with optimal worker configuration
  phase=collection
  event=worker_config
  worker_count=8
  environment=local
  cpu_count=16
```

## Performance Expectations

### Local Machine (16-core)
- **Collection**: 8 workers (I/O-bound, no API limit)
- **Enrichment**: 4 workers (API-limited by OpenAI)
- **Expected**: ~2x speedup for collection, API-limited for enrichment

### GitHub Actions (2-core)
- **Collection**: 2 workers (conservative)
- **Enrichment**: 2 workers (conservative)
- **Expected**: Minimal speedup (small machine), but stable and conservative

## Advanced Usage

### Custom Use Cases
To add support for new use cases, extend `get_optimal_worker_count()`:

```python
elif use_case == "my_custom_use_case":
    if in_ci:
        return min(2, cpu_count)
    else:
        return min(cpu_count // 2, 8)  # Custom limit of 8 workers
```

### Benchmarking
The module logs worker configuration, so you can benchmark different setups:

```bash
# Baseline
time python -m src.main > baseline.txt 2>&1

# Half workers
WORKER_COUNT=$(($(nproc) / 4)) time python -m src.main > half.txt 2>&1

# Double workers
WORKER_COUNT=$(($(nproc))) time python -m src.main > double.txt 2>&1
```

## Troubleshooting

### Workers not increasing on local machine
1. Check CPU count: `python -c "import os; print(f'CPU count: {os.cpu_count()}')"`
2. Check environment detection: Set `GITHUB_ACTIONS=true` to disable CI-conservative mode
3. Force worker count: Use `WORKER_COUNT=X` to override detection

### Workers still limited despite high CPU count
1. **Enrichment is API-limited**: Max 4 workers due to OpenAI rate limits (by design)
2. **Collection hitting network limit**: May be bandwidth-bound, not CPU-bound
3. **Check logs**: Look for `worker_count` and `reason` in structured logs

### CI running slowly
1. Default CI is conservative (2 workers) to avoid resource exhaustion
2. Increase with: `WORKER_COUNT=4` in CI environment
3. Monitor resource usage - may be hitting memory or bandwidth limits

## Related Documentation

- [LOGGING-GUIDE.md](LOGGING-GUIDE.md) - Comprehensive logging setup
- [FREE-THREADING-OPTIMIZATION.md](FREE-THREADING-OPTIMIZATION.md) - Python 3.14t no-GIL setup
- [src/utils/worker_config.py](../src/utils/worker_config.py) - Source implementation

## Summary

Dynamic worker configuration:
- ✅ Maximizes local performance (8 workers for I/O, 4 for API)
- ✅ Conservative in CI (2 workers)
- ✅ Easily testable with `WORKER_COUNT=X` override
- ✅ Logged for observability
- ✅ No code changes needed for environment-specific behavior
