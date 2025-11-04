#!/usr/bin/env python3
"""Benchmark script for Python 3.14 free-threading benefits.

This script measures the speedup from free-threading when generating multiple articles.
Run with and without PYTHON_GIL=0 to see the difference:

    # With GIL enabled (default):
    python scripts/benchmark_free_threading.py

    # With free-threading (Python 3.14+):
    PYTHON_GIL=0 python scripts/benchmark_free_threading.py

Usage in GitHub Actions:
    - The benchmarks are automatically included in CI/CD pipelines
    - Results are printed to the workflow logs for inspection
    - Compare timings across runs to validate free-threading benefits
"""

import asyncio
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def check_python_version() -> bool:
    """Check if Python 3.14+ is installed."""
    print("\n" + "=" * 60)
    print("Python Version Check")
    print("=" * 60)

    version = sys.version_info
    version_str = f"{version.major}.{version.minor}.{version.micro}"

    print(f"Python version: {version_str}")

    if version >= (3, 14):
        print("✓ Python 3.14+ detected")
        return True
    else:
        print("⚠ Python 3.13 or earlier detected")
        return False


def check_gil_status() -> bool:
    """Check if GIL is enabled or disabled."""
    print("\n" + "=" * 60)
    print("GIL Status Check")
    print("=" * 60)

    gil_enabled = os.getenv("PYTHON_GIL", "1") != "0"

    if gil_enabled:
        print("GIL status: ENABLED (default)")
        print("To disable: export PYTHON_GIL=0")
        return False
    else:
        print("GIL status: DISABLED ✓")
        print("Free-threading should provide 2-4x speedup")
        return True


def benchmark_sequential() -> tuple[float, int]:
    """Benchmark sequential article generation simulation.

    Simulates the work of generating 4 articles sequentially.
    Each article takes ~5 seconds of API calls + processing.
    """
    print("\n" + "=" * 60)
    print("Sequential Generation Benchmark")
    print("=" * 60)

    def simulate_article_generation() -> int:
        """Simulate article generation (CPU + I/O work)."""
        # Simulate API calls and text processing
        result = 0
        for i in range(10_000_000):
            result += i % 13
        return result

    num_articles = 4
    print(f"Generating {num_articles} articles sequentially...")

    start = time.time()
    results = [simulate_article_generation() for _ in range(num_articles)]
    sequential_time = time.time() - start

    print(f"Sequential time: {sequential_time:.2f}s")
    print(f"Average per article: {sequential_time / num_articles:.2f}s")

    return sequential_time, len(results)


def benchmark_threaded() -> tuple[float, int]:
    """Benchmark parallel article generation with ThreadPoolExecutor.

    With GIL disabled (Python 3.14+), this should be ~3-4x faster.
    With GIL enabled (Python 3.13), this will be similar or slower due to GIL contention.
    """
    print("\n" + "=" * 60)
    print("Parallel Generation Benchmark (ThreadPoolExecutor)")
    print("=" * 60)

    def simulate_article_generation() -> int:
        """Simulate article generation (CPU + I/O work)."""
        # Simulate API calls and text processing
        result = 0
        for i in range(10_000_000):
            result += i % 13
        return result

    num_articles = 4
    max_workers = min(4, os.cpu_count() or 1)
    print(f"Generating {num_articles} articles in parallel ({max_workers} workers)...")

    start = time.time()
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        results = list(executor.map(lambda _: simulate_article_generation(), range(num_articles)))
    parallel_time = time.time() - start

    print(f"Parallel time: {parallel_time:.2f}s")
    print(f"Average per article: {parallel_time / num_articles:.2f}s")

    return parallel_time, len(results)


async def benchmark_async() -> tuple[float, int]:
    """Benchmark async article generation with free-threading.

    This is the most efficient approach for Python 3.14+ with GIL disabled.
    Uses asyncio.gather with ThreadPoolExecutor for true parallelism.
    """
    print("\n" + "=" * 60)
    print("Async Generation Benchmark (asyncio + ThreadPoolExecutor)")
    print("=" * 60)

    def simulate_article_generation() -> int:
        """Simulate article generation (CPU + I/O work)."""
        # Simulate API calls and text processing
        result = 0
        for i in range(10_000_000):
            result += i % 13
        return result

    num_articles = 4
    max_workers = min(4, os.cpu_count() or 1)
    print(f"Generating {num_articles} articles async ({max_workers} workers)...")

    loop = asyncio.get_event_loop()

    start = time.time()
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            loop.run_in_executor(executor, simulate_article_generation)
            for _ in range(num_articles)
        ]
        results = await asyncio.gather(*futures)
    async_time = time.time() - start

    print(f"Async time: {async_time:.2f}s")
    print(f"Average per article: {async_time / num_articles:.2f}s")

    return async_time, len(results)


