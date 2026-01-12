import httpx


def test_validate_url_reachable_retries_on_429(monkeypatch):
    """429 should trigger retry/backoff (eventually succeeding)."""

    from src.config import get_config
    from src.enrichment.fact_check import validate_url_reachable

    # Speed up retries in test
    config = get_config()
    monkeypatch.setattr(config, "fact_check_retry_attempts", 3, raising=False)
    monkeypatch.setattr(config, "fact_check_retry_backoff_min", 0.0, raising=False)
    monkeypatch.setattr(config, "fact_check_retry_backoff_max", 0.0, raising=False)
    monkeypatch.setattr(config, "fact_check_retry_jitter", 0.0, raising=False)

    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        # First two attempts rate-limited, then OK
        status = 429 if calls["n"] < 3 else 200
        return httpx.Response(status_code=status, request=request)

    transport = httpx.MockTransport(handler)

    orig_client = httpx.Client

    def client_factory(*args, **kwargs):
        kwargs["transport"] = transport
        return orig_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "Client", client_factory)

    assert validate_url_reachable("https://example.com") is True
    assert calls["n"] >= 3


def test_validate_url_reachable_fallbacks_to_get_when_head_blocked(monkeypatch):
    """If HEAD returns 405, validator should try GET and accept 200."""

    from src.config import get_config
    from src.enrichment.fact_check import validate_url_reachable

    config = get_config()
    monkeypatch.setattr(config, "fact_check_retry_attempts", 1, raising=False)
    monkeypatch.setattr(config, "fact_check_retry_backoff_min", 0.0, raising=False)
    monkeypatch.setattr(config, "fact_check_retry_backoff_max", 0.0, raising=False)
    monkeypatch.setattr(config, "fact_check_retry_jitter", 0.0, raising=False)

    seen = {"head": 0, "get": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "HEAD":
            seen["head"] += 1
            return httpx.Response(status_code=405, request=request)
        if request.method == "GET":
            seen["get"] += 1
            return httpx.Response(status_code=200, request=request)
        return httpx.Response(status_code=500, request=request)

    transport = httpx.MockTransport(handler)
    orig_client = httpx.Client

    def client_factory(*args, **kwargs):
        kwargs["transport"] = transport
        return orig_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "Client", client_factory)

    assert validate_url_reachable("https://example.com") is True
    assert seen["head"] == 1
    assert seen["get"] == 1


def test_validate_url_reachable_retries_on_timeout(monkeypatch):
    """Timeout should retry and eventually fail if all attempts timeout."""

    from src.config import get_config
    from src.enrichment.fact_check import validate_url_reachable

    config = get_config()
    monkeypatch.setattr(config, "fact_check_retry_attempts", 2, raising=False)
    monkeypatch.setattr(config, "fact_check_retry_backoff_min", 0.0, raising=False)
    monkeypatch.setattr(config, "fact_check_retry_backoff_max", 0.0, raising=False)
    monkeypatch.setattr(config, "fact_check_retry_jitter", 0.0, raising=False)

    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        raise httpx.ReadTimeout("timeout", request=request)

    transport = httpx.MockTransport(handler)
    orig_client = httpx.Client

    def client_factory(*args, **kwargs):
        kwargs["transport"] = transport
        return orig_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "Client", client_factory)

    assert validate_url_reachable("https://example.com") is False
    assert calls["n"] == 2
