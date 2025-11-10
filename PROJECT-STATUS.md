# Tech Content Curator - Project Status

**Last Updated:** November 7, 2025  
**Version:** 1.0 (Production)  
**Status:** ✅ Operational - Automated pipeline running 3x daily

---

## Executive Summary

The Tech Content Curator is a **fully operational, production-ready system** that automatically generates high-quality, well-researched technical articles from trending topics across multiple platforms. The system runs autonomously via GitHub Actions, generating approximately 9 articles per day across diverse topics with AI-enhanced visuals and multiple writing styles.

**Key Metrics:**
- 📝 **163 articles published** (growing daily)
- 🤖 **3 automated runs per day** (06:00, 18:00, 02:00 UTC)
- 💰 **~$0.20/day operational cost** (with image generation)
- ⚡ **3-4x speedup** with Python 3.14 free-threading
- 🎨 **5 distinct writing voices** for content variety
- 📊 **Adaptive learning** improves quality over time

---

## Architecture Overview

### Modular Pipeline Design

The system was refactored from a 928-line monolithic orchestrator into focused, maintainable modules:

```
Data Flow:
Collection → Enrichment → Deduplication → Selection → Generation → Publication

Modules:
├── collectors/          # Multi-source content gathering
├── enrichment/          # AI research and scoring
├── deduplication/       # Adaptive pattern learning
├── pipeline/            # Modular orchestration
│   ├── orchestrator.py           # Main coordinator
│   ├── diversity_selector.py     # Candidate selection
│   ├── illustration_service.py   # Visual generation
│   └── article_builder.py        # Content assembly
├── generators/          # Content creation
│   ├── general.py               # Standard articles
│   ├── integrative.py           # Integrative guides
│   ├── specialized/             # Topic-specific
│   └── voices/                  # 5 writing styles
├── illustrations/       # Visual aids (Mermaid, ASCII, SVG)
└── images/             # DALL-E 3 integration
```

### Technology Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Language | Python 3.14+ | Free-threading support (3-4x speedup) |
| Package Manager | uv | Fast, reliable dependency management |
| AI | OpenAI (GPT-4, GPT-4o-mini, DALL-E 3) | Content & image generation |
| Type Safety | Pydantic 2.x | Runtime validation |
| Testing | pytest (~100 tests) | Quality assurance |
| Code Quality | ruff, mypy | Linting & type checking |
| Site Generator | Hugo + PaperMod | Static site publishing |
| Deployment | GitHub Actions + Pages | Automated CI/CD |

---

## Completed Features

### Phase 1: Basic Pipeline ✅

- [x] Multi-source content collection
- [x] AI enrichment with research
- [x] Article generation
- [x] Static site publishing

### Phase 2: Multi-Source ✅

- [x] GitHub Trending integration
- [x] HackerNews top stories
- [x] Mastodon feeds
- [x] Reddit subreddits
- [x] Token-bucket rate limiting
- [x] Exponential backoff with jitter

### Phase 3: Quality Improvement ✅

**Content Quality:**
- [x] AI enrichment with topics and research
- [x] Specialized generators (general, integrative, self-hosted)
- [x] Voice system (5 distinct writing styles)
- [x] Readability analysis and optimization
- [x] Fact-checking integration
- [x] Citation resolution

**Visual Enhancement:**
- [x] Intelligent illustration system
  - AI-generated Mermaid diagrams
  - ASCII art for tables/lists
  - SVG graphics library
  - Context-aware placement
  - WCAG accessibility compliance
- [x] Featured images (DALL-E 3)
- [x] Optimized image processing (50% cost reduction)
- [x] Local icon generation

**Quality Systems:**
- [x] Adaptive deduplication with pattern learning
- [x] Diversity-based candidate selection
- [x] Content relevance filtering
- [x] Source cooldown (7 days)
- [x] Quality score threshold (0.5 minimum)

**Attribution & Transparency:**
- [x] Clear source attribution
- [x] References section with links
- [x] Reading time estimation
- [x] Actual cost tracking per article

