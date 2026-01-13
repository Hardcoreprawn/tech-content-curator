"""Type-safe helpers for test construction.

This repo treats types as executable expectations. Tests should prefer
canonical model types rather than loosely-typed stand-ins.
"""

from __future__ import annotations

from typing import Any

from pydantic import HttpUrl, TypeAdapter

from src.models import CollectedItemMetadata

_HTTP_URL_ADAPTER = TypeAdapter(HttpUrl)


def http_url(url: str) -> HttpUrl:
    return _HTTP_URL_ADAPTER.validate_python(url)


def collected_item_metadata(**kwargs: Any) -> CollectedItemMetadata:
    # TypedDict has no runtime validation; this is a narrow, explicit cast.
    return kwargs  # type: ignore[return-value]
