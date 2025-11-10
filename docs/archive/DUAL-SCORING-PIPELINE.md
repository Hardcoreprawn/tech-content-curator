## Dual-Scoring Pipeline Redesign

**Date**: November 5, 2025  
**Issue**: No new articles generated despite good quality content - need data-driven approach to scoring

### What Changed

#### 1. **Enrichment Scoring (Two-Stage)**
- **Before**: Heuristic (30%) + AI (70%) = Combined score
- **After**: 
  - Heuristic: Used for pre-filtering analysis only (no rejection)
  - AI: Primary quality signal (what we trust)
  - Both scores stored for comparison

#### 2. **Model Changes** (`src/models.py`)
- Added `heuristic_score: float` field to `EnrichedItem`
- Added `ai_score: float` field to `EnrichedItem`
- Renamed `quality_score` description to clarify it's AI-based

#### 3. **Enrichment Pipeline** (`src/enrichment/orchestrator.py`)
- Changed from combined scoring to AI-only scoring
- Heuristic still calculated but now tracked separately
- AI >= 0.3 threshold for research (lowered from 0.5 to capture more context)
- All scores logged with both values visible

#### 4. **Candidate Selection** (`src/pipeline/candidate_selector.py`)
- Uses AI score >= 0.5 threshold (trust AI, not combined)
- Rejection logs now show both heuristic and AI scores
- Better visibility into why items were filtered

#### 5. **Pipeline Tracking** (`src/pipeline/tracking.py`) - NEW
- New module that tracks every item through the pipeline
- Records:
  - Enrichment scores (heuristic + AI)
  - Candidate selection decisions
  - Generation outcomes
  - Topics identified
  - Rejection reasons
- Saves to `data/pipeline_tracking.json` for post-analysis
- Includes summary statistics on startup

#### 6. **Generation Orchestrator** (`src/pipeline/orchestrator.py`)
- Instantiates `PipelineTracker` 
- Calls `tracker.track_generation()` for each article
- Prints summary and saves data at end
- All import updates for tracking module

### Data-Driven Benefits

1. **Visibility**: Every item tracked from enrichment → generation
2. **Analysis**: Can now compare heuristic vs AI scores post-run
3. **No Rejections Yet**: Both scoring methods run, no data lost
4. **Logging**: Rich console and file logging for debugging

### Next Steps (Manual Analysis)

After running the pipeline, check:

```bash
# View tracking data
cat data/pipeline_tracking.json | jq '.runs[-1].items[] | {title, stage, scores}' | head -20

# Compare heuristic vs AI
uv run python << 'EOF'
import json
with open('data/pipeline_tracking.json') as f:
    data = json.load(f)
    items = data['runs'][-1]['items']
    enriched = [i for i in items if i['stage'] == 'enrichment']
    h_scores = [i['scores']['heuristic'] for i in enriched]
    a_scores = [i['scores']['ai'] for i in enriched]
    print(f"Heuristic: mean={sum(h_scores)/len(h_scores):.2f}")
    print(f"AI: mean={sum(a_scores)/len(a_scores):.2f}")
EOF
```

### Tuning Strategy

Once you have one or two runs of data:

1. **Compare score distributions** between heuristic and AI
2. **Analyze which items passed/failed** and why
3. **Decide**: 
   - Keep AI-only approach (simpler, more content)
   - Adjust threshold (e.g., 0.45 instead of 0.5)
   - Add pre-filter on heuristic (e.g., skip < 0.15 to save API calls)

### Files Modified

- `src/models.py` - Added score tracking fields
- `src/enrichment/orchestrator.py` - Dual scoring, AI-based final score
- `src/pipeline/orchestrator.py` - Pipeline tracking integration
- `src/pipeline/candidate_selector.py` - Better logging
- `.github/workflows/content-pipeline.yml` - Already updated to save enriched data

### Testing

All files verified to compile:
```
✅ src/pipeline/tracking.py
✅ src/enrichment/orchestrator.py
✅ src/pipeline/orchestrator.py
✅ src/models.py
```

The next pipeline run will generate tracking data you can analyze.
