# Model Evaluation Strategy

## Key Learnings from Testing

### 1. Token Efficiency Varies by Task Length

**Short Tasks (200 words):**
- GPT-5.1: 1.8 tokens/word
- GPT-4o-mini: 1.4 tokens/word
- GPT-5-mini: 13.8 tokens/word (massive reasoning overhead)

**Long Tasks (1500+ words):**
- GPT-5.1: 1.5 tokens/word (improved!)
- GPT-4o-mini: 1.2 tokens/word (improved!)

**Insight:** Both models become MORE efficient on longer content. The reasoning overhead is amortized over more output.

### 2. "Cheaper" ≠ Lower Cost

Our A/B testing revealed counterintuitive results:
- **Premium (All 5.1)**: $1.52/month
- **Budget (All 4o-mini)**: $2.22/month (46% MORE expensive!)

This happens because:
- Higher per-token pricing can be offset by token efficiency
- Faster models = less API overhead
- Multiple short API calls add up

### 3. Model Behavior Changes with Context

**GPT-5-mini:** 
- Terrible on short tasks (70s for 200 words)
- Reasoning overhead dominates small outputs
- Not viable for production

**GPT-5.1 & GPT-4o-mini:**
- Both excellent on short and long tasks
- Predictable token usage
- Production ready

## Ongoing Evaluation Framework

### Principle: Test in Production Context

Instead of synthetic benchmarks, use real article generation as our testing ground:

### 1. New Model Detection & Quick Test

When a new model is released:

```bash
# Quick 10-iteration comparison
python scripts/compare_models.py \
  --models NEW_MODEL gpt-5.1 gpt-4o-mini \
  --iterations 10 \
  --parallel 30
```

**Decision criteria:**
- ✅ Tokens/word < 2.0 (efficient)
- ✅ Cost per 1K words competitive with existing models
- ✅ Speed within 2x of current fastest
- ✅ No empty response issues

If all pass, proceed to A/B test.

### 2. A/B Configuration Test

Add new model to configurations:

```python
# In ab_test_models.py
CONFIGS.append(
    ModelConfig(
        name="New Model Test",
        content_model="new-model",
        title_model="gpt-4o-mini",  # Keep others stable
        enrichment_model="gpt-4o-mini",
        review_model="gpt-4o-mini",
    )
)
```

Run adaptive test:
```bash
python scripts/ab_test_models.py \
  --iterations 10 \
  --adaptive \
  --prune-after 3 \
  --keep-top 3 \
  --parallel 40
```

**Decision criteria:**
- Must be in top 3 after pruning
- Must be within 50% cost of best current option
- Check quality/readability scores

### 3. Production Shadow Testing

If A/B results look promising, integrate into actual pipeline:

**Option A: Random A/B in Production**
- 10% of articles use new model
- Track quality scores, costs, user engagement
- Compare over 1 week (270 articles = 27 with new model)

**Option B: Batch Comparison**
- Generate same article with multiple models
- Compare outputs side-by-side
- Use for quality assessment

### 4. Format & Length Testing

Test models on diverse content types:

```bash
# Long-form (1500+ words)
python scripts/test_complex_article.py --models NEW_MODEL gpt-5.1

# Short-form (500 words)
python scripts/compare_models.py --models NEW_MODEL --prompt "Write a 500-word..."

# Different formats:
# - Tutorial with code examples
# - News summary
# - Technical deep-dive
# - Opinion/analysis piece
```

**Track:**
- Token efficiency by length
- Quality by format
- Cost by content type

## Continuous Monitoring Strategy

### Monthly Model Review

**First week of each month:**

1. **Check for new models**
   - Monitor OpenAI announcements
   - Check API documentation for new model names

2. **Review current performance**
   ```bash
   # Analyze last month's actual usage
   python scripts/analyze_model_performance.py --month last
   ```
   
3. **Quick retest current models**
   ```bash
   # Verify no degradation
   python scripts/compare_models.py --iterations 5
   ```

### Quarterly Deep Evaluation

**Every 3 months:**

1. Full A/B test on all available models
2. Test on diverse content types
3. Evaluate new GPT family releases
4. Update pricing database

### Production Experimentation

#### Strategy 1: Rotating Model Days

```python
# In config.py
day_of_week = datetime.now().weekday()
if day_of_week == 0:  # Monday
    content_model = "experimental-model"
else:
    content_model = "gpt-5.1"
```

Benefits:
- Real-world testing
- Consistent sample size
- Easy to track by day

#### Strategy 2: Category-Based Testing

```python
# Different models for different topics
if "ai" in tags or "machine-learning" in tags:
    content_model = "gpt-5.1"  # Best for AI content
elif "tutorial" in tags:
    content_model = "gpt-4o-mini"  # Fast for tutorials
```

Benefits:
- Optimize per content type
- Natural A/B testing
- Track effectiveness by category

#### Strategy 3: Quality-Tiered Generation

```python
# Two-pass generation for high-value content
if item.engagement_score > 0.7:  # High quality source
    # Use premium model
    content_model = "gpt-5.1"
else:
    # Use budget model
    content_model = "gpt-4o-mini"
```

Benefits:
- Cost optimization
- Quality where it matters
- Automatic value alignment

## Testing Infrastructure Improvements

### 1. Automated Model Comparison Tool

Create scheduled job:

