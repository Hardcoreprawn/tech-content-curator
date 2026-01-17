"""Tests for site configuration defaults."""

from __future__ import annotations

import tomllib
from pathlib import Path


def test_sponsor_config_defaults() -> None:
    """Sponsor slot config is defined and disabled by default."""
    config_path = Path("site/hugo.toml")
    data = tomllib.loads(config_path.read_text(encoding="utf-8"))

    params = data.get("params", {})
    sponsor = params.get("sponsor", {})

    assert "enabled" in sponsor
    assert sponsor.get("enabled") is False
    assert "url" in sponsor
    assert "text" in sponsor
