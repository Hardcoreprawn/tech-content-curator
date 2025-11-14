# Model Testing & Selection Guide

This guide explains how to test and compare different AI models to find the optimal balance of quality, cost, and performance for your content generation pipeline.

## Overview

The project includes two complementary testing tools:

1. **`compare_models.py`** - Compare individual models on identical tasks
2. **`ab_test_models.py`** - Test complete model configurations across all pipeline roles

## Quick Start

### Basic Model Comparison

Test 3 models with 10 iterations each:

```bash
python scripts/compare_models.py \
  --models gpt-4o-mini gpt-5-mini gpt-5.1 \
  --iterations 10
```

### A/B Testing Model Combinations

Test all predefined configurations with 5 iterations:

```bash
python scripts/ab_test_models.py --iterations 5
```

Test with adaptive pruning (keeps top 3 after 3 iterations):

```bash
python scripts/ab_test_models.py \
  --iterations 10 \
  --adaptive \
  --prune-after 3 \
  --keep-top 3
```

## Tool 1: Individual Model Comparison

### Purpose

Tests individual models on a single standardized prompt to compare:
- Token efficiency (input/output ratios)
- Generation speed
- Cost per request
- Response consistency across iterations

### Usage

```bash
python scripts/compare_models.py [OPTIONS]
```

**Key Options:**

- `--models MODEL1 MODEL2 ...` - Models to compare (default: viable GPT-5 and GPT-4o variants)
- `--iterations N` - Number of test runs per model (default: 10)
- `--prompt TEXT` - Custom prompt to use
- `--temperature FLOAT` - Temperature setting (default: 0.7)
- `--output FILE` - Save detailed results to JSON

**Example Output:**

```
Model Comparison Results (Averaged)
┌──────────────┬────────────┬────────────┬───────┬──────────────────┬──────────────────┬───────────────┬──────────────┐
│ Model        │ Status     │ Iterations │ Words │ Tokens (in/out)  │ Time (s)         │ Cost ($)      │ $/1K words   │
├──────────────┼────────────┼────────────┼───────┼──────────────────┼──────────────────┼───────────────┼──────────────┤
│ gpt-4o-mini  │ ✓ 10/10    │ 10         │ 154   │ 50/235           │ 4.4 (3.8-5.2)    │ 0.000145      │ 0.000941     │
│ gpt-5-mini   │ ✓ 10/10    │ 10         │ 162   │ 52/487           │ 6.2 (5.1-7.8)    │ 0.000987      │ 0.006093     │
│ gpt-5.1      │ ✓ 10/10    │ 10         │ 137   │ 52/250           │ 4.1 (3.5-4.9)    │ 0.003036      │ 0.022161     │
└──────────────┴────────────┴────────────┴───────┴──────────────────┴──────────────────┴───────────────┴──────────────┘

Summary:
  Best Value: gpt-4o-mini ($0.000941 per 1K words)
  Fastest: gpt-5.1 (4.1s avg, 3.5s min)
  Most Consistent: gpt-4o-mini (±1.4s variance)
```

### Interpreting Results

**Token Efficiency:**
- Low output tokens relative to content = efficient
- High output tokens = model using tokens for internal reasoning
- Example: gpt-5-nano uses 2176 tokens for 162 words (wasteful)

**Cost Per 1K Words:**
- Best metric for comparing value
- Accounts for both pricing and token efficiency
- Lower is better for budget optimization

**Time Variance:**
- Shows consistency of performance
- Lower variance = more predictable
- Important for time-sensitive workflows

## Tool 2: A/B Testing Model Combinations

### Purpose

Tests complete model configurations across all pipeline roles:
- **Content generation** (main article body)
- **Title generation** (headlines)
- **Enrichment** (meta descriptions, tags)
- **Review** (quality checks)

Calculates total cost per article and estimates monthly budget impact.

### Predefined Configurations

The tool includes 5 carefully designed configurations:

1. **Budget (All 4o-mini)**
   - All roles: `gpt-4o-mini`
   - Best for: Minimal cost, proven quality
   - Estimated: ~$0.25/month (270 articles)

2. **Mixed (5.1 content, 4o-mini other)**
   - Content: `gpt-5.1`
   - Others: `gpt-4o-mini`
   - Best for: Premium content, budget-conscious support tasks

