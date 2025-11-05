"""Compatibility fix for python-frontmatter on Python 3.14+.

The python-frontmatter library uses deprecated codecs.open() which triggers
warnings on Python 3.14. This module monkey-patches it to use open() instead.

Import this module early (before frontmatter) to apply the fix.
"""

# Monkey-patch frontmatter to use open() instead of codecs.open()
import frontmatter

from ..utils.logging import get_logger

logger = get_logger(__name__)

# Replace the codecs.open usage in frontmatter's load function
original_load = frontmatter.load


def patched_load(fd, encoding="utf-8", **defaults):
    """Load frontmatter using open() instead of codecs.open()."""
    if isinstance(fd, str):
        # If it's a file path, use regular open()
        logger.debug(f"Loading frontmatter from file: {fd}")
        try:
            with open(fd, encoding=encoding) as f:
                result = frontmatter.loads(f.read(), **defaults)
            logger.debug(f"Successfully loaded frontmatter from {fd}")
            return result
        except Exception as e:
            logger.error(
                f"Error loading frontmatter from {fd}: {type(e).__name__} - {e}"
            )
            raise
    else:
        # If it's already a file object, use original function
        logger.debug("Loading frontmatter from file object using original function")
        return original_load(fd, encoding=encoding, **defaults)


# Apply the patch
frontmatter.load = patched_load
logger.info("Applied Python 3.14+ compatibility patch for python-frontmatter")
