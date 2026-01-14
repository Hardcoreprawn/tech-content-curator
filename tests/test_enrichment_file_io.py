"""Tests for enrichment file I/O.

These tests ensure loading behavior is robust:
- Validation/coercion errors are logged and skipped
- Unexpected exceptions are not silently swallowed
"""

import json

import pytest

from src.enrichment.file_io import load_collected_items, load_enriched_items
from src.models import CollectedItem, EnrichedItem, SourceType
from tests.utils.types import http_url


def test_load_collected_items_skips_invalid_items(tmp_path):
    """Invalid items are skipped so other items still load."""

    valid = CollectedItem(
        id="1",
        title="t",
        content="c",
        source=SourceType.REDDIT,
        url=http_url("https://example.com/ok"),
        author="a",
        metadata={},
    ).model_dump(mode="json")

    invalid = {**valid, "url": "not-a-url"}

    path = tmp_path / "collected.json"
    path.write_text(
        json.dumps({"items": [valid, invalid]}, ensure_ascii=False), encoding="utf-8"
    )

    items = load_collected_items(path)
    assert [item.id for item in items] == ["1"]


def test_load_enriched_items_skips_invalid_items(tmp_path):
    """Invalid enriched items are skipped so other items still load."""

    original = CollectedItem(
        id="1",
        title="t",
        content="c",
        source=SourceType.GITHUB,
        url=http_url("https://example.com/ok"),
        author="a",
        metadata={},
    )

    valid = EnrichedItem(
        original=original,
        research_summary="r",
        related_sources=[http_url("https://example.com/source")],
        topics=["python"],
        quality_score=0.8,
    ).model_dump(mode="json")

    invalid = {
        **valid,
        "original": {**valid["original"], "url": "not-a-url"},
    }

    path = tmp_path / "enriched.json"
    path.write_text(
        json.dumps({"items": [valid, invalid]}, ensure_ascii=False), encoding="utf-8"
    )

    items = load_enriched_items(path)
    assert [item.original.id for item in items] == ["1"]


def test_load_collected_items_does_not_swallow_unexpected_exceptions(
    tmp_path, monkeypatch
):
    """Unexpected exceptions should surface (fail fast) rather than being silently skipped."""

    import src.enrichment.file_io as file_io

    class BoomCollectedItem:  # noqa: D101
        def __init__(self, **_kwargs):  # noqa: D401
            raise RuntimeError("boom")

    monkeypatch.setattr(file_io, "CollectedItem", BoomCollectedItem)

    path = tmp_path / "collected.json"
    path.write_text(json.dumps({"items": [{"any": "shape"}]}), encoding="utf-8")

    with pytest.raises(RuntimeError, match="boom"):
        load_collected_items(path)
