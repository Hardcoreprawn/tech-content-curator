"""Worker configuration for parallel processing.

Intelligently determines optimal worker count based on:
- CPU count (available cores)
- Environment (CI/GitHub Actions vs local/production)
- API rate limits (OpenAI: 3-4 concurrent requests)
- Explicit overrides via environment variables

This ensures:
- Local development: Maximum parallelism (up to CPU count / 2)
- CI/GitHub Actions: Conservative (2 workers max)
- Production: Safe defaults (4 workers)
- Enrichment: Capped at API rate limits (4 workers)
"""

import os


def get_cpu_count() -> int:
    """Get CPU count with fallback to 4 if unavailable."""
    return os.cpu_count() or 4


def is_ci_environment() -> bool:
    """Detect if running in CI/GitHub Actions environment."""
    return os.getenv("GITHUB_ACTIONS") == "true"


def get_optimal_worker_count(
    use_case: str = "enrichment", max_limit: int | None = None
) -> int:
    """Determine optimal worker count based on environment and use case.

    Args:
        use_case: 'enrichment' (API-limited) or 'collection' (I/O-bound)
        max_limit: Maximum workers to use (for API rate limits, etc.)

    Returns:
        Optimal number of workers for the environment

    Priority:
        1. WORKER_COUNT env var (explicit override)
        2. Use case specific limits (enrichment: API rate limit)
        3. Environment detection (CI vs local)
        4. CPU count
        5. Sensible defaults

    Examples:
        Local (16 cores, enrichment):
            - WORKER_COUNT not set
            - Not in CI
            - cpu_count = 16
            - Returns: min(4, 8) = 4 (API limited)

        Local (16 cores, collection):
            - WORKER_COUNT not set
            - Not in CI
            - cpu_count = 16
            - Returns: min(4, 8) = 4 (4 sources)

        GitHub Actions (2 cores, enrichment):
            - WORKER_COUNT not set
            - GITHUB_ACTIONS=true
            - cpu_count = 2
            - Returns: min(4, 2) = 2 (conservative)

        Explicit override (any environment):
            - WORKER_COUNT=16
            - Returns: 16 (user knows what they're doing)
    """
    # Priority 1: Explicit override via environment variable
    if env_workers := os.getenv("WORKER_COUNT"):
        try:
            workers = int(env_workers)
            return workers
        except ValueError:
            # Invalid value, fall through to auto-detect
            pass

    # Get CPU count
    cpu_count = get_cpu_count()

    # Detect environment
    in_ci = is_ci_environment()

    # Priority 2: Use case specific limits via dispatch
    def _calc_enrichment_workers() -> int:
        """Calculate workers for enrichment (I/O-bound, API-limited).

        Threads spend 95% time waiting on API responses.
        OpenAI SDK handles 429 rate limit errors with exponential backoff.
        """
        if max_limit:
            # Respect explicit hard limit if provided
            return min(cpu_count * 4, max_limit)

        # Both CI and local: use 4x CPU for I/O-bound work
        # Empirically: 4x gives best throughput without overwhelming API
        # 16-core: 64 workers → 1.07 items/sec vs 16 workers → 0.38 items/sec
        return cpu_count * 4

    def _calc_collection_workers() -> int:
        """Calculate workers for collection (I/O-bound, network I/O).

        Not API-limited like enrichment, but still I/O-bound.
        """
        if in_ci:
            # GitHub Actions: Conservative (2-4 cores typical)
            return min(4, cpu_count)
        else:
            # Local/production: More aggressive
            # (cpu_count // 2) allows other processes to run
            cpu_workers = max(1, cpu_count // 2)
            if max_limit:
                cpu_workers = min(cpu_workers, max_limit)
            return cpu_workers

    # Type-safe dispatch
    use_case_calculators = {
        "enrichment": _calc_enrichment_workers,
        "collection": _calc_collection_workers,
    }

    calculator = use_case_calculators.get(use_case)
    if calculator:
        return calculator()

    # Default: conservative safe choice
    return min(4, cpu_count)


def log_worker_config(use_case: str, workers: int, extra: dict | None = None) -> dict:
    """Generate logging data for worker configuration.

    Returns dict suitable for use as 'extra' in logger calls.
    """
    cpu = get_cpu_count()
    ci = is_ci_environment()

    log_data = {
        "phase": "worker_config",
        "use_case": use_case,
        "worker_count": workers,
        "cpu_count": cpu,
        "environment": "ci" if ci else "local",
    }

    if extra:
        log_data.update(extra)

    return log_data
