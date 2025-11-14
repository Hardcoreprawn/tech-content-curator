# Automatic Model Capability Detection

## Overview

This system automatically detects, probes, and integrates new OpenAI models into the tech-content-curator pipeline without manual code changes.

## What Gets Automated

### ✅ Fully Automated
- **Model Discovery**: Detects new `gpt-*` models from OpenAI API
- **Parameter Probing**: Tests which parameters each model supports
- **Config Generation**: Creates ready-to-use `MODEL_CONFIGS` code
- **Fallback Suggestions**: Recommends appropriate fallback models
- **Cost Testing**: Evaluates performance and pricing
- **Config Updates**: Updates default model assignments

### ⚠️ Semi-Automated (Review Required)
- **MODEL_CONFIGS Integration**: Generated code must be reviewed and added to `openai_client.py`
- **Fallback Mappings**: Suggested mappings should be validated before use

## Architecture

```
┌─────────────────────┐
│ OpenAI API          │
│ (models.list())     │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ discover_models.py  │  ← Finds new models
│ --probe-new         │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ probe_model_        │  ← Tests parameters
│ capabilities.py     │     individually
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ generate_model_     │  ← Creates Python code
│ configs.py          │     for MODEL_CONFIGS
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ compare_models.py   │  ← Tests performance
│ ab_test_models.py   │     and costs
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ update_config_      │  ← Updates defaults
│ from_eval.py        │     in config.py
└──────────┬──────────┘
           │
           ▼
     GitHub PR with:
     • Evaluation results
     • Generated configs
     • Recommendations
```

## How It Handles New Models

### Scenario 1: New Variant (e.g., gpt-5-ultra)
**Status**: ✅ Fully automatic

1. Discovery finds "gpt-5-ultra"
2. Matches existing "gpt-5" prefix
3. Uses existing `MODEL_CONFIGS` entry
4. Tests performance and cost
5. Updates config if best performer

**Result**: Works immediately, no code changes needed

### Scenario 2: New Family (e.g., gpt-6-mini)
**Status**: ⚠️ Semi-automatic

1. Discovery finds "gpt-6-mini"
2. Probes parameter support:
   - Tests max_tokens, temperature, top_p, etc.
   - Detects unsupported parameters
   - Infers API parameter names
3. Generates MODEL_CONFIGS code:
   ```python
   {
       "prefix": "gpt-6",
       "param_map": {
           "max_tokens": "max_completion_tokens",
           "messages": "messages",
           ...
       },
       "unsupported": ["temperature", "top_p"],
   }
   ```
4. Suggests fallback: `"gpt-6-mini": "gpt-5.1"`
5. Tests performance
6. Creates PR with:
   - Generated config code
   - Integration instructions
   - Performance data

**Result**: Generates integration-ready code, human reviews and adds to `openai_client.py`

### Scenario 3: API Contract Change
**Status**: ✅ Automatic detection

If OpenAI changes parameter support (e.g., GPT-5 suddenly supports temperature):

1. Quarterly probe re-tests all parameters
2. Detects changes in support
3. Generates updated `MODEL_CONFIGS`
4. PR highlights differences
5. Human reviews and updates code

**Result**: Changes detected and surfaced for review

## Usage

### Manual Model Probing

```bash
# Probe a specific model
python scripts/probe_model_capabilities.py --model gpt-6-mini

# Probe all newly discovered models
python scripts/discover_models.py --probe-new

# Generate integration code
python scripts/generate_model_configs.py

# Generate code for specific model
python scripts/generate_model_configs.py --model gpt-6-mini
```

### Quarterly Evaluation (Automatic)

Runs on 15th of Jan/Apr/Jul/Oct:

1. Discovers new models
2. Probes capabilities
3. Generates configs
4. Tests performance
5. Creates PR with recommendations

### Manual Trigger

```bash
# In GitHub Actions UI:
Actions → Quarterly Model Evaluation → Run workflow
Options:
  - test_model: Optional specific model to test
  - skip_discovery: Skip discovery and re-evaluate current
```

## Parameter Probing Details

### Parameters Tested

```python
PARAMETERS_TO_TEST = {
    "max_tokens": 10,           # Token limit
    "temperature": 0.7,         # Sampling temperature
    "top_p": 0.9,              # Nucleus sampling
    "frequency_penalty": 0.0,   # Frequency penalty
    "presence_penalty": 0.0,    # Presence penalty
    "seed": 12345,             # Random seed
    "stop": ["END"],           # Stop sequences
    "logprobs": True,          # Log probabilities
    "top_logprobs": 1,         # Top log probs count
}
```