```bash
#!/bin/bash
# Compare models weekly
# Run every Monday at 2 AM

cd /path/to/project
source .venv/bin/activate

python scripts/compare_models.py \
  --models gpt-5.1 gpt-4o-mini \
  --iterations 20 \
  --parallel 40 \
  --output "data/weekly_comparison_$(date +%Y%m%d).json"

# Alert if costs change significantly
python scripts/check_cost_drift.py
```

### 2. Cost Anomaly Detection

Monitor for:
- Sudden token/word ratio increases
- Cost spikes
- Speed degradations
- Empty response patterns

Alert thresholds:
- Tokens/word > 2.5x baseline
- Cost > 1.5x expected
- Speed > 2x baseline
- Empty responses > 1%

### 3. Quality Drift Detection

Track over time:
- Readability scores
- Article structure quality
- Technical depth
- User engagement metrics

## Decision Matrix

### When to Switch Models

**Switch immediately if:**
- ❌ Empty responses > 5%
- ❌ Cost > 2x current model with no quality improvement
- ❌ Speed > 3x slower than alternatives
- ❌ Consistent quality issues

**Investigate if:**
- ⚠️ Cost increases 25%+
- ⚠️ Token efficiency degrades 20%+
- ⚠️ New model offers 30%+ cost savings
- ⚠️ Quality scores drop 10%+

**Consider switch if:**
- ✅ New model is 50%+ cheaper with equivalent quality
- ✅ 2x faster with acceptable quality tradeoff
- ✅ Better quality scores at reasonable cost increase
- ✅ More token efficient for our common use cases

### Model Selection by Use Case

Based on current testing:

| Use Case | Best Model | Rationale |
|----------|-----------|-----------|
| Standard articles (1500w) | gpt-5.1 | Best quality, surprisingly cheapest |
| Bulk generation (100+) | gpt-5.1 | Efficiency at scale, consistency |
| Quick summaries (<500w) | gpt-4o-mini | Fast, cheap for short content |
| Complex technical (2000w+) | gpt-5.1 | Token efficiency improves with length |
| Title generation | gpt-4o-mini | Simple task, no benefit from premium |
| Meta descriptions | gpt-4o-mini | Very short, speed matters |
| Quality reviews | gpt-5.1 | Sophistication worth the cost |

## Experimentation Guidelines

### Safe Experimentation

**Low Risk:**
- ✅ Title/description generation (easily regenerated)
- ✅ 10% random sampling in production
- ✅ Weekend-only experimental models
- ✅ Category-specific trials

**Medium Risk:**
- ⚠️ Primary content generation with fallback
- ⚠️ 50% A/B split on new models
- ⚠️ Full day experimental model usage

**High Risk:**
- ❌ Switching all production to unproven model
- ❌ No fallback for experimental models
- ❌ Testing on high-engagement content only

### Experiment Lifecycle

1. **Hypothesis**: "Model X will reduce costs by Y% while maintaining quality"
2. **Test**: Run A/B comparison over N articles
3. **Measure**: Track cost, quality, speed, user engagement
4. **Analyze**: Statistical significance of results
5. **Decide**: Keep, iterate, or abandon
6. **Document**: Record learnings for future reference

## Cost Prediction Formula

Based on our findings:

```python
def estimate_monthly_cost(
    model: str,
    articles_per_month: int = 270,
    avg_words: int = 1500,
):
    """Estimate monthly cost based on test data."""
    
    # Token efficiency by model (from testing)
    tokens_per_word = {
        "gpt-5.1": 1.5,
        "gpt-4o-mini": 1.2,
        "gpt-5-mini": 13.8,  # Don't use!
    }
    
    # Pricing per 1M tokens
    output_pricing = {
        "gpt-5.1": 12.00,
        "gpt-4o-mini": 0.60,
        "gpt-5-mini": 2.00,
    }
    
    # Calculate for all 4 roles (content, title, enrichment, review)
    # Assuming: content=1500w, title=10w, enrichment=150w, review=100w
    total_words = 1500 + 10 + 150 + 100  # 1760 words/article
    
    tokens = total_words * tokens_per_word[model]
    cost_per_article = (tokens / 1_000_000) * output_pricing[model]
    
    return cost_per_article * articles_per_month
```

## Action Items

### Immediate (This Week)
- [x] Document current model performance baselines
- [x] Create testing scripts (compare_models.py, ab_test_models.py)
- [ ] Set up weekly model comparison cron job
- [ ] Create cost alerting system

### Short Term (This Month)
- [ ] Implement shadow A/B testing in production
- [ ] Add model performance tracking to dashboard
- [ ] Create model comparison report generator
- [ ] Test different article formats (tutorial, news, analysis)

### Long Term (This Quarter)
- [ ] Build automated model selection system
- [ ] Implement quality-tiered generation
- [ ] Create comprehensive model evaluation dashboard
- [ ] Establish cost anomaly detection

## Key Takeaways

1. **Test in context**: Short benchmarks don't predict long-form performance
2. **Question assumptions**: "Cheaper" models often cost more in practice
3. **Use production data**: Real articles > synthetic benchmarks
4. **Monitor continuously**: Model behavior and pricing can change
5. **Automate testing**: Weekly comparisons catch issues early
6. **Document learnings**: Build institutional knowledge
7. **Be ready to adapt**: New models arrive frequently

## Resources

- [Model Comparison Tool](../scripts/compare_models.py)
- [A/B Testing Framework](../scripts/ab_test_models.py)
- [Complex Article Testing](../scripts/test_complex_article.py)
- [Testing Guide](MODEL-TESTING-GUIDE.md)
- [Current Test Results](../data/)
