# Tech Content Curator - Project Kickoff

**Goal**: Automatically generate readable, well-sourced blog articles from interesting tech content on social media.

**Status**: Fresh start - experimenting and learning  
**Philosophy**: Simple, working code over complex architecture  
**Timeline**: Build iteratively, ship something in weeks not months

## Project status (snapshot)

- Phase: Phase 3 – Quality Improvement ✅ COMPLETE
- What works: multi-source collection (GitHub Trending, HackerNews, Mastodon, Reddit), URL+semantic dedup with adaptive learning, AI enrichment with research, specialized generators (general, integrative, self-hosted), voice system (5 distinct writing styles), intelligent illustration system (Mermaid diagrams, ASCII art, SVG graphics), featured image generation (DALL-E 3 with local processing), transparent cost tracking, fact-checking validation, Hugo site with PaperMod theme; **163 articles live**
- Latest improvements: Modular pipeline architecture (split from 928-line monolith into focused modules), Python 3.14 free-threading support (3-4x speedup), automated GitHub Actions workflows (3x daily scheduled runs), adaptive deduplication with pattern learning, diversity-based candidate selection
- Known issues: None blocking
- Next steps (priority):
    1) Monitor automated pipeline performance
    2) Refine adaptive learning patterns
    3) Explore multi-language support
    4) Analytics dashboard for content performance

### Quick checklist

- [x] Phase 1: Basic Pipeline
- [x] Phase 2: Multi-Source
- [x] Phase 3: Quality Improvement ✅
  - [x] AI enrichment with topics/research
  - [x] Specialized generators (general, integrative, self-hosted)
  - [x] Voice system (5 distinct writing styles)
  - [x] Intelligent illustration system (Mermaid, ASCII, SVG)
  - [x] Clear attribution at top of articles
  - [x] References section with original links
  - [x] Reading time in frontmatter
  - [x] Fact-checking integration
  - [x] Featured images with DALL-E 3
  - [x] Cost tracking with actual token usage
  - [x] Optimized image generation (50% cost reduction)
  - [x] Theme customization (PaperMod)
  - [x] Adaptive deduplication with pattern learning
- [x] Phase 4: Automation ✅
  - [x] Scheduled runs (GitHub Actions - 3x daily)
  - [x] Three workflow strategies (scheduled, quick deploy, manual override)
  - [x] Automated SEO (sitemap notifications)
  - [x] Git conflict handling

## Core Decisions (Locked In)

These are **fixed** - don't second-guess these:

1. **Language**: Python 3.14+ (free-threading support, modern features)
2. **Sources**: GitHub Trending, HackerNews, Mastodon, Reddit (diverse, tech-focused communities)
3. **Output Format**: Blog-style articles (1200-1500 words, well-researched with visuals)
4. **Publishing**: GitHub Pages with Hugo (free, simple, reliable)
5. **Quality Bar**: "Readable and gets read" - value over volume, diversity over duplication

## What We're Building

A **simple content pipeline** that:

1. Collects interesting tech topics from social media
2. Researches and enriches them with AI
3. Generates well-sourced blog articles
4. Publishes to a static site

**Not building**: Enterprise infrastructure, microservices, real-time systems, production-scale platform

## Technology Stack (Modern & Simple)

### Core (Required)

- **Python 3.14+** - Free-threading support (3-4x speedup on article generation)
- **uv** - Fast Python package manager (replaces pip/poetry)
- **Pydantic 2.x** - Type validation and settings
- **httpx** - Modern HTTP client with retry logic
- **Rich** - Beautiful console output for debugging

### AI & Content

- **OpenAI Python SDK** - GPT-4 content generation, GPT-4o-mini for titles/slugs, DALL-E 3 for images
- **mastodon.py** - Mastodon API client
- **praw** - Reddit API client with token-bucket rate limiter
- **HackerNews API** - Direct API access (no client library needed)
- **GitHub API** - Trending repositories via httpx

