"""Compatibility fix for python-frontmatter on Python 3.14+.

The python-frontmatter library uses deprecated codecs.open() which triggers
warnings on Python 3.14. This module monkey-patches it to use open() instead.

Import this module early (before frontmatter) to apply the fix.
"""

# Monkey-patch frontmatter to use open() instead of codecs.open()
import frontmatter

# Replace the codecs.open usage in frontmatter's load function
original_load = frontmatter.load


def patched_load(fd, encoding="utf-8", **defaults):
    """Load frontmatter using open() instead of codecs.open()."""
    if isinstance(fd, str):
        # If it's a file path, use regular open()
        with open(fd, encoding=encoding) as f:
            return frontmatter.loads(f.read(), **defaults)
    else:
        # If it's already a file object, use original function
        return original_load(fd, encoding=encoding, **defaults)


# Apply the patch
frontmatter.load = patched_load