### Phase 4: Automation ✅

- [x] GitHub Actions workflows (3 strategies)
- [x] Scheduled runs (3x daily, timezone-optimized)
- [x] Quick site deployment workflow
- [x] Manual override workflow
- [x] Git conflict handling
- [x] SEO automation (sitemap notifications)
- [x] Artifact management

---

## Current Configuration

### Default Settings

```yaml
# Article Generation
ARTICLES_PER_RUN: 3                    # Default per workflow run
QUALITY_THRESHOLD: 0.5                 # Minimum quality score
SOURCE_COOLDOWN_DAYS: 7                # Prevent duplicate sources

# Content Sources
HACKERNEWS_ENABLED: true
GITHUB_TRENDING_ENABLED: true
MASTODON_ENABLED: true
REDDIT_ENABLED: false                  # Optional

# AI Models
CONTENT_MODEL: gpt-4                   # Main article generation
TITLE_MODEL: gpt-4o-mini              # Title/slug generation (70% cheaper)
IMAGE_MODEL: dall-e-3                  # Featured images

# Illustration System
ENABLE_ILLUSTRATIONS: true
MERMAID_DIAGRAMS: true                # Flowcharts, architecture
ASCII_ART: true                       # Tables, lists
SVG_GRAPHICS: true                    # Infographics
```

### Cost Structure

| Operation | Model | Cost per Item | Volume | Daily Cost |
|-----------|-------|---------------|--------|------------|
| Article Content | gpt-4 | ~$0.0015 | 9 | ~$0.014 |
| Titles/Slugs | gpt-4o-mini | ~$0.00006 | 9 | ~$0.001 |
| Featured Images | DALL-E 3 | $0.020 | 9 | ~$0.180 |
| Icon Processing | Pillow (local) | $0.000 | 9 | $0.000 |
| **Total Daily** | | | | **~$0.20** |
| **Monthly** | | | | **~$6.00** |

**Optimization Notes:**
- Switched to gpt-4o-mini for titles/slugs (70% cost reduction)
- Generate 1024x1024 images, resize locally (50% cost savings vs 1792x1024)
- Adaptive learning reduces duplicate processing

---

## Automation Strategy

### Three-Workflow Design

**1. Content Pipeline** (`.github/workflows/content-pipeline.yml`)
- **Trigger:** Scheduled 3x daily (06:00, 18:00, 02:00 UTC) + manual
- **Actions:** Collect → Enrich → Generate 3 articles → Deploy
- **Duration:** 45-60 minutes
- **Cost:** ~$0.07 per run
- **Use Case:** Regular content generation aligned with timezone peaks

**2. Site Update** (`.github/workflows/site-update.yml`)
- **Trigger:** Push to `main` (site/ or content/ changes) + manual
- **Actions:** Optional test article → Hugo build → Deploy
- **Duration:** 3-5 minutes
- **Cost:** ~$0.00 (site-only) or ~$0.002 (with test article)
- **Use Case:** Quick theme/design changes without full pipeline

**3. Full Pipeline** (`.github/workflows/full-pipeline.yml`)
- **Trigger:** Manual only (with configurable article count)
- **Actions:** Same as Content Pipeline
- **Duration:** 45-60 minutes
- **Cost:** Variable based on article count
- **Use Case:** On-demand content generation

### Timezone Optimization

Scheduled runs align with peak discussion periods:

| Time (UTC) | Coverage | Rationale |
|------------|----------|-----------|
| 06:00 | Morning EU + Asia Overnight | Catch Asian discussions + EU morning trends |
| 18:00 | Afternoon US | Peak US daytime discussions |
| 02:00 | Evening US + Early Asia | Late US + early Asian timezone activity |

---

## Quality Systems

### Adaptive Deduplication

The system learns from patterns to improve duplicate detection:

**Features:**
- URL normalization (RFC-compliant)
- Semantic similarity analysis
- Adaptive pattern learning
- Feedback from generated articles
- Confidence scoring