3. **GPT-5 Mini (all roles)**
   - All roles: `gpt-5-mini`
   - Best for: Testing GPT-5 family without high costs

4. **Selective 5.1 (content & review)**
   - Content & Review: `gpt-5.1`
   - Title & Enrichment: `gpt-4o-mini`
   - Best for: Quality-focused on high-impact roles

5. **Premium (All 5.1)**
   - All roles: `gpt-5.1`
   - Best for: Maximum quality, budget not a concern

### Usage

```bash
python scripts/ab_test_models.py [OPTIONS]
```

**Key Options:**

- `--iterations N` - Test runs per config (default: 5)
- `--configs budget mixed ...` - Test specific configs only
- `--adaptive` - Enable smart pruning of poor performers
- `--prune-after N` - Iterations before pruning (default: 3)
- `--keep-top N` - Top performers to keep (default: 3)
- `--output FILE` - Save results to JSON

**Example Output:**

```
A/B Test Results Summary
┌──────────────────────────┬─────────┬──────────────┬───────────────┬────────────────┬───────────────┬──────────────┐
│ Configuration            │ Success │ Cost/Article │ Time/Article  │ Monthly Cost   │ Content Model │ Other Models │
├──────────────────────────┼─────────┼──────────────┼───────────────┼────────────────┼───────────────┼──────────────┤
│ Budget (All 4o-mini)     │ ✓ 5/5   │ $0.000923    │ 18.2s         │ $0.25          │ gpt-4o-mini   │ Same         │
│ Mixed (5.1 content, ...) │ ✓ 5/5   │ $0.019487    │ 17.8s         │ $5.26          │ gpt-5.1       │ gpt-4o-mini  │
│ Selective 5.1 (...)      │ ✓ 5/5   │ $0.038234    │ 18.1s         │ $10.32         │ gpt-5.1       │ gpt-4o-mini  │
└──────────────────────────┴─────────┴──────────────┴───────────────┴────────────────┴───────────────┴──────────────┘

Recommendations:
  💰 Best Value: Budget (All 4o-mini)
     $0.000923/article, $0.25/month

  ⚡ Fastest: Mixed (5.1 content, 4o-mini other)
     17.8s per article

Cost vs Best Value:
  Mixed (5.1 content, 4o-mini other): 21.1x more (+$5.01/month)
  Selective 5.1 (content & review): 41.4x more (+$10.07/month)
```

### Adaptive Testing

Adaptive mode intelligently prunes poor-performing configurations to focus testing resources:

```bash
python scripts/ab_test_models.py \
  --iterations 10 \
  --adaptive \
  --prune-after 3 \
  --keep-top 3
```

**How it works:**
1. Run first 3 iterations on all configs
2. Rank by average cost per article
3. Keep only top 3 performers
4. Continue remaining 7 iterations on winners

**Benefits:**
- Saves API costs by not testing obvious losers
- Gathers more data on promising configs
- Useful when testing many custom configurations

## Custom Testing Scenarios

### Testing Specific Model Pairs

```bash
# Compare just the two most viable options
python scripts/compare_models.py \
  --models gpt-4o-mini gpt-5.1 \
  --iterations 20
```

### Testing Only Budget Options

```bash
# Test only budget-friendly configs
python scripts/ab_test_models.py \
  --configs budget mixed \
  --iterations 10
```

### High-Confidence Testing

```bash
# More iterations for statistical significance
python scripts/ab_test_models.py \
  --iterations 20 \
  --adaptive \
  --prune-after 5
```

## Decision Framework

### When to Use Each Tool

**Use `compare_models.py` when:**
- Investigating a specific model's characteristics
- Understanding token usage patterns
- Debugging performance issues
- Validating new model releases

**Use `ab_test_models.py` when:**
- Deciding which config to deploy
- Estimating budget impact
- Comparing role-specific model assignments
- Testing custom model combinations

### Making Your Decision

**Step 1: Run Individual Comparison**
```bash
python scripts/compare_models.py \
  --models gpt-4o-mini gpt-5-mini gpt-5.1 \
  --iterations 10
```

Identify which models are viable (good cost/performance ratio).

**Step 2: Run A/B Test**
```bash
python scripts/ab_test_models.py \
  --iterations 10 \
  --adaptive
```

