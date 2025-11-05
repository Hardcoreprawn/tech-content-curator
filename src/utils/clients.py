"""Resource management utilities for external clients (OpenAI, HTTP, etc).

Provides context managers for proper cleanup of long-lived client connections.
This ensures resources are released even if errors occur during operations.

Key features:
- OpenAI client context manager with configurable timeout and retries
- HTTP client context manager with redirect handling
- Automatic cleanup via context manager protocol
- Integration with pipeline configuration
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING

import httpx
from openai import OpenAI

from .logging import get_logger

if TYPE_CHECKING:
    from ..config import PipelineConfig

logger = get_logger(__name__)


@contextmanager
def get_openai_client(config: PipelineConfig):
    """Context manager for OpenAI client lifecycle management.

    Ensures the client is properly closed after use, preventing resource leaks
    when processing large batches of items.

    Usage:
        with get_openai_client(config) as client:
            response = client.chat.completions.create(...)

    Args:
        config: Pipeline configuration with API key and timeouts

    Yields:
        OpenAI client ready for API calls

    Raises:
        ValueError: If OpenAI API key is not configured
        openai.AuthenticationError: If API key is invalid
    """
    if not config.openai_api_key:
        msg = "OpenAI API key not configured. Set OPENAI_API_KEY environment variable."
        logger.error(msg)
        raise ValueError(msg)

    client = None
    try:
        logger.debug(
            f"Creating OpenAI client with timeout={config.timeouts.openai_api_timeout}s"
        )
        client = OpenAI(
            api_key=config.openai_api_key,
            timeout=config.timeouts.openai_api_timeout,
            max_retries=config.retries.max_attempts,
        )
        logger.debug("OpenAI client created successfully")
        yield client

    except Exception as e:
        logger.error(f"Error during OpenAI client operation: {e}", exc_info=True)
        raise

    finally:
        if client is not None:
            try:
                client.close()
                logger.debug("OpenAI client closed successfully")
            except Exception as e:
                logger.warning(f"Error closing OpenAI client: {e}")


@contextmanager
def get_http_client(timeout: int | float = 30, follow_redirects: bool = True):
    """Context manager for HTTP client lifecycle management.

    Ensures the HTTP client (httpx) is properly closed after use.

    Usage:
        with get_http_client(timeout=60) as client:
            response = client.get("https://api.example.com/data")

    Args:
        timeout: Request timeout in seconds
        follow_redirects: Whether to automatically follow HTTP redirects

    Yields:
        httpx.Client ready for HTTP requests

    Note:
        httpx.Client manages connection pooling, so proper cleanup ensures
        pooled connections are returned and file handles are closed.
    """
    client = None
    try:
        logger.debug(f"Creating HTTP client with timeout={timeout}s")
        client = httpx.Client(follow_redirects=follow_redirects, timeout=timeout)
        logger.debug("HTTP client created successfully")
        yield client

    except Exception as e:
        logger.error(f"Error during HTTP client operation: {e}", exc_info=True)
        raise

    finally:
        if client is not None:
            try:
                client.close()
                logger.debug("HTTP client closed successfully")
            except Exception as e:
                logger.warning(f"Error closing HTTP client: {e}")