**Pattern Storage:**
```json
data/dedup_patterns.json   # Learned deduplication patterns
data/dedup_feedback.json   # User feedback for improvement
```

### Diversity Selection

Ensures variety in generated content:

**Criteria:**
- Topic diversity (avoid clustering)
- Generator variety (mix article types)
- Source diversity (multiple platforms)
- Quality threshold enforcement
- Novelty scoring

### Content Relevance Filtering

Filters collected content based on topic relevance:

**Configurable Filters:**
```bash
ALLOW_TECH_CONTENT=true        # Programming, tools, frameworks
ALLOW_SCIENCE_CONTENT=true     # Research, papers, astronomy
ALLOW_POLICY_CONTENT=true      # Tech policy, regulations, privacy
```

**Custom Exclusions:**
```bash
RELEVANCE_NEGATIVE_KEYWORDS=recipe,baking,cooking,sports,fashion
```

---

## Monitoring & Observability

### Article Tracking

Each generated article includes comprehensive metadata:

```yaml
generation_costs:
  content_generation: 0.00150075    # Actual tokens from API
  title_generation: 0.0000585
  slug_generation: 0.000052
  image_generation: 0.02            # DALL-E 3
  icon_generation: 0.0              # Local processing

quality_score: 0.82                 # Enrichment quality score
reading_time: 6                     # Minutes
illustration_count: 2               # Visual aids added
voice: balanced                     # Writing style used
```

### Performance Tracking

```json
data/generation_costs.json     # Historical cost data
data/enriched_*.json          # Quality score history
data/voice_history.json       # Voice distribution
```

### GitHub Actions Dashboard

Monitor workflow runs at:
```
https://github.com/Hardcoreprawn/tech-content-curator/actions
```

**Key Metrics:**
- Workflow success rate
- Average run duration
- Articles generated per run
- Artifact sizes

---

## Writing System

### Voice Profiles

Five distinct writing styles for content variety:

| Voice | Tone | Depth | Use Case |
|-------|------|-------|----------|
| **Balanced** | Professional, clear | Medium | General technical content |
| **Technical-Deep** | Expert, formal | Deep | Complex architecture, research |
| **Conversational** | Friendly, accessible | Light | Beginner tutorials, overviews |
| **Analytical** | Data-driven, precise | Medium-Deep | Comparisons, evaluations |
| **Story-Driven** | Narrative, engaging | Medium | Community discussions, trends |

**Selection Logic:**
- Automatically chosen based on content type
- Balanced across article batches
- Can be manually specified

### Illustration System

**Three AI-Powered Visual Types:**

1. **Mermaid Diagrams** (flowcharts, architecture)
   - Context-aware generation
   - Automatic syntax validation
   - Responsive rendering

2. **ASCII Art** (tables, lists, trees)
   - Lightweight text-based visuals
   - Terminal-friendly
   - Fast generation

3. **SVG Graphics** (infographics, icons)
   - Hand-crafted template library
   - Programmatic customization
   - Scalable and accessible

**Features:**
- Intelligent placement analysis
- WCAG accessibility compliance
- Descriptive alt-text generation
- Context-aware visual selection

---

## Known Limitations

### Current Constraints

1. **Rate Limits**
   - Reddit: 30 requests/minute (configurable)
   - GitHub: 60 requests/hour (unauthenticated)
   - HackerNews: Self-throttled (0.1s between requests)

2. **Content Volume**
   - Default: 3 articles per run (9 per day)
   - Can be increased via `ARTICLES_PER_RUN` environment variable
   - Cost scales linearly with volume

3. **Language Support**
   - Currently English-only
   - Multi-language support is a future enhancement

4. **Image Generation**
   - DALL-E 3 rate limits apply
   - Occasional generation failures (handled gracefully)

### Active Issues (Being Addressed)

**See `BUGS.md` and `TODO.md` for details:**