### Detection Strategy

For each parameter:

1. **Test standard name**: Try `max_tokens`
2. **Test alternatives**: Try `max_completion_tokens`
3. **Analyze errors**:
   - "unsupported" → Parameter not available
   - "unexpected" → Wrong parameter name
   - Success → Parameter supported

4. **Record results**:
   ```json
   {
     "param_name": "max_tokens",
     "supported": true,
     "actual_api_name": "max_completion_tokens",
     "tested_value": 10
   }
   ```

### Cost Impact

- ~10 minimal API calls per model (~$0.0001)
- Uses shortest possible prompt: "Hi"
- Requests only 10 tokens
- Total cost per model: < $0.001

## Integration Workflow

### When New Models Appear

**Quarterly evaluation creates PR with:**

```
🤖 Quarterly Model Evaluation - 2025-Q4
├── data/quarterly-eval-2025-Q4/
│   ├── models-discovered.json        ← New models found
│   ├── model-capabilities/           ← Probe results
│   │   └── capabilities_gpt-6-mini.json
│   ├── new-model-configs.py          ← Generated code
│   ├── comparison-results.json       ← Performance data
│   ├── ab-test-results.json          ← Cost analysis
│   └── recommendation.md             ← Summary + instructions
```

**PR Body includes:**
- Performance comparison tables
- Cost estimates
- Recommended configuration
- **→ Generated MODEL_CONFIGS code**
- **→ Integration instructions**

### Review Checklist

1. **Review capability probe results**
   - Check supported/unsupported parameters
   - Validate API parameter mappings
   - Verify fallback suggestions

2. **Test generated config**
   ```bash
   # Copy generated config to openai_client.py
   # Test with a simple call
   python scripts/compare_models.py --model gpt-6-mini --iterations 1
   ```

3. **Merge if successful**
   - Config updates applied automatically
   - New models integrated
   - Fallbacks configured

## Files and Scripts

| Script | Purpose | When to Use |
|--------|---------|-------------|
| `discover_models.py` | Find new models from OpenAI | Quarterly (auto) or manual |
| `probe_model_capabilities.py` | Test parameter support | After discovering new model family |
| `generate_model_configs.py` | Create integration code | After probing capabilities |
| `compare_models.py` | Test individual performance | Testing specific models |
| `ab_test_models.py` | Test configuration combos | Choosing best config |
| `update_config_from_eval.py` | Apply recommended config | After evaluation |

## Benefits

### Before (Manual Process)
1. GPT-6 released
2. ❌ System crashes: "Unknown model family"
3. Read OpenAI docs
4. Manually test parameters
5. Update `MODEL_CONFIGS`
6. Test manually
7. Update fallback mappings
8. Deploy
9. **Total time**: Hours to days

### After (Automated Process)
1. GPT-6 released
2. ✅ Quarterly eval detects it
3. ✅ Probes capabilities automatically
4. ✅ Generates integration code
5. ✅ Tests performance
6. 👤 Human reviews PR (5 minutes)
7. 👤 Merges if looks good
8. **Total time**: 5 minutes of human time

## Limitations

### What's Still Manual

1. **Final integration**: Generated code must be added to `openai_client.py`
2. **Edge cases**: Unusual parameter behaviors may need custom handling
3. **Cost decisions**: Human decides if new model is worth using

### Why Not Fully Automatic?

- **Safety**: Model parameters affect API costs and behavior
- **Validation**: Generated code should be reviewed before production use
- **Business logic**: Cost/performance tradeoffs require human judgment

## Future Enhancements

Potential improvements:

1. **Auto-PR to openai_client.py**: Automatically create PR with MODEL_CONFIGS changes
2. **Regression testing**: Test that new configs don't break existing functionality
3. **Cost alerts**: Flag models that would significantly increase costs
4. **A/B testing**: Automatically test new models in production with traffic splitting
5. **Provider expansion**: Support Claude, Gemini, etc. with similar probing

## Related Documentation

- [MODEL-EVALUATION-STRATEGY.md](./MODEL-EVALUATION-STRATEGY.md) - Overall strategy
- [QUICK-REFERENCE.md](./QUICK-REFERENCE.md) - Command reference
- [MODEL-TESTING-GUIDE.md](./MODEL-TESTING-GUIDE.md) - Manual testing guide
