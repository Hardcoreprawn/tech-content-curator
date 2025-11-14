#!/usr/bin/env python3
"""Test improved content-aware image selector."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from openai import OpenAI

from src.config import get_config
from src.images.selector import CoverImageSelector


def test_microprocessor_article():
    """Test with the Intel 4004 microprocessor article that got wrong image."""
    config = get_config()
    client = OpenAI(api_key=config.openai_api_key)
    selector = CoverImageSelector(client, config)
    title = "First Commercial Microprocessor: Intel 4004"
    topics = ["computing", "hardware", "vintage", "microprocessor"]
    content = """
The Intel 4004 was the first commercially produced microprocessor, released in 1971.
It was designed for the Busicom calculator and marked a revolution in computing.
The 4004 had 2,300 transistors and operated at 740 kHz. Federico Faggin led the design
team at Intel. The chip was part of a family that included ROM, RAM, and shift register
chips. The Busicom calculator project demonstrated that a single chip could perform
complex calculations that previously required many discrete components.
    """.strip()

    print("=" * 80)
    print("TESTING: Intel 4004 Microprocessor Article")
    print("=" * 80)
    print(f"\nTitle: {title}")
    print(f"Topics: {topics}")
    print(f"Content excerpt: {content[:200]}...")
    print("\n" + "=" * 80)
    print("Generating queries with content-aware LLM...")
    print("=" * 80 + "\n")

    # Test query generation (without actually searching)
    queries = selector._generate_search_queries(title, topics, content)

    print("GENERATED QUERIES:")
    print(f"  Unsplash: {queries.get('unsplash')}")
    print(f"  Pexels:   {queries.get('pexels')}")
    print(f"  DALL-E:   {queries.get('dalle')}")

    print("\n" + "=" * 80)
    print("EXPECTED: Queries should mention 'Intel 4004', 'microprocessor', 'chip'")
    print("EXPECTED: NOT generic 'vintage computer' or 'data center'")
    print("=" * 80)


def test_modern_tech_article():
    """Test with a modern tech article."""
    config = get_config()
    client = OpenAI(api_key=config.openai_api_key)
    selector = CoverImageSelector(client, config)

    title = "GPT-4 Vision Capabilities"
    topics = ["ai", "machine learning", "gpt"]
    content = """
OpenAI's GPT-4 introduced multimodal capabilities, allowing the model to process
both text and images. This advancement enables applications like image description,
visual question answering, and document analysis. The model can understand charts,
    diagrams, and photographs with impressive accuracy.
    """.strip()

    print("\n" + "=" * 80)
    print("TESTING: GPT-4 Vision Article")
    print("=" * 80)
    print(f"\nTitle: {title}")
    print(f"Topics: {topics}")
    print(f"Content excerpt: {content[:150]}...")
    print("\n" + "=" * 80)
    print("Generating queries with content-aware LLM...")
    print("=" * 80 + "\n")

    queries = selector._generate_search_queries(title, topics, content)

    print("GENERATED QUERIES:")
    print(f"  Unsplash: {queries.get('unsplash')}")
    print(f"  Pexels:   {queries.get('pexels')}")
    print(f"  DALL-E:   {queries.get('dalle')}")

    print("\n" + "=" * 80)
    print("EXPECTED: Queries should reference AI, neural networks, or GPT")
    print("=" * 80)


if __name__ == "__main__":
    test_microprocessor_article()
    test_modern_tech_article()
