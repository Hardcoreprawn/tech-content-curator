"""Simple rate limiting utilities.

Provides a lightweight token bucket limiter and exponential backoff helper
to keep external API usage respectful and avoid 429 blocks.
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass


@dataclass
class TokenBucket:
    capacity: int
    refill_rate_per_sec: float
    tokens: float
    last_refill: float

    @classmethod
    def create(cls, rate_per_minute: int, burst: int) -> TokenBucket:
        now = time.monotonic()
        return cls(
            capacity=burst,
            refill_rate_per_sec=rate_per_minute / 60.0,
            tokens=burst,
            last_refill=now,
        )

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self.last_refill
        if elapsed > 0:
            self.tokens = min(
                self.capacity, self.tokens + elapsed * self.refill_rate_per_sec
            )
            self.last_refill = now

    def try_take(self, amount: float = 1.0) -> bool:
        self._refill()
        if self.tokens >= amount:
            self.tokens -= amount
            return True
        return False

    def time_until_available(self, amount: float = 1.0) -> float:
        self._refill()
        if self.tokens >= amount:
            return 0.0
        deficit = amount - self.tokens
        return max(0.0, deficit / self.refill_rate_per_sec)


class RateLimiter:
    """Blocking token bucket limiter with optional jitter."""

    def __init__(self, rate_per_minute: int, burst: int, jitter: float = 0.1) -> None:
        self.bucket = TokenBucket.create(rate_per_minute, burst)
        self.jitter = max(0.0, min(jitter, 1.0))

    def acquire(self, amount: float = 1.0) -> None:
        from ..config import get_config

        config = get_config()
        min_interval = config.sleep_intervals.rate_limit_minimum_interval
        while not self.bucket.try_take(amount):
            wait = self.bucket.time_until_available(amount)
            # Add small jitter to avoid thundering herd
            wait *= 1.0 + random.uniform(-self.jitter, self.jitter)
            time.sleep(max(min_interval, wait))

    def next_available_in(self, amount: float = 1.0) -> float:
        return self.bucket.time_until_available(amount)


def exponential_backoff(
    attempt: int, base: float = 2.0, max_delay: float = 60.0, jitter: float = 0.2
) -> float:
    """Calculate backoff delay with jitter for a given attempt number (1-based)."""
    delay = min(max_delay, (base ** max(1, attempt)))
    # Apply jitter +/- percentage
    return max(0.1, delay * (1.0 + random.uniform(-jitter, jitter)))
