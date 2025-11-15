#!/usr/bin/env python3
"""Test image attribution system."""

from openai import OpenAI

from src.config import get_config
from src.images.selector import CoverImageSelector

config = get_config()
client = OpenAI(api_key=config.openai_api_key)
selector = CoverImageSelector(client, config)

# Test with a simple query
cover = selector.select(
    "Database optimization guide",
    ["database", "performance"],
    "Learn how to optimize database queries",
)
print(f"✓ Source: {cover.source}")
print(f"✓ URL: {cover.url[:60]}...")
print(f"✓ Alt text: {cover.alt_text}")
print(f"✓ Photographer: {cover.photographer_name}")
print(f"✓ Profile: {cover.photographer_url}")
print(f"✓ Cost: ${cover.cost}")