See how viable models perform across all pipeline roles.

**Step 3: Evaluate Results**

Consider:
- **Budget**: Can you afford 10x-40x cost increase?
- **Quality**: Will users notice the difference?
- **Speed**: Does generation time matter for your workflow?
- **Consistency**: How important is predictable behavior?

**Step 4: Deploy Winner**

Update `src/config.py`:

```python
# config.py
content_model = "gpt-4o-mini"  # Your choice here
title_model = "gpt-4o-mini"
enrichment_model = "gpt-4o-mini"
review_model = "gpt-4o-mini"
```

## Recommendations

### For Most Users

**Start with:** Budget (All 4o-mini)
- Proven quality from testing
- ~$0.25/month for 270 articles
- Fast, consistent performance

### For Premium Quality

**Consider:** Mixed (5.1 content, 4o-mini other)
- Latest GPT-5.1 for main content
- Budget models for support tasks
- ~$5/month - significant but manageable increase

### Models to Avoid

❌ **gpt-5-nano** - 8.7x token overhead makes it slow and expensive
❌ **gpt-5-mini** - Similar cost to gpt-5.1 but older
❌ **gpt-5** (standard) - No advantage over gpt-5.1, more expensive
❌ **gpt-5-codex** variants - Unnecessary for article generation

### Testing Schedule

**Quarterly Review:**
```bash
# Full test every 3 months
python scripts/ab_test_models.py --iterations 20
```

**After Model Updates:**
```bash
# Quick check when OpenAI releases new models
python scripts/compare_models.py --models NEW_MODEL gpt-4o-mini --iterations 10
```

## Understanding the Data

### Results Files

Both tools save detailed JSON results:

- `data/model_comparison.json` - Individual model test data
- `data/ab_test_results.json` - Configuration test data

### JSON Structure

**Model Comparison:**
```json
{
  "timestamp": "2025-11-14T10:30:00",
  "iterations": 10,
  "models": {
    "gpt-4o-mini": {
      "avg_cost": 0.000145,
      "avg_elapsed_seconds": 4.4,
      "avg_output_tokens": 235,
      "runs": [...]
    }
  }
}
```

**A/B Test:**
```json
{
  "timestamp": "2025-11-14T10:30:00",
  "configs": {
    "Budget (All 4o-mini)": {
      "avg_total_cost": 0.000923,
      "monthly_cost_estimate_270_articles": 0.25,
      "role_breakdown": {
        "content": {"model": "gpt-4o-mini", "avg_cost": 0.000523},
        "title": {"model": "gpt-4o-mini", "avg_cost": 0.000145}
      }
    }
  }
}
```

## Troubleshooting

### Model Returns Empty Responses

This is a known issue with GPT-5 models when `max_completion_tokens` is set. The wrapper automatically handles this, but if you see it:

1. Check that you're using `create_chat_completion()` from our wrapper
2. Verify the model name is correct
3. Check logs for fallback messages

### Tests Taking Too Long

Reduce iterations for quick checks:
```bash
python scripts/ab_test_models.py --iterations 3
```

Or use adaptive mode to prune early:
```bash
python scripts/ab_test_models.py --adaptive --prune-after 2
```

### Cost Estimates Don't Match Production

A/B tests use simplified prompts. Real articles have:
- Longer prompts (with source material)
- Variable content lengths
- Multiple revision passes

Multiply test costs by 1.5-2x for realistic estimates.

## Advanced: Custom Configurations

You can test custom model combinations by modifying `ab_test_models.py`:

```python
# Add to CONFIGS list
CONFIGS.append(
    ModelConfig(
        name="Custom Mix",
        content_model="gpt-5.1",
        title_model="gpt-4o-mini",
        enrichment_model="gpt-4o-mini",
        review_model="gpt-4o",  # Higher quality review
    )
)
```

Then run:
```bash
python scripts/ab_test_models.py --configs custom
```

## Related Documentation

- [MODEL-SELECTION-GUIDE.md](MODEL-SELECTION-GUIDE.md) - General model selection guidance
- [CREDIT-MANAGEMENT-QUICKSTART.md](CREDIT-MANAGEMENT-QUICKSTART.md) - Budget monitoring
- [QUICK-REFERENCE.md](QUICK-REFERENCE.md) - Configuration reference
