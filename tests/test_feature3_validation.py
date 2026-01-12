#!/usr/bin/env python3
"""
Feature 3 Validation Script - Generate test articles with AI illustrations

This script:
1. Creates sample enriched items with different concept types
2. Generates complete articles with multi-format illustrations
3. Validates output quality and format diversity
4. Tracks costs
"""

import os
import re
import sys
from datetime import datetime

from openai import OpenAI
from pydantic import HttpUrl

from src.models import CollectedItem, EnrichedItem, PipelineConfig, SourceType
from src.pipeline import generate_single_article
from src.pipeline.candidate_selector import get_available_generators


def create_test_enriched_item(title: str, content: str, source: str) -> EnrichedItem:
    """Create a test enriched item for article generation."""
    collected = CollectedItem(
        id=f"test-{datetime.now().timestamp()}",
        title=title,
        content=content,
        source=SourceType.BLUESKY,
        url=HttpUrl("https://bsky.app/profile/test/feed/test"),
        author="Test Author",
        metadata={"source_name": "feature3_validation"},
    )

    return EnrichedItem(
        original=collected,
        research_summary="Test article for Feature 3 validation",
        topics=[],
        quality_score=0.85,
    )


def main():
    """Generate test articles and validate illustrations."""

    print("\n" + "=" * 80)
    print("FEATURE 3 VALIDATION: Multi-Format AI Illustrations")
    print("=" * 80 + "\n")

    # Initialize config and client
    config = PipelineConfig(openai_api_key=os.getenv("OPENAI_API_KEY", ""))
    client = OpenAI()
    # Get available generators for orchestrator
    generators = get_available_generators(client)

    # Test articles with different concept types
    test_articles = [
        {
            "title": "Understanding Network Address Translation (NAT)",
            "content": """
# Understanding Network Address Translation (NAT)

## What is NAT?

Network Address Translation (NAT) is a networking technique that allows private IP addresses
to communicate with external networks by translating those addresses into public IP addresses.
When data packets flow through a NAT router, the router modifies the source or destination IP
addresses in packet headers, maintaining a translation table to track connections.

## How NAT Works

The core mechanism involves several steps:

1. A device on the private network sends a packet with a private IP address (e.g., 192.168.1.10)
2. The packet reaches the NAT router
3. The router creates an entry in its translation table
4. The router replaces the private source IP with its public IP address
5. The packet is sent to the internet with the public address
6. Response packets are received by the router
7. The router looks up the translation table entry
8. The router replaces the public destination IP back to the private IP
9. The packet is delivered to the original device

This process happens transparently to both the client and the external server.

## NAT Types

There are several types of NAT implementations:

- **Static NAT**: One-to-one mapping of private to public IP addresses
- **Dynamic NAT**: Multiple private IPs map to a pool of public IPs
- **Port Address Translation (PAT)**: Many private IPs share a single public IP (most common)

## Benefits and Limitations

NAT provides significant advantages for network security and IP address conservation. However,
it can complicate peer-to-peer connections and certain protocols like VoIP or gaming.

## Practical Alternatives

Modern alternatives to traditional NAT include IPv6, which eliminates the need for address
translation by providing sufficient address space for all devices. However, NAT remains
ubiquitous in current networks.
""",
            "source": "networking",
            "concepts": ["network_topology", "system_architecture"],
        },
        {
            "title": "Building Scalable Data Pipelines",
            "content": """
# Building Scalable Data Pipelines

## Introduction

A data pipeline is a series of processing steps that move data from source systems to target systems,
transforming and enriching it along the way. Building scalable pipelines is critical for modern
data-driven applications.

## Pipeline Architecture

The typical data pipeline follows this pattern:

1. **Ingestion**: Raw data enters from various sources
2. **Validation**: Data quality checks and schema validation
3. **Transformation**: Business logic applied to transform data
4. **Enrichment**: Adding context and related information
5. **Loading**: Storing processed data in target systems
6. **Monitoring**: Tracking performance and health

## Components

Each pipeline requires:

- **Message queues** for reliable data transport
- **Processing engines** for compute-heavy transformations
- **Storage systems** for intermediate and final data
- **Orchestration tools** for scheduling and monitoring

## Best Practices

Successful pipelines follow these patterns:

- Start simple, scale incrementally
- Implement comprehensive monitoring and alerting
- Design for failure with retry logic
- Version your data transformations
- Document data contracts between stages

## Common Patterns

ETL (Extract-Transform-Load) and ELT (Extract-Load-Transform) are the two primary patterns,
each suited for different scenarios and performance requirements.
""",
            "source": "data_engineering",
            "concepts": ["data_flow", "system_architecture"],
        },
        {
            "title": "A/B Testing: Statistical Methods and Best Practices",
            "content": """
# A/B Testing: Statistical Methods and Best Practices

## What is A/B Testing?

A/B testing (split testing) is a controlled experiment where you compare two versions of something
to determine which performs better. It's fundamental to data-driven product development.

## Statistical Foundations

A/B tests rely on hypothesis testing:

- **Null Hypothesis (H0)**: No difference between variants
- **Alternative Hypothesis (H1)**: There is a meaningful difference
- **Significance Level (α)**: Probability of Type I error (typically 5%)
- **Power (1-β)**: Probability of detecting a real effect (typically 80%)

## When to Use A/B Testing

A/B testing is ideal for:

- Feature decisions (which version converts better?)
- Design changes (layout impact on engagement)
- Pricing experiments (optimal price point)
- Messaging tests (which copy resonates more?)

## Common Pitfalls

- **Multiple testing problem**: Running too many tests increases false positives
- **Peeking**: Stopping early when results look good
- **Ignoring interactions**: Not considering how variants affect each other
- **Sample size too small**: Insufficient data for statistical power

## Best Practices

- Calculate required sample size before running tests
- Use proper randomization and assignment methods
- Document all tests and their outcomes
- Account for multiple comparisons
- Replicate significant findings

## Analysis Methods

Standard methods include t-tests for continuous metrics and chi-square tests for categorical
data, with proper adjustment for multiple testing scenarios.
""",
            "source": "analytics",
            "concepts": ["comparison", "scientific_process"],
        },
    ]

    print(f"Generating {len(test_articles)} test articles with AI illustrations...\n")

    total_cost = 0
    results = []

    for i, article_data in enumerate(test_articles, 1):
        print(f"\n{'=' * 80}")
        print(f"[{i}/{len(test_articles)}] {article_data['title']}")
        print(f"{'=' * 80}")

        # Create enriched item
        enriched = create_test_enriched_item(
            title=article_data["title"],
            content=article_data["content"],
            source=article_data["source"],
        )

        # Generate article
        print("\nGenerating article with multi-format illustrations...")
        article = generate_single_article(
            enriched,
            generators,
            client,
            config=config,
        )

        if article:
            print("✅ Article generated successfully")
            print(f"   Title: {article.title}")
            print(f"   Filename: {article.filename}")
            print(f"   Illustrations: {article.illustrations_count}")

            # Extract cost information
            ill_costs = article.generation_costs.get("illustrations", [])
            ill_cost = sum(ill_costs)
            total_cost += ill_cost

            print("\n📊 Illustration Details:")
            print(f"   Cost: ${ill_cost:.6f}")

            total_generation_cost = sum(
                sum(costs) for costs in article.generation_costs.values()
            )
            print(f"   Total generation cost: ${total_generation_cost:.6f}")

            # Show content preview with illustrations
            print("\n📝 Generated Content Preview:")
            print("-" * 80)
            content_preview = (
                article.content[:500] + "..."
                if len(article.content) > 500
                else article.content
            )
            print(content_preview)
            print("-" * 80)

            # Analyze illustrations in content
            if article.illustrations_count > 0:
                print("\n🎨 Illustration Analysis:")

                # Count format usage
                mermaid_count = article.content.count("```mermaid")
                ascii_count = article.content.count("```\n")  # Simple heuristic
                svg_count = article.content.count("<figure>")

                print(f"   Mermaid diagrams: {mermaid_count}")
                print(f"   ASCII diagrams: {ascii_count - mermaid_count}")
                print(f"   SVG graphics: {svg_count}")

                # Show alt-text samples
                alt_texts = re.findall(r"<!-- (.*?) -->", article.content)
                if alt_texts:
                    print("\n   Alt-text samples:")
                    for alt in alt_texts[:2]:
                        print(f"   • {alt[:80]}...")
            else:
                print("\n⚠️  No illustrations generated for this article")

            results.append(
                {
                    "title": article.title,
                    "illustrations": article.illustrations_count,
                    "cost": ill_cost,
                    "concepts": article_data["concepts"],
                }
            )
        else:
            print("❌ Failed to generate article")
            results.append(
                {
                    "title": article_data["title"],
                    "illustrations": 0,
                    "cost": 0,
                    "concepts": article_data["concepts"],
                    "error": "Generation failed",
                }
            )

    # Summary
    print(f"\n\n{'=' * 80}")
    print("VALIDATION SUMMARY")
    print(f"{'=' * 80}\n")

    print(
        f"Generated: {len([r for r in results if 'error' not in r])}/{len(test_articles)} articles"
    )
    print(f"Total illustrations: {sum(r['illustrations'] for r in results)}")
    print(f"Total illustration cost: ${total_cost:.6f}")

    print("\n📊 Detailed Results:")
    print(f"{'Article':<40} {'Illustrations':<15} {'Cost':<12} {'Concepts'}")
    print("-" * 80)

    for r in results:
        concepts_str = ", ".join(r.get("concepts", [])[:2])
        error_str = f" (ERROR: {r['error']})" if "error" in r else ""
        print(
            f"{r['title'][:37]:<40} {r['illustrations']:<15} ${r['cost']:<11.6f} {concepts_str}{error_str}"
        )

    print(f"\n{'=' * 80}")
    print("✅ VALIDATION COMPLETE")
    print(f"{'=' * 80}\n")

    # Return results for CI/CD
    return 0 if all("error" not in r for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
