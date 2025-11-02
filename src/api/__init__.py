"""API client wrappers package.

This package provides centralized API client management for external services,
primarily AI/LLM providers.

Features:
- Centralized OpenAI client configuration
- Retry logic and error handling
- Rate limiting and cost tracking
- Request/response logging
- Circuit breaker patterns

Components:
- openai_client: OpenAI API wrapper
- anthropic_client: Claude API wrapper (future)

Usage:
    from src.api import get_openai_client, call_with_retry

    client = get_openai_client()
    response = await call_with_retry(
        client.chat.completions.create,
        model="gpt-4o-mini",
        messages=[...]
    )

Design Principles:
- Fail gracefully with retries
- Track costs per request
- Respect rate limits
- Log for debugging
- Timeout protection

Retry Strategy:
- Exponential backoff (1s, 2s, 4s, 8s)
- Retry on: RateLimitError, APITimeoutError, APIConnectionError
- Max 4 attempts
- Log each retry attempt

Cost Tracking:
- Track tokens per request
- Accumulate costs per run
- Report costs per model
- Alert on budget thresholds
"""

# API clients will be implemented in Phase 3
# from .openai_client import (
#     get_openai_client,
#     call_with_retry,
#     estimate_cost
# )

__all__ = []
