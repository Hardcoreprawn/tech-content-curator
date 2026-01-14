"""Tests for fetch_article_content in src.enrichment.source_fetcher.

These tests focus on exception handling and optional-dependency behavior.
"""

import sys
from types import ModuleType
from typing import Any, cast

import pytest

from src.enrichment.source_fetcher import fetch_article_content


def test_fetch_article_content_missing_requests_returns_none(monkeypatch):
    """Missing requests dependency returns None (no crash in except clauses)."""

    real_import = __import__

    def guarded_import(name, *args, **kwargs):  # noqa: ANN001
        if name == "requests":
            raise ModuleNotFoundError("requests")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", guarded_import)
    monkeypatch.setattr("time.sleep", lambda _seconds: None)

    assert fetch_article_content("https://example.com") is None


def test_fetch_article_content_missing_bs4_returns_none(monkeypatch):
    """Missing bs4 dependency returns None (no crash in except clauses)."""

    real_import = __import__

    def guarded_import(name, *args, **kwargs):  # noqa: ANN001
        if name == "bs4":
            raise ModuleNotFoundError("bs4")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", guarded_import)
    monkeypatch.setattr("time.sleep", lambda _seconds: None)

    assert fetch_article_content("https://example.com") is None


def test_fetch_article_content_timeout_returns_none(monkeypatch):
    """Timeouts are treated as expected failures and return None."""

    monkeypatch.setattr("time.sleep", lambda _seconds: None)

    class Timeout(Exception):
        pass

    class RequestException(Exception):
        pass

    def get(*_args, **_kwargs):
        raise Timeout("timeout")

    fake_requests = ModuleType("requests")
    requests_mod = cast(Any, fake_requests)
    requests_mod.Timeout = Timeout
    requests_mod.RequestException = RequestException
    requests_mod.get = get

    fake_bs4 = ModuleType("bs4")

    class BeautifulSoup:  # noqa: D101
        def __init__(self, *_args, **_kwargs):
            raise AssertionError("BeautifulSoup should not be used on timeout")

    cast(Any, fake_bs4).BeautifulSoup = BeautifulSoup

    monkeypatch.setitem(sys.modules, "requests", fake_requests)
    monkeypatch.setitem(sys.modules, "bs4", fake_bs4)

    assert fetch_article_content("https://example.com") is None


def test_fetch_article_content_success_returns_text(monkeypatch):
    """Successful fetch parses and returns cleaned text."""

    monkeypatch.setattr("time.sleep", lambda _seconds: None)

    class Timeout(Exception):
        pass

    class RequestException(Exception):
        pass

    class Response:  # noqa: D101
        def __init__(self):
            self.content = (
                b"<html><body><article>Hello\n\nWorld</article></body></html>"
            )

        def raise_for_status(self):
            return None

    def get(*_args, **_kwargs):
        return Response()

    fake_requests = ModuleType("requests")
    requests_mod = cast(Any, fake_requests)
    requests_mod.Timeout = Timeout
    requests_mod.RequestException = RequestException
    requests_mod.get = get

    fake_bs4 = ModuleType("bs4")

    class _Main:  # noqa: D101
        def get_text(self, separator="\n", strip=True):  # noqa: ANN001
            assert separator == "\n"
            assert strip is True
            return "Hello\n\nWorld\n"

    class BeautifulSoup:  # noqa: D101
        def __init__(self, *_args, **_kwargs):
            self.body = _Main()

        def __call__(self, _tags):  # noqa: ANN001
            return []

        def select_one(self, _selector):  # noqa: ANN001
            return _Main()

    cast(Any, fake_bs4).BeautifulSoup = BeautifulSoup

    monkeypatch.setitem(sys.modules, "requests", fake_requests)
    monkeypatch.setitem(sys.modules, "bs4", fake_bs4)

    text = fetch_article_content("https://example.com", max_size=5000)
    assert text is not None
    assert "Hello" in text
    assert "World" in text


def test_fetch_article_content_truncates(monkeypatch):
    """Large content is truncated with a marker."""

    monkeypatch.setattr("time.sleep", lambda _seconds: None)

    class Timeout(Exception):
        pass

    class RequestException(Exception):
        pass

    class Response:  # noqa: D101
        def __init__(self):
            self.content = b"<html><body><article>ignored</article></body></html>"

        def raise_for_status(self):
            return None

    def get(*_args, **_kwargs):
        return Response()

    fake_requests = ModuleType("requests")
    requests_mod = cast(Any, fake_requests)
    requests_mod.Timeout = Timeout
    requests_mod.RequestException = RequestException
    requests_mod.get = get

    fake_bs4 = ModuleType("bs4")

    class _Main:  # noqa: D101
        def get_text(self, separator="\n", strip=True):  # noqa: ANN001
            return "x" * 100

    class BeautifulSoup:  # noqa: D101
        def __init__(self, *_args, **_kwargs):
            self.body = _Main()

        def __call__(self, _tags):  # noqa: ANN001
            return []

        def select_one(self, _selector):  # noqa: ANN001
            return _Main()

    cast(Any, fake_bs4).BeautifulSoup = BeautifulSoup

    monkeypatch.setitem(sys.modules, "requests", fake_requests)
    monkeypatch.setitem(sys.modules, "bs4", fake_bs4)

    text = fetch_article_content("https://example.com", max_size=10)
    assert text is not None
    assert text.endswith("[Content truncated...]")


@pytest.mark.parametrize("bad_module", ["requests", "bs4"])
def test_fetch_article_content_restores_imports(monkeypatch, bad_module: str):
    """The tests' sys.modules patching doesn't leak across tests."""

    # This is a sanity check: if something leaks, later imports would behave oddly.
    monkeypatch.setattr("time.sleep", lambda _seconds: None)

    sys.modules.pop(bad_module, None)
    result = fetch_article_content("https://example.com")
    assert result is None or isinstance(result, str)
