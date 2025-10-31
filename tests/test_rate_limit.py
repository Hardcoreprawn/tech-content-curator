from src.utils.rate_limit import RateLimiter, exponential_backoff


def test_rate_limiter_next_available_without_sleep():
    limiter = RateLimiter(rate_per_minute=2, burst=1, jitter=0.0)
    # First token should be available immediately
    assert limiter.next_available_in() == 0.0
    # Consume a token
    limiter.bucket.try_take()
    # Now we should need to wait roughly 30s for next token at 2 rpm
    wait = limiter.next_available_in()
    assert 29.0 <= wait <= 31.0


def test_exponential_backoff_bounded():
    # Backoff should increase and cap at max_delay
    delays = [exponential_backoff(i, base=2.0, max_delay=8.0, jitter=0.0) for i in range(1, 6)]
    assert delays[0] == 2.0
    assert delays[1] == 4.0
    assert delays[2] == 8.0
    assert delays[3] == 8.0  # capped
    assert delays[4] == 8.0  # capped
