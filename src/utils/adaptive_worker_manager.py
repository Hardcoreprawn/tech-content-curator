"""Adaptive worker count management based on API backoff and CPU headroom.

Dynamically adjusts worker count during execution to maximize throughput while
respecting API rate limits and available CPU resources.
"""

import logging
import os
import time
from dataclasses import dataclass, field
from threading import Lock

logger = logging.getLogger(__name__)


@dataclass
class WorkerMetrics:
    """Metrics for adaptive worker management."""

    worker_count: int
    start_time: float = field(default_factory=time.time)
    completed_items: int = 0
    rate_limit_errors: int = 0
    last_rate_limit_time: float | None = None
    total_errors: int = 0
    last_adjustment_time: float = field(default_factory=time.time)
    adjustment_history: list[tuple[float, int, str]] = field(default_factory=list)
    _lock: Lock = field(default_factory=Lock, repr=False)

    def record_completion(self) -> None:
        """Record a successfully completed item."""
        with self._lock:
            self.completed_items += 1

    def record_rate_limit(self) -> None:
        """Record a 429 rate limit error."""
        with self._lock:
            self.rate_limit_errors += 1
            self.last_rate_limit_time = time.time()

    def record_error(self) -> None:
        """Record a non-rate-limit error."""
        with self._lock:
            self.total_errors += 1

    def get_throughput(self) -> float:
        """Calculate current throughput in items/sec."""
        with self._lock:
            elapsed = time.time() - self.start_time
            if elapsed > 0:
                return self.completed_items / elapsed
            return 0.0

    def get_error_rate(self) -> float:
        """Calculate rate limit error rate (errors per second)."""
        with self._lock:
            elapsed = time.time() - self.start_time
            if elapsed > 0:
                return self.rate_limit_errors / elapsed
            return 0.0


class AdaptiveWorkerManager:
    """Manages adaptive worker count scaling based on API and CPU metrics."""

    def __init__(
        self,
        initial_workers: int,
        min_workers: int = 4,
        max_workers: int | None = None,
        adjustment_interval: float = 10.0,  # seconds between adjustments
        rate_limit_threshold: float = 0.1,  # errors/sec before backing off
        cpu_threshold: float = 0.8,  # CPU usage threshold for scaling up
    ):
        """Initialize adaptive worker manager.

        Args:
            initial_workers: Starting worker count
            min_workers: Minimum allowed workers
            max_workers: Maximum allowed workers (None = cpu_count * 8)
            adjustment_interval: Seconds between worker count adjustments
            rate_limit_threshold: Rate limit errors/sec before backing off
            cpu_threshold: CPU usage % before scaling up workers
        """
        self.metrics = WorkerMetrics(worker_count=initial_workers)
        self.min_workers = min_workers
        self.max_workers = max_workers or (os.cpu_count() or 4) * 8
        self.adjustment_interval = adjustment_interval
        self.rate_limit_threshold = rate_limit_threshold
        self.cpu_threshold = cpu_threshold

    def should_adjust(self) -> bool:
        """Check if enough time has passed for an adjustment."""
        return (
            time.time() - self.metrics.last_adjustment_time >= self.adjustment_interval
        )

    def get_cpu_usage(self) -> float:
        """Get current CPU usage percentage (0.0-1.0).

        Returns average CPU usage across all cores.
        """
        try:
            import psutil

            return psutil.cpu_percent(interval=0.1) / 100.0
        except ImportError:
            # If psutil not available, assume moderate usage
            logger.warning("psutil not available - cannot measure CPU usage")
            return 0.5

    def calculate_adjustment(self) -> tuple[int, str]:
        """Calculate worker count adjustment based on current metrics.

        Returns:
            Tuple of (new_worker_count, reason)
        """
        current_workers = self.metrics.worker_count
        error_rate = self.metrics.get_error_rate()
        throughput = self.metrics.get_throughput()

        # Check for rate limiting - most important signal
        if error_rate > self.rate_limit_threshold:
            # Back off aggressively - reduce by 25%
            new_workers = max(self.min_workers, int(current_workers * 0.75))
            reason = f"rate_limit_backoff (error_rate={error_rate:.3f}/s)"
            logger.info(
                f"Rate limit detected - reducing workers {current_workers} → {new_workers}"
            )
            return new_workers, reason

        # Check if we recently hit rate limits (within last 30 seconds)
        if (
            self.metrics.last_rate_limit_time
            and time.time() - self.metrics.last_rate_limit_time < 30.0
        ):
            # Don't scale up if we recently hit rate limits
            return current_workers, "cooldown_after_rate_limit"

        # Check CPU usage
        cpu_usage = self.get_cpu_usage()

        if cpu_usage < self.cpu_threshold and current_workers < self.max_workers:
            # CPU has headroom and we're below max - scale up by 25%
            new_workers = min(self.max_workers, int(current_workers * 1.25))
            reason = (
                f"cpu_headroom (cpu={cpu_usage:.2%}, throughput={throughput:.2f}/s)"
            )
            logger.info(
                f"CPU headroom detected - increasing workers {current_workers} → {new_workers}"
            )
            return new_workers, reason

        # No adjustment needed
        return current_workers, "optimal"

    def adjust_if_needed(self) -> bool:
        """Adjust worker count if conditions warrant.

        Returns:
            True if adjustment was made, False otherwise
        """
        if not self.should_adjust():
            return False

        new_workers, reason = self.calculate_adjustment()

        if new_workers != self.metrics.worker_count:
            with self.metrics._lock:
                old_workers = self.metrics.worker_count
                self.metrics.worker_count = new_workers
                self.metrics.last_adjustment_time = time.time()
                self.metrics.adjustment_history.append(
                    (time.time(), new_workers, reason)
                )

            logger.info(
                f"Adjusted workers: {old_workers} → {new_workers} ({reason})",
                extra={
                    "event": "worker_adjustment",
                    "old_workers": old_workers,
                    "new_workers": new_workers,
                    "reason": reason,
                    "throughput": self.metrics.get_throughput(),
                    "rate_limit_errors": self.metrics.rate_limit_errors,
                },
            )
            return True

        return False

    def get_current_worker_count(self) -> int:
        """Get the current recommended worker count."""
        return self.metrics.worker_count

    def get_stats(self) -> dict:
        """Get current statistics for logging/monitoring."""
        return {
            "worker_count": self.metrics.worker_count,
            "completed_items": self.metrics.completed_items,
            "throughput": self.metrics.get_throughput(),
            "rate_limit_errors": self.metrics.rate_limit_errors,
            "error_rate": self.metrics.get_error_rate(),
            "total_errors": self.metrics.total_errors,
            "adjustment_count": len(self.metrics.adjustment_history),
        }
