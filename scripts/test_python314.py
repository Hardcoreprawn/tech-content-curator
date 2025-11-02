"""Test script for Python 3.14 free-threading and modular refactoring.

Run this to verify:
1. Python 3.14 is installed
2. Free-threading is available and enabled
3. New modular imports work
4. Async generation works

Usage:
    # Test with GIL enabled (default)
    python scripts/test_python314.py

    # Test with free-threading (Python 3.14+)
    PYTHON_GIL=0 python scripts/test_python314.py

    # Or use CLI flag
    python --gil=0 scripts/test_python314.py
"""

import sys
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def check_python_version() -> bool:
    """Check if Python 3.14+ is installed."""
    print("=" * 60)
    print("Python Version Check")
    print("=" * 60)

    version = sys.version_info
    print(f"Python version: {version.major}.{version.minor}.{version.micro}")

    if version < (3, 14):
        print("❌ Python 3.14+ is required for free-threading")
        print(f"   Current version: {version.major}.{version.minor}")
        print("\nTo upgrade:")
        print("  - pyenv install 3.14.0")
        print("  - pyenv local 3.14.0")
        return False

    print("✓ Python 3.14+ detected")
    return True


def check_gil_status() -> bool:
    """Check if GIL is enabled or disabled."""
    print("\n" + "=" * 60)
    print("GIL Status Check")
    print("=" * 60)

    if not hasattr(sys, "_is_gil_enabled"):
        print("❌ sys._is_gil_enabled not available")
        print("   This Python build does not support free-threading")
        print("   Note: Standard Python 3.14 builds have GIL enabled by default")
        print("   You need a special build with --disable-gil to use free-threading")
        return False

    try:
        gil_enabled = sys._is_gil_enabled()
    except Exception as e:
        print(f"❌ Error checking GIL status: {e}")
        print("   This Python build does not support free-threading")
        return False

    if gil_enabled:
        print("⚠️  GIL is ENABLED")
        print("   To enable free-threading:")
        print("   - export PYTHON_GIL=0")
        print("   - Or: python --gil=0 your_script.py")
        return False
    else:
        print("✓ GIL is DISABLED - Free-threading active!")
        return True


def test_imports() -> bool:
    """Test that new modular imports work."""
    print("\n" + "=" * 60)
    print("Module Import Check")
    print("=" * 60)

    try:
        from src.pipeline.illustration_service import (
            ConceptSectionMatch,
            IllustrationResult,
            IllustrationService,
        )

        print("✓ illustration_service.py imports work")

        from src.pipeline.diversity_selector import select_diverse_candidates

        print("✓ diversity_selector.py imports work")

        from src.pipeline.orchestrator import (
            generate_articles_async,
            generate_articles_from_enriched,
            generate_single_article,
        )

        print("✓ orchestrator_slim.py imports work")

        print("\n✓ All modular imports successful!")
        return True

    except ImportError as e:
        print(f"❌ Import failed: {e}")
        return False


def test_async_available() -> bool:
    """Test that async generation is available."""
    print("\n" + "=" * 60)
    print("Async Generation Check")
    print("=" * 60)

    try:
        from src.pipeline.orchestrator import generate_articles_async

        print("✓ Async generation function available")

        # Check if it's an async function
        import inspect

        if inspect.iscoroutinefunction(generate_articles_async):
            print("✓ Function is properly async")
            return True
        else:
            print("❌ Function is not async")
            return False

    except ImportError as e:
        print(f"❌ Async import failed: {e}")
        return False


def benchmark_threading() -> None:
    """Quick benchmark to show threading benefits."""
    print("\n" + "=" * 60)
    print("Threading Benchmark")
    print("=" * 60)

    import threading
    from concurrent.futures import ThreadPoolExecutor

    def cpu_intensive_task(n: int) -> int:
        """Simulate CPU-intensive work."""
        result = 0
        for i in range(n):
            result += i**2
        return result

    iterations = 10_000_000
    num_workers = 4

    # Sequential benchmark
    start = time.time()
    results = [cpu_intensive_task(iterations) for _ in range(num_workers)]
    sequential_time = time.time() - start

    # Parallel benchmark
    start = time.time()
    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        results = list(executor.map(cpu_intensive_task, [iterations] * num_workers))
    parallel_time = time.time() - start

    speedup = sequential_time / parallel_time

    print(f"Sequential time: {sequential_time:.2f}s")
    print(f"Parallel time:   {parallel_time:.2f}s")
    print(f"Speedup:         {speedup:.2f}x")

    if speedup > 2.0:
        print("✓ Excellent parallelism - free-threading is working!")
    elif speedup > 1.5:
        print("⚠️  Moderate parallelism - check if GIL is disabled")
    else:
        print("❌ Limited parallelism - GIL is likely enabled")
        print("   Try: export PYTHON_GIL=0")


def main() -> None:
    """Run all checks."""
    print("\n" + "=" * 60)
    print("Python 3.14 Free-Threading Test Suite")
    print("=" * 60)

    checks_passed = 0
    total_checks = 5

    if check_python_version():
        checks_passed += 1

    if check_gil_status():
        checks_passed += 1

    if test_imports():
        checks_passed += 1

    if test_async_available():
        checks_passed += 1

    # Always run benchmark
    try:
        benchmark_threading()
        checks_passed += 1
    except Exception as e:
        print(f"❌ Benchmark failed: {e}")

    # Summary
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"Checks passed: {checks_passed}/{total_checks}")

    if checks_passed == total_checks:
        print("\n✓ All checks passed! Ready for Python 3.14 free-threading!")
    elif checks_passed >= 3:
        print("\n⚠️  Most checks passed, but some improvements recommended")
    else:
        print("\n❌ Several checks failed. See recommendations above.")

    print("\n" + "=" * 60)
    print("Next Steps")
    print("=" * 60)

    if sys.version_info < (3, 14):
        print("1. Install Python 3.14:")
        print("   pyenv install 3.14.0")
        print("   pyenv local 3.14.0")

    if hasattr(sys, "_is_gil_enabled") and sys._is_gil_enabled():
        print("2. Enable free-threading:")
        print("   export PYTHON_GIL=0")
        print("   python scripts/test_python314.py")

    print("3. Try async article generation:")
    print("   See docs/MODULAR-REFACTOR-PYTHON314.md")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback

        traceback.print_exc()