### Content Processing

- **python-frontmatter** - YAML frontmatter handling
- **python-slugify** - URL-safe slug generation
- **textstat** - Readability analysis
- **mdformat** - Markdown linting and formatting
- **Pillow** - Image processing for icons
- **bleach** - Input sanitization
- **url-normalize** - RFC-compliant URL normalization

### Static Site

- **Markdown** - Article format with extended syntax
- **Hugo** - Static site generator (extended version)
- **PaperMod Theme** - Clean, fast Hugo theme
- **GitHub Pages** - Free hosting with Actions deployment

### Development

- **pytest** - Testing framework (~100 tests)
- **ruff** - Fast Python linter/formatter (replaces flake8, black, isort)
- **mypy** - Type checking
  
### Rate limiting & retries

- Lightweight token bucket limiter (configurable via env)
- Exponential backoff with jitter on 429/5xx for Reddit
- Defaults tuned to be conservative and respectful

## Standards

- Keep it simple: one script per stage (collect, enrich, generate, publish); synchronous by default; JSON files for storage
- Type everything: Pydantic models and Python type hints throughout
- Observability: rich console output and clear, early validation; fail fast with actionable errors
- Code quality: ruff (lint/format), mypy (types), pytest (tests); small functions; avoid premature abstractions
- API etiquette: token-bucket rate limiting + backoff (especially Reddit); respect provider TOS
- Tooling: uv for install/run/test; target Python 3.12+ (3.13 preferred when available)

