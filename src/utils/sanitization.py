"""Input sanitization utilities for security.

Provides functions to sanitize external content before processing:
- Safe filename generation from slugs (prevents directory traversal)
- HTML content sanitization (prevents injection attacks)
- Text field escaping (prevents markup injection)
- Path validation (prevents symlink attacks)

Uses industry-standard libraries:
- bleach: HTML sanitization (used by Mozilla, Django, etc.)
- python-slugify: Unicode-aware slug generation
- pathlib: Path validation and traversal prevention
"""

from pathlib import Path
from typing import Any

import bleach
from markupsafe import escape
from slugify import slugify

from ..utils.logging import get_logger

logger = get_logger(__name__)

# Bleach configuration for safe HTML
ALLOWED_TAGS = {
    "p",
    "br",
    "strong",
    "em",
    "b",
    "i",
    "code",
    "pre",
    "a",
    "ul",
    "ol",
    "li",
    "blockquote",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "img",
}

ALLOWED_ATTRIBUTES = {
    "a": ["href", "title"],
    "img": ["src", "alt", "title"],
}


def safe_filename(slug: str, max_length: int = 100) -> str:
    """Generate a safe filename that prevents directory traversal attacks.

    Uses python-slugify to handle Unicode and special characters properly,
    then validates the result to ensure filesystem safety.
    Preserves file extensions (e.g., .md, .txt).

    Args:
        slug: Input string to convert to safe filename
        max_length: Maximum filename length (default 100)

    Returns:
        Safe filename string suitable for filesystem operations

    Raises:
        ValueError: If the slug is empty or becomes empty after sanitization
    """
    if not slug or not isinstance(slug, str):
        raise ValueError(
            f"Invalid slug: expected non-empty string, got {type(slug).__name__}"
        )

    # Strip whitespace first
    slug = slug.strip()
    if not slug:
        raise ValueError("Slug is empty or whitespace-only")

    logger.debug(f"Sanitizing filename from slug: {slug[:50]}...")

    # Extract and preserve file extension (e.g., .md, .txt)
    extension = ""
    if "." in slug and not slug.startswith("."):
        # Get the last dot for extension
        parts = slug.rsplit(".", 1)
        if (
            len(parts) == 2 and parts[1] and len(parts[1]) <= 10
        ):  # reasonable extension length
            slug = parts[0]
            extension = f".{parts[1]}"

    # Use python-slugify for robust Unicode handling and character conversion
    safe = slugify(slug, max_length=max_length, word_boundary=True, separator="-")

    # Ensure result is not empty
    if not safe:
        raise ValueError(f"Slug becomes empty after sanitization: {slug}")

    # Additional safety checks
    # Reject if it starts with a dot (hidden files on Unix)
    if safe.startswith("."):
        safe = safe.lstrip(".")
        if not safe:
            raise ValueError(f"Slug is only dots: {slug}")

    # Reattach the extension
    safe = safe + extension

    logger.debug(f"Generated safe filename: {safe}")
    return safe


def sanitize_html(content: str, max_length: int | None = None) -> str:
    """Sanitize HTML content to prevent injection attacks.

    Uses bleach with a whitelist of safe tags and attributes.
    Removes any potentially dangerous HTML/JavaScript.

    Args:
        content: HTML content to sanitize
        max_length: Optional maximum content length in characters

    Returns:
        Safe HTML string with dangerous tags removed
    """
    if not isinstance(content, str):
        raise ValueError(f"Expected string, got {type(content).__name__}")

    logger.debug(f"Sanitizing HTML content ({len(content)} chars)...")

    # Use bleach to sanitize with whitelist approach
    safe_content: str = bleach.clean(
        content, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES, strip=True
    )

    # Apply length limit if specified
    if max_length and len(safe_content) > max_length:
        logger.debug(
            f"Truncating HTML content from {len(safe_content)} to {max_length} chars"
        )
        safe_content = safe_content[:max_length].strip()

    logger.debug(f"Sanitized HTML content to {len(safe_content)} chars")
    return safe_content


def sanitize_text(content: str, max_length: int | None = None) -> str:
    """Escape plain text to prevent markdown/markup injection.

    Converts HTML special characters to entities, useful for user-provided
    content that shouldn't contain any markup.

    Args:
        content: Plain text content to escape
        max_length: Optional maximum content length in characters

    Returns:
        Escaped text safe for markdown/HTML contexts
    """
    if not isinstance(content, str):
        raise ValueError(f"Expected string, got {type(content).__name__}")

    logger.debug(f"Escaping text content ({len(content)} chars)...")

    # Apply length limit if specified
    if max_length and len(content) > max_length:
        logger.debug(f"Truncating text from {len(content)} to {max_length} chars")
        content = content[:max_length].strip()

    # Use markupsafe to escape HTML entities
    safe_content = str(escape(content))

    logger.debug(f"Escaped text content to {len(safe_content)} chars")
    return safe_content


def validate_path(filepath: str | Path, base_dir: str | Path | None = None) -> Path:
    """Validate a file path to prevent directory traversal attacks.

    Ensures the path:
    - Is absolute and normalized
    - Doesn't contain .. or other traversal sequences
    - Stays within base_dir if provided (symlinks resolved)

    Args:
        filepath: Path to validate
        base_dir: Optional base directory to confine path within

    Returns:
        Validated absolute Path object

    Raises:
        ValueError: If path attempts directory traversal or escapes base_dir
    """
    try:
        # Convert to Path and resolve (follows symlinks, removes ..)
        path = Path(filepath).resolve()

        logger.debug(f"Validating path: {path}")

        # If base_dir specified, ensure path is within it
        if base_dir:
            base = Path(base_dir).resolve()
            try:
                # This raises ValueError if path is not relative to base
                path.relative_to(base)
                logger.debug(f"Path is within base directory: {base}")
            except ValueError as e:
                raise ValueError(f"Path {path} escapes base directory {base}") from e

        logger.debug(f"Path validation passed: {path}")
        return path

    except (TypeError, OSError) as e:
        raise ValueError(f"Invalid path: {e}") from e


def sanitize_metadata(
    metadata: dict[str, Any], max_length: int = 255
) -> dict[str, Any]:
    """Sanitize metadata dictionary (fields like author, title, etc.).

    Escapes all string values in metadata to prevent injection attacks.

    Args:
        metadata: Dictionary of metadata fields
        max_length: Maximum length for text values

    Returns:
        Dictionary with sanitized string values
    """
    logger.debug(f"Sanitizing metadata with {len(metadata)} fields")

    sanitized: dict[str, Any] = {}
    for key, value in metadata.items():
        if isinstance(value, str):
            sanitized[key] = sanitize_text(value, max_length=max_length)
        elif isinstance(value, dict):
            # Recursively sanitize nested dicts
            sanitized[key] = sanitize_metadata(value, max_length=max_length)
        elif isinstance(value, list):
            # Sanitize list items if they're strings
            sanitized[key] = [
                sanitize_text(item, max_length=max_length)
                if isinstance(item, str)
                else item
                for item in value
            ]
        else:
            # Pass through other types (int, float, bool, etc.)
            sanitized[key] = value

    logger.debug(f"Sanitized metadata: {len(sanitized)} fields")
    return sanitized