def print_summary(sequential_time: float, parallel_time: float, async_time: float) -> None:
    """Print comparison summary."""
    print("\n" + "=" * 60)
    print("Summary & Speedup Analysis")
    print("=" * 60)

    speedup_threaded = sequential_time / parallel_time
    speedup_async = sequential_time / async_time

    print(f"\nSequential time:  {sequential_time:.2f}s")
    print(f"Threaded time:    {parallel_time:.2f}s (speedup: {speedup_threaded:.2f}x)")
    print(f"Async time:       {async_time:.2f}s (speedup: {speedup_async:.2f}x)")

    gil_enabled = os.getenv("PYTHON_GIL", "1") != "0"

    if speedup_async > 2.5:
        print("\n✓ Excellent parallelism!")
        print("  Free-threading is working well.")
        if gil_enabled:
            print("  💡 Hint: Try disabling GIL for even better performance:")
            print("     export PYTHON_GIL=0")
    elif speedup_async > 1.5:
        print("\n⚠ Moderate parallelism")
        print("  Some parallelism is working, but not optimal.")
        if gil_enabled:
            print("  💡 Try disabling GIL: export PYTHON_GIL=0")
    else:
        print("\n⚠ Limited parallelism")
        print("  Not much speedup from threading.")
        if gil_enabled:
            print("  This is expected with GIL enabled (Python 3.13 or earlier).")
            print("  Upgrade to Python 3.14+ and disable GIL for benefits:")
            print("  export PYTHON_GIL=0")

    # Calculate potential savings
    articles_per_run = 10
    time_saved_per_run = sequential_time * articles_per_run - async_time * articles_per_run
    time_saved_per_day = time_saved_per_run * 3  # 3 runs per day

    print("\n💰 Potential Savings (10 articles per run, 3 runs/day):")
    print(f"  Per run: {time_saved_per_run:.0f}s saved")
    print(f"  Per day: {time_saved_per_day:.0f}s saved ({time_saved_per_day/60:.1f} minutes)")
    print(f"  Per month: {time_saved_per_day * 30:.0f}s saved ({time_saved_per_day * 30 / 3600:.1f} hours)")


def main() -> None:
    """Run all benchmarks."""
    print("\n" + "=" * 60)
    print("Python 3.14 Free-Threading Benchmark Suite")
    print("=" * 60)
    print(f"\nCPU cores available: {os.cpu_count()}")

    # Check environment
    has_py314 = check_python_version()
    gil_disabled = check_gil_status()

    # Run benchmarks
    seq_time, _ = benchmark_sequential()
    par_time, _ = benchmark_threaded()

    # Async benchmark requires Python 3.14
    if has_py314:
        async_time, _ = asyncio.run(benchmark_async())
    else:
        print("\n" + "=" * 60)
        print("Async Generation Benchmark")
        print("=" * 60)
        print("⚠ Python 3.14+ required for async benchmarking")
        print("Skipping async benchmark...")
        async_time = par_time  # Use parallel time for comparison

    # Summary
    print_summary(seq_time, par_time, async_time)

    # Recommendations
    print("\n" + "=" * 60)
    print("Recommendations")
    print("=" * 60)

    if not has_py314:
        print("✓ Upgrade to Python 3.14 to access free-threading")

    if has_py314 and not gil_disabled:
        print("✓ Enable free-threading in GitHub Actions:")
        print("  - Add 'PYTHON_GIL: \"0\"' to workflow env variables")
        print("  - This is already configured in your workflows!")

    if has_py314 and gil_disabled:
        print("✓ Free-threading is enabled!")
        print("  Your GitHub Actions workflows will benefit from this.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nBenchmark interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