See details in [Architecture Principles](#architecture-principles) and [AI Agent Guidelines](#ai-agent-guidelines).

## Article conventions (quality and accessibility)

To keep content professional, ethical, and accessible:

- **Attribution**: Every article begins with a clear line crediting the original post/author and links to the source. We don't reproduce content; we expand upon it.
- **Key takeaways**: Near the top, include a short bullet list (3–5) summarizing the most important points.
- **Visual aids**: Intelligent illustration system adds Mermaid diagrams, ASCII art, or SVG graphics where they enhance understanding.
- **Voice variety**: Five distinct writing styles (balanced, technical-deep, conversational, analytical, story-driven) for diverse content.
- **References**: A "References" section at the end lists the original source(s) with links and authors.
- **Explanations**: Define acronyms and non‑mainstream terms the first time they appear. When background is optional, add a short blockquote callout.
- **Reading time**: We estimate and include reading time in frontmatter to set expectations.
- **Accessibility**: All visual elements include descriptive alt-text for screen readers.
- **Tone**: Informative, respectful, and non‑condescending; assume curiosity, not prior expertise.

## Cost tracking and optimization

Transparency matters. Every generated article includes actual API costs in frontmatter:

```yaml
generation_costs:
  content_generation: 0.00150075  # Actual tokens from API
  title_generation: 0.0000585
  slug_generation: 0.000052
  image_generation: 0.02          # DALL-E 3 (if enabled)
  icon_generation: 0.0            # Local processing
```

**Current pricing** (October 2024):

- **Text generation**: gpt-4o-mini @ $0.150/$0.600 per 1M tokens (input/output)
  - Used for: article content, titles, slugs
  - Typical article cost: ~$0.0015-0.0020
- **Image generation**: DALL-E 3 @ $0.020 per 1024x1024 image
  - Generate square, resize locally to 1792x1024 hero + 512x512 icon
  - Cost per article: $0.02 (hero) + $0.00 (icon via Pillow)
  - **50% savings** vs direct 1792x1024 generation ($0.04)

**Total per article**: ~$0.002 (text only) or ~$0.022 (with images)

The PRICING constants in `src/generate.py` hold rates ($/token), not estimates. All costs calculated from actual API usage data.

## Content strategy and cadence

**SEO opportunity**: Capture trending topics from social platforms and create authoritative long-form content before others.

**The cycle**:

1. **Social platforms trend** (Reddit, Mastodon, HackerNews) across timezones
2. **We collect** during peak engagement (3-4x daily)
3. **We generate** comprehensive 1200-1500 word articles with research
4. **People search** for those topics later → find our deep-dive articles

**Volume and costs**:

- **3 articles per run** (default, configurable via `ARTICLES_PER_RUN` environment variable)
- **3 runs per day** aligned with timezone peaks (06:00, 18:00, 02:00 UTC) = ~9 articles/day
- **Cost**: ~$0.06-0.07/run with images = **~$0.20/day** for 9 articles
- **Quality threshold**: 0.5 minimum score (filters low-quality content)
- **Source cooldown**: 7 days (prevents same GitHub repo appearing too frequently)
- **Adaptive learning**: Deduplication and scoring patterns improve over time

**Timezone alignment** (recommended GitHub Actions schedule):

- 06:00 UTC (morning EU) - catches Asia overnight + EU morning
- 18:00 UTC (afternoon US) - catches US daytime discussions  
- 02:00 UTC (evening US) - catches late US + early Asia

## Live Site & Feeds

- Site: <https://hardcoreprawn.github.io/tech-content-curator/>
- RSS: <https://hardcoreprawn.github.io/tech-content-curator/index.xml>

## GitHub Deployment

### Initial Setup

1. **Create a new GitHub repository** for your project

2. **Configure repository secrets** (Settings → Secrets and variables → Actions):

   ```
   OPENAI_API_KEY=sk-...
   ANTHROPIC_API_KEY=sk-ant-...
   ```

3. **Enable GitHub Pages** (Settings → Pages):
   - Source: GitHub Actions
   - No custom domain configuration needed initially

4. **Update Hugo configuration**:
   - Edit `site/hugo.toml`
   - Change `baseURL` to: `https://<username>.github.io/<repo-name>/`
   - Example: `https://yourusername.github.io/tech-blog/`

5. **Push to GitHub**:

   ```bash
   git remote add origin https://github.com/<username>/<repo-name>.git
   git branch -M main
   git push -u origin main
   ```

### Automated Workflows

Three GitHub Actions workflows handle the complete pipeline:

**1. Content Pipeline (Scheduled)** (`.github/workflows/content-pipeline.yml`)

- **Schedule**: 3x daily (06:00, 18:00, 02:00 UTC)
- **Manual trigger**: Available for testing
- **Actions**:
  - Collect from HackerNews, GitHub Trending, Mastodon
  - Enrich with AI research and scoring
  - Generate 10 articles with images
  - Build Hugo site
  - Deploy to GitHub Pages
- **Outputs**: New articles in `content/posts/`, images, patterns
- **Cost**: ~$0.22 per run (10 articles with images)
- **Duration**: ~45-60 minutes
- **Use case**: Scheduled batch content creation (3x daily)

**2. Site Update (Fast)** (`.github/workflows/site-update.yml`)

- **Triggers**:
  - Push to `main` when `site/` or `content/` files change
  - Manual workflow dispatch (with optional test article)
- **Actions**:
  - Optionally generate 1 test article (if manually triggered with flag)
  - Build Hugo site
  - Deploy to GitHub Pages
- **Outputs**: Site published, optional test article
- **Cost**: ~$0.00 (site-only) or ~$0.002 (with test article)
- **Duration**: ~3-5 minutes
- **Use case**: Quick theme/design tweaks without running collection/enrichment
  - Perfect for CSS changes, layout updates, testing site design
  - Can optionally generate one article for validation

**3. Full Pipeline (Manual Override)** (`.github/workflows/full-pipeline.yml`)

- **Trigger**: Manual workflow dispatch only (with optional `max_articles` input)
- **Actions**: Same as Content Pipeline but manually triggered
- **Inputs**:
  - `max_articles`: Number of articles to generate (default: 10)
- **Use case**: "I need fresh content NOW" without waiting for scheduled run
  - Can specify how many articles to generate (1-50)
  - Full collection, enrichment, and generation cycle

### Workflow Strategy

The split workflow design optimizes for two different use cases:

**Scenario 1: Scheduled Content Batch** (Every 6 hours)

```
Content Pipeline (3x daily)
  ├── Collect content from all sources
  ├── Enrich with AI research
  ├── Generate 10 articles + images
  └── Deploy
```

- **Cost**: $0.22/run (3x daily = $0.66/day)
- **Duration**: 45-60 min
- **Benefit**: Captures trending topics on schedule, uses AI efficiently in batches

**Scenario 2: Site Tweaks & Rapid Testing** (Any time)

```
Site Update (push or manual)
  ├── Skip collection/enrichment
  ├── Optionally generate 1 test article (manual only)
  └── Deploy immediately
```

- **Cost**: $0.00 (site-only) or $0.002 (with test article)
- **Duration**: 3-5 min
- **Benefit**: Test CSS changes, theme updates, layout tweaks WITHOUT running expensive AI batch

**Scenario 3: Emergency Full Refresh** (When needed)

```
Full Pipeline (manual override)
  ├── Collect & Enrich
  ├── Generate N articles (configurable)
  └── Deploy
```

- **Cost**: $0.22 for 10 articles
- **Duration**: 45-60 min
- **Benefit**: Manual control—generate 1-50 articles whenever you need fresh content

### Manual Triggers

Workflows can be manually triggered via GitHub Actions UI:

- Repository → Actions → Select workflow → Run workflow

**Site Update** workflow supports an optional input:

- `generate_article`: Set to `true` to generate 1 test article before deploying
  - Useful for testing site changes with realistic content
  - Adds ~5-10 minutes to deployment

### Monitoring

- **GitHub Actions**: Monitor workflow runs, check logs for errors
- **Costs**: Review `generation_costs` in article frontmatter
- **Quality**: Check enriched JSON files for quality score distribution
- **Cooldown**: Watch for "⏸ In cooldown" messages in generation logs

### Migration from Old Pipeline

If you had a single `pipeline.yml`:

1. **Delete the old pipeline**:

   ```bash
   rm .github/workflows/pipeline.yml
   ```

2. **The three new workflows are now in place**:
   - `.github/workflows/content-pipeline.yml` - Runs on schedule
   - `.github/workflows/site-update.yml` - Runs on push/manual
   - `.github/workflows/full-pipeline.yml` - Manual override only

3. **Test the workflows**:
   - Push a small site change to trigger `site-update.yml` (should be fast)
   - Manually trigger `content-pipeline.yml` via GitHub UI to test collection flow
   - Manually trigger `full-pipeline.yml` with custom article count

4. **Verify scheduling**:
   - Wait for next scheduled time (06:00, 18:00, or 02:00 UTC) to confirm `content-pipeline.yml` runs automatically

### Cost Management

- **Daily cost**: ~$0.44-0.66 for 2-3 automated runs
- **Monthly cost**: ~$13-20 for 20-30 articles/day
- **Scaling**: Adjust `ARTICLES_PER_RUN` or schedule frequency as needed

## File Structure

```
content-curator/
├── README.md                 # This file
├── SETUP.md                 # Development setup guide
├── pyproject.toml           # Python 3.14+ dependencies
├── .env.example             # Template for API keys
│
├── .github/workflows/       # Automated pipelines
│   ├── content-pipeline.yml # Scheduled 3x daily
│   ├── site-update.yml     # Quick deploy
│   └── full-pipeline.yml   # Manual override
│
├── src/
│   ├── collectors/          # Multi-source content collection
│   │   ├── hackernews.py   # HackerNews top stories
│   │   ├── github.py       # GitHub Trending
│   │   ├── mastodon.py     # Mastodon feeds
│   │   └── reddit.py       # Reddit subreddits
│   ├── enrichment/          # AI research and scoring
│   ├── deduplication/       # Adaptive dedup system
│   ├── generators/          # Article generation
│   │   ├── base.py         # Abstract base
│   │   ├── general.py      # Standard articles
│   │   ├── integrative.py  # Integrative guides
│   │   ├── voices/         # 5 writing styles
│   │   └── specialized/    # Topic-specific
│   ├── illustrations/       # Visual generation
│   │   ├── ai_mermaid_generator.py
│   │   ├── ai_ascii_generator.py
│   │   ├── placement.py
│   │   └── accessibility.py
│   ├── pipeline/            # Modular orchestration
│   │   ├── orchestrator.py # Main coordinator
│   │   ├── diversity_selector.py
│   │   ├── illustration_service.py
│   │   └── article_builder.py
│   ├── images/              # Image generation
│   ├── citations/           # Citation resolution
│   ├── models.py            # Pydantic models
│   └── config.py            # Configuration
│
├── tests/                   # ~100 test cases
│   ├── test_illustrations.py
│   ├── test_generators.py
│   ├── test_deduplication.py
│   └── ...
│
├── content/posts/           # 163 generated articles
├── site/                    # Hugo site + PaperMod
├── data/                    # JSON data + patterns
└── docs/                    # Architecture docs
```

## Architecture Principles

### 1. Keep It Simple

- **One Python script per pipeline stage** (collect, enrich, generate, publish)
- **Synchronous by default** - use async only when actually beneficial
- **Files for storage** - JSON files work fine, no databases needed yet
- **Manual triggers** - run scripts when you want, add automation later

### 2. Type Everything

```python
from pydantic import BaseModel
from datetime import datetime

class CollectedItem(BaseModel):
    """Every data structure is a Pydantic model."""
    id: str
    title: str
    content: str
    source: str  # "reddit", "mastodon", "bluesky"
    url: str
    collected_at: datetime
    metadata: dict[str, Any]
```

### 3. Make It Observable

```python
from rich.console import Console
console = Console()

def collect_content():
    console.print("[bold blue]Starting collection...[/bold blue]")
    
    items = fetch_from_sources()
    
    console.print(f"[green]✓[/green] Collected {len(items)} items")
    return items
```

### 4. Fail Fast, Fail Clear

```python
# Good: Clear error messages
if not OPENAI_API_KEY:
    raise ValueError(
        "OPENAI_API_KEY not found. "
        "Add it to .env file or set environment variable."
    )

# Bad: Silent failures, generic errors
try:
    result = some_complex_thing()
except Exception:
    pass  # Don't do this
```

## AI Agent Guidelines

**For GitHub Copilot / other AI coding assistants:**

### DO

- ✅ Use type hints everywhere (`def func(x: int) -> str:`)
- ✅ Keep functions under 50 lines
- ✅ Write docstrings with examples
- ✅ Use Pydantic models for data structures
- ✅ Add logging/console output for visibility
- ✅ Validate inputs early
- ✅ Return typed results, not dicts

### DON'T

- ❌ Add async/await unless actually needed (95% of the time you don't need it)
- ❌ Create classes when functions work fine
- ❌ Add database/queue/cache until proven necessary
- ❌ Use "enterprise patterns" (factories, singletons, dependency injection frameworks)
- ❌ Create abstractions for one use case
- ❌ Add containers/Docker until deployment time
- ❌ Suggest microservices - this is a simple pipeline

### EXCEPTION - When Abstractions Are OK

Sometimes a simple class hierarchy makes sense. Use it when:

- ✅ You have **3+ similar implementations** that share a pattern
- ✅ User explicitly requests **extensibility** for future growth
- ✅ The abstraction is **straightforward** (not factory/DI/builder patterns)
- ✅ Each implementation is **self-contained** and understandable

**Example:** This project uses generator classes for different article types (general, integrative guides, specialized topics). Each generator is ~120 lines, simple to understand, and easy to add new ones. The abstract base is minimal (just `can_handle()` and `generate_content()`). This is acceptable pragmatic abstraction, not enterprise over-engineering.

### When AI Suggests Complexity

If an AI agent suggests:

- "Let's add a message queue" → **NO** - use files or simple Python functions
- "Let's use async/await" → **MAYBE** - only if doing concurrent I/O (rare)
- "Let's create an abstract base class" → **NO** - start with simple functions
- "Let's add caching" → **LATER** - only if you measure a performance problem
- "Let's use Docker" → **LATER** - develop locally first
- "Let's add a database" → **NO** - JSON files work fine for this scale

**Push back!** Ask: "Can this be simpler? Can we use the standard library?"

## Getting Started

### 1. First-Time Setup (10 minutes)

```bash
# Install uv (modern Python package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone/create your repo
cd your-new-repo/

# Create a project-local virtual environment with Python 3.14+
uv venv --python 3.14

# No need to activate with uv; use `uv run` to execute inside the venv

# Install dependencies with dev tools
uv sync --all-extras

# Copy environment template
cp .env.example .env
# Edit .env and add your API keys (OPENAI_API_KEY required)
```

**Python 3.14 Benefits**: Free-threading support provides 3-4x speedup on article generation when GIL is disabled (`export PYTHON_GIL=0`).

### uv as default, Python versions, and the .venv

- This repo uses uv for everything (install, run, test). Prefer `uv run ...` over calling `python` directly.
- The dev container may have system Python 3.11, but this project’s `.venv` targets Python 3.13 by default when available.
- `uv run` automatically uses `.venv` so you don’t have to activate it. Verify with:

```bash
uv run python -V  # should print Python 3.13.x if available
```

If you need to recreate the venv on a specific version, run:

```bash
rm -rf .venv
uv venv --python 3.13  # or 3.12/3.11
uv pip install -e .[dev]
```

### 2. Development Workflow (uv-first)

```bash
# Collect content from social media
uv run python -m src.collect

# Enrich with research
uv run python -m src.enrich

# Generate articles (with options)
uv run python -m src.generate                    # New articles only
uv run python -m src.generate --force-regenerate # Regenerate existing
uv run python -m src.generate --dry-run          # Preview without generating
uv run python -m src.generate --max-articles 5   # Generate more

# Publish to GitHub Pages
uv run python -m src.publish

# Or run full pipeline
uv run python -m src.pipeline  # Runs all steps
```

#### Reddit rate limit settings (optional)

You can tweak Reddit throttling via environment variables:

```
# Max requests per minute overall and short burst size
REDDIT_REQUESTS_PER_MINUTE=30
REDDIT_BURST=5

# Delay between subreddit requests
REDDIT_REQUEST_INTERVAL_SECONDS=1.0

# Retry behavior for 429/5xx
REDDIT_MAX_RETRIES=3
REDDIT_BACKOFF_BASE=2.0
REDDIT_BACKOFF_MAX=60.0
```

These keep our usage within Reddit's limits and reduce the chance of temporary blocks.

#### Content relevance filtering (optional)

Control what types of content pass through collection:

```
# Topic toggles (true/false)
ALLOW_TECH_CONTENT=true       # Technical content (programming, tools, etc.)
ALLOW_SCIENCE_CONTENT=true    # Research, papers, astronomy, etc.
ALLOW_POLICY_CONTENT=true     # Tech policy, regulations, privacy laws

# Custom negative keywords (comma-separated)
RELEVANCE_NEGATIVE_KEYWORDS=recipe,baking,cooking,gardening,jigsaw,puzzle,sports,fashion,music,movie
```

These filters are applied during collection to save API costs on enrichment. Add your own keywords to fine-tune what gets filtered out.

### 3. Quality Checks (uv)

```bash
# Type checking
uv run mypy src/

# Linting and formatting
uv run ruff check src/
uv run ruff format src/

# Run tests
uv run pytest tests/ -v

# All checks
make check  # or create a simple script
```