1. **Exception Handling** 🚨 - Silent failures in production
2. **Config Validation** - Fails late, wastes resources
3. **Input Sanitization** 🔐 - Path traversal vulnerability
4. **Logging Inconsistency** - Mixed print/logger usage
5. **Async Strategy** - Unclear threading model

**Timeline:** Critical issues being fixed Week of Nov 10-17, 2025

### Non-Issues

These are **not** problems:
- ✅ Deduplication works well with adaptive learning
- ✅ Quality threshold effectively filters low-value content
- ✅ Source cooldown prevents repetitive content
- ✅ Git conflicts handled automatically

---

## Future Enhancements

### Short-Term (Next Quarter)

1. **Analytics Dashboard**
   - Article performance metrics
   - Cost trends visualization
   - Quality score tracking
   - Source effectiveness analysis

2. **Enhanced Monitoring**
   - Error notifications (email/Slack)
   - Quality degradation alerts
   - Cost anomaly detection

3. **Content Optimization**
   - A/B testing different prompts
   - Voice effectiveness analysis
   - Illustration impact measurement

### Medium-Term (6-12 Months)

1. **Multi-Language Support**
   - Automatic translation
   - Language-specific sources
   - Cultural adaptation

2. **Advanced Visuals**
   - Video summaries (short clips)
   - Interactive diagrams
   - Code syntax highlighting improvements

3. **Community Features**
   - Comment integration
   - Social sharing optimization
   - Newsletter generation

### Long-Term (1+ Years)

1. **Machine Learning**
   - Content recommendation engine
   - Predictive trending
   - Personalized article generation

2. **Platform Expansion**
   - Mobile app
   - RSS reader integration
   - Browser extension

3. **Monetization**
   - Sponsored content (ethical)
   - API access for other projects
   - Premium features

---

## Getting Started for New Contributors

### Prerequisites

1. **System Setup**
   - Python 3.14+ (free-threading recommended)
   - uv package manager
   - Git
   - VS Code (recommended)

2. **API Keys Required**
   - `OPENAI_API_KEY` (required for article generation)
   - `ANTHROPIC_API_KEY` (optional, for alternative models)
   - Social media credentials (optional, for collection)

### Quick Start

```bash
# Clone repository
git clone https://github.com/Hardcoreprawn/tech-content-curator.git
cd tech-content-curator

# Setup environment
uv venv --python 3.14
uv sync --all-extras

# Configure environment
cp .env.example .env
# Edit .env with your API keys

# Run tests
uv run pytest tests/ -v

# Generate test article (manual)
uv run python -m src.pipeline.orchestrator --max-articles 1 --dry-run
```

### Key Documentation

| Document | Purpose |
|----------|---------|
| `README.md` | Project overview and quick reference |
| `SETUP.md` | Detailed development setup |
| `PROJECT-STATUS.md` | This document |
| `docs/ADR-*.md` | Architecture decisions |
| `docs/FEATURE-3-DESIGN.md` | Illustration system design |
| `docs/FREE-THREADING-SETUP.md` | Python 3.14 optimization |

---

## Support & Contact

### Issues & Bugs

Report issues at:
```
https://github.com/Hardcoreprawn/tech-content-curator/issues
```

### Discussion & Questions

GitHub Discussions:
```
https://github.com/Hardcoreprawn/tech-content-curator/discussions
```

### Live Site

View published articles:
```
https://hardcoreprawn.github.io/tech-content-curator/
```

---

## Summary

The Tech Content Curator is a **mature, production-ready system** that successfully automates the entire content creation pipeline from discovery to publication. With adaptive learning, multiple writing voices, intelligent visual generation, and cost-effective operation, it provides a solid foundation for ongoing content creation.

**Current Status:** ✅ Fully Operational  
**Maintenance:** Minimal (automated with monitoring)  
**Cost:** ~$6/month (~$0.20/day)  
**Output:** ~9 quality articles per day (~270/month)  
**Quality:** High (adaptive learning, multiple review stages)

The system is ready for scale-up, feature expansion, or adaptation to other content domains.

---

*Last updated: November 7, 2025*
