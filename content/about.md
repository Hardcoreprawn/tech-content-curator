---
title: "About Tech Content Curator"
layout: "single"
url: "/about"
summary: "How we curate and generate tech content"
ShowToc: false
ShowReadingTime: false
---

## What We Do

Tech Content Curator automatically discovers, researches, and synthesizes high-quality technical content from across the web. We monitor conversations on **HackerNews**, **GitHub Trending**, **Mastodon**, and **Reddit** to find the most interesting technical discussions, then use AI to create comprehensive, well-researched articles.

## How It Works

### 1. Collection
We monitor multiple sources for interesting technical content, such as:
- **HackerNews**: Top stories and discussions
- **GitHub Trending**: Popular repositories and releases
- **Mastodon**: Tech-focused instances (Hachyderm, Fosstodon)
- **Reddit**: Select technology subreddits

### 2. Quality Scoring
Each item goes through adaptive quality assessment:
- Content relevance and depth
- Author credibility
- Community engagement
- Technical substance

### 3. Research & Enrichment
High-scoring items are researched and enriched with:
- Related sources and context
- Topic extraction and tagging
- Background research
- Fact-checking validation

### 4. Article Generation
Specialized generators create different types of content:
- **Deep-dive articles**: Technical explanations and analysis
- **Integrative guides**: Curated lists synthesized into comprehensive guides
- **Specialized content**: Self-hosting, security, DevOps topics

### 5. Transparent Attribution
Every article includes:
- Clear attribution to original authors
- Links to all source materials
- Generation costs for full transparency
- Reading time estimates

## Technology Stack

- **Python 3.12+** for the pipeline
- **OpenAI GPT** for content generation
- **Hugo + PaperMod** for the static site
- **GitHub** for automation & hosting

## Cost Transparency

We track and publish the actual API costs for each article:
- Text generation: ~$0.002 per article (GPT-4o-mini)
- Images: $0 (reused library variants)
- Total: ~$0.002 per article

## Quality Philosophy

We prioritize:
- **Accuracy**: Fact-checked content with source validation
- **Depth**: 1000-1500 word articles with thorough research
- **Attribution**: Clear crediting of original authors and sources
- **Accessibility**: Technical content explained for broad audiences
- **Transparency**: Open source pipeline, visible costs

## Source Code

The entire pipeline is open source:
- **Repository**: [github.com/Hardcoreprawn/tech-content-curator](https://github.com/Hardcoreprawn/tech-content-curator)
- **License**: MIT
- **Contributions**: This is a portfolio project, so we won't accept any as standard.

## Content Policy

We don't:
- Reproduce content without attribution
- Generate clickbait titles
- Publish low-quality content
- Reuse sources within 7 days (diversity guarantee)

## Updates

The pipeline runs automatically:
- **3× daily** scheduled runs (06:00, 18:00, 02:00 UTC)
- **On demand** via GitHub Actions
- **On push** for immediate updates

New articles are typically published within minutes of trending discussions.

## Contact

Questions, feedback, or issues? Open an issue on [GitHub](https://github.com/Hardcoreprawn/tech-content-curator/issues).
