"""Tech Content Curator - Source Package

This package contains the core pipeline for curating and generating tech content
from social media sources.

Package Structure (Post-Reorganization):

    src/
    ├── config.py              # Pipeline configuration
    ├── models.py              # Shared data models
    ├── costs.py               # API cost tracking
    │
    ├── pipeline/              # Main pipeline orchestration
    │   ├── collect.py         # (To be refactored from root)
    │   ├── enrich.py          # (To be refactored from root)
    │   └── generate.py        # (To be refactored from root)
    │
    ├── collectors/            # Content source collectors
    │   ├── mastodon.py        # (To be extracted from collect.py)
    │   ├── bluesky.py         # (To be extracted from collect.py)
    │   ├── reddit.py          # (To be extracted from collect.py)
    │   └── hackernews.py      # (To be extracted from collect.py)
    │
    ├── enrichment/            # AI enrichment and scoring
    │   ├── scorer.py          # (To be extracted from enrich.py)
    │   ├── researcher.py      # (To be extracted from enrich.py)
    │   ├── analyzer.py        # (To be extracted from enrich.py)
    │   ├── adaptive_scoring.py # (Moved from root)
    │   └── fact_check.py      # (Moved from root)
    │
    ├── deduplication/         # Deduplication strategies
    │   ├── semantic_dedup.py  # (Moved from root)
    │   ├── story_clustering.py # (Moved from root)
    │   ├── adaptive_dedup.py  # (Moved from root)
    │   ├── post_gen_dedup.py  # (Moved from root)
    │   ├── dedup_feedback.py  # (Moved from root)
    │   └── recent_content_cache.py # (Moved from root)
    │
    ├── generators/            # Article generators [EXISTING]
    ├── citations/             # Citation management [EXISTING]
    ├── images/                # Image management [EXISTING]
    ├── content/               # Article management [NEW]
    ├── sources/               # Source quality management [NEW]
    ├── api/                   # API client wrappers [NEW]
    └── utils/                 # Shared utilities [EXISTING]

Data Flow:
    1. Collection (collectors/) -> CollectedItem
    2. Enrichment (enrichment/) -> EnrichedItem
    3. Deduplication (deduplication/) -> Filtered EnrichedItems
    4. Generation (generators/) -> GeneratedArticle
    5. Publishing (content/) -> Saved Article Files

Migration Status:
    ✅ Phase 1: Directory structure created (COMPLETE)
    ⏳ Phase 2: Move complete modules
    ⏳ Phase 3: Refactor collect.py
    ⏳ Phase 4: Refactor enrich.py
    ⏳ Phase 5: Refactor generate.py
    ⏳ Phase 6: Move utility files
    ⏳ Phase 7: Testing and validation
"""

__version__ = "0.2.0"  # Bumped for reorganization

# Core models and config are always available
from .config import PipelineConfig, get_config, get_content_dir, get_data_dir
from .models import CollectedItem, EnrichedItem, GeneratedArticle

__all__ = [
    "CollectedItem",
    "EnrichedItem",
    "GeneratedArticle",
    "PipelineConfig",
    "get_config",
    "get_data_dir",
    "get_content_dir",
]
