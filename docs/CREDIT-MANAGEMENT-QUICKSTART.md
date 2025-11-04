# Quick Start: Credit Management Integration

## For Testing

Run this to see the error tracking in action:

```python
from src.api_credit_manager import get_credit_manager
from src.graceful_shutdown import check_for_quota_error, handle_credits_exhausted

# Simulate a quota error
try:
    # This would be an actual API call that fails
    raise Exception("Error 429: You exceeded your current quota, please check your plan and billing details")
except Exception as e:
    if check_for_quota_error(e):
        handle_credits_exhausted(str(e))
    # Output: Prints clear message and raises CreditsExhaustedError
```

## For Production Integration

In `src/pipeline/orchestrator.py`, wrap API calls:

```python
from src.graceful_shutdown import check_for_quota_error, handle_credits_exhausted

def generate_single_article(...):
    """Generate article with credit awareness."""
    try:
        content, tokens_in, tokens_out = generator.generate_content(item)
        # ... continue with generation ...
    except Exception as e:
        # Check if credits are exhausted
        if check_for_quota_error(e):
            handle_credits_exhausted(str(e))
        
        # Other errors continue as normal
        logger.error(f"Generation failed: {e}")
        return None
```

## Error History

View accumulated errors:

```python
from src.api_credit_manager import get_credit_manager

manager = get_credit_manager()
print(manager.get_error_summary())
# Shows: total errors, recent errors (24h), error types, current mode

manager.print_status()
# Pretty-prints status to console
```

## What the User Sees

When credits run out:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠ API CREDITS EXHAUSTED
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

What happened:
  • OpenAI API returned a quota exceeded error
  • Your account has run out of available credits
  • Article generation pipeline has stopped

Next steps:
  1. Log into your OpenAI account: https://platform.openai.com/account/billing
  2. Add more credits or set a higher usage limit
  3. Verify your API key is still valid
  4. Restart the pipeline once credits are available

API Error: Error 429: You exceeded your current quota...
```

## Design Philosophy

✅ **Stop Don't Degrade** - No fallback templates, no low-quality content  
✅ **Clear Messages** - User knows exactly what happened  
✅ **Track Everything** - Error history on disk for analysis  
✅ **Fast Fail** - Don't waste time retrying, stop immediately  
✅ **Actionable** - Tell user exactly how to fix it  

## Files

- `src/api_credit_manager.py` - Error tracking and quota detection (445 lines)
- `src/graceful_shutdown.py` - Graceful shutdown handler (70 lines)
- `docs/API-CREDIT-MANAGEMENT.md` - Full documentation (400+ lines)

## Key Functions

```python
# Detect quota error
from src.graceful_shutdown import check_for_quota_error
is_quota = check_for_quota_error(exception)

# Shutdown gracefully
from src.graceful_shutdown import handle_credits_exhausted
handle_credits_exhausted(error_message)

# Track errors
from src.api_credit_manager import handle_api_error
error_type, should_retry = handle_api_error(exception, context="generation")

# Check status
from src.api_credit_manager import get_credit_manager
manager = get_credit_manager()
manager.print_status()
```

That's it! When credits run out, the system detects it and stops with a clear message. No guessing, no low-quality fallbacks.
