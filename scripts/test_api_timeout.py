#!/usr/bin/env python3
"""Debug script to test OpenAI API timeout issues."""

import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

# Create client with timeout
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    timeout=30.0,  # 30 second timeout
    max_retries=2,
)

print("Testing OpenAI API with various calls...")

# Test 1: Simple model list
print("\n1. Testing models.list()...")
try:
    result = client.models.list()
    print(f"   ✓ Success: Found {len(result.data)} models")
except Exception as e:
    print(f"   ✗ Failed: {e}")

# Test 2: Simple completion
print("\n2. Testing simple chat completion...")
try:
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": "Say hello"}],
        max_tokens=10,
    )
    print(f"   ✓ Success: {response.choices[0].message.content}")
except Exception as e:
    print(f"   ✗ Failed: {e}")

# Test 3: Longer request (similar to what integrative generator does)
print("\n3. Testing longer prompt (integrative generator style)...")
try:
    long_prompt = """
    You're writing an in-depth integrative guide based on a curated list-style source.

    CONTEXT FROM SOURCE:
    TITLE: Example Title
    CONTENT (excerpt): This is some test content
    SOURCE URL: https://example.com
    TOPICS: test, example

    WRITE A COMPREHENSIVE GUIDE THAT:
    - Opens with why this problem space matters
    - Includes a short "Key Takeaways" bullet list
    - Groups tools into a clear taxonomy
    """

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": long_prompt}],
        max_tokens=100,
    )
    print(
        f"   ✓ Success: Got response ({len(response.choices[0].message.content)} chars)"
    )
except Exception as e:
    print(f"   ✗ Failed: {e}")

print("\nAll tests completed!")
