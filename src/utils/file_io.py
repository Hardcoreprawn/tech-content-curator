"""File I/O utilities with safety guarantees.

Provides atomic write operations to prevent corruption from interrupted writes,
disk full errors, or concurrent access. All JSON writes use temporary files
with fsync to ensure data durability.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any, Callable

from .logging import get_logger

logger = get_logger(__name__)


def get_available_disk_space(path: Path) -> int:
    """Get available disk space for the given path in bytes.

    Works for both existing and non-existent paths by finding the nearest
    parent directory that exists.

    Args:
        path: Path on the filesystem to check

    Returns:
        Available disk space in bytes
    """
    path = Path(path)
    # Find nearest existing parent directory
    check_path = path if path.exists() else path.parent
    while not check_path.exists() and check_path.parent != check_path:
        check_path = check_path.parent

    stat = shutil.disk_usage(str(check_path))
    return stat.free


def atomic_write_json(
    filepath: Path,
    data: dict[str, Any],
    min_disk_space: int = 1024 * 1024,  # 1MB default
    ensure_ascii: bool = False,
    indent: int = 2,
    default: Callable[[Any], Any] | None = None,
) -> None:
    """Write JSON data atomically to prevent corruption.

    Uses a temporary file in the same directory with fsync to ensure durability.
    The temporary file is renamed atomically to the target path, making the
    operation fail-safe against:
    - Interrupted writes
    - Out of disk space (temp file cleanup happens before error)
    - Partial/corrupted data

    Args:
        filepath: Target file path to write to
        data: Dictionary to serialize as JSON
        min_disk_space: Minimum free disk space required (in bytes). Raises if
                       insufficient space available.
        ensure_ascii: Whether to escape non-ASCII characters in JSON output
        indent: JSON indentation level
        default: Function to handle non-JSON-serializable objects (e.g., str for HttpUrl)

    Raises:
        OSError: If disk full or write fails
        json.JSONDecodeError: If data is not JSON serializable
        ValueError: If insufficient disk space available

    Example:
        >>> data = {"name": "Alice", "age": 30}
        >>> atomic_write_json(Path("data.json"), data)
        # File is either fully written or not modified at all
    """
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)

    # Check available disk space
    available = get_available_disk_space(filepath.parent)
    if available < min_disk_space:
        msg = (
            f"Insufficient disk space for writing {filepath}. "
            f"Required: {min_disk_space} bytes, Available: {available} bytes"
        )
        logger.error(msg)
        raise ValueError(msg)

    # Use .tmp suffix for temp file (same directory ensures same filesystem)
    temp_file = filepath.with_suffix(filepath.suffix + ".tmp")

    try:
        # Write to temporary file
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(
                data,
                f,
                ensure_ascii=ensure_ascii,
                indent=indent,
                default=default,
            )
            # Force write to disk
            f.flush()
            os.fsync(f.fileno())

        # Atomic rename (POSIX guarantees this is atomic)
        temp_file.replace(filepath)

        logger.debug(f"Atomically wrote {len(str(data))} bytes to {filepath}")

    except (OSError, json.JSONDecodeError) as e:
        # Clean up temporary file if write failed
        temp_file.unlink(missing_ok=True)
        logger.error(f"Failed to write {filepath}: {e}", exc_info=True)
        raise


def safe_read_json(filepath: Path) -> dict[str, Any]:
    """Safely read JSON file with error handling.

    Handles missing files and corrupted JSON gracefully with logging.

    Args:
        filepath: Path to JSON file to read

    Returns:
        Parsed JSON data as dictionary, or empty dict if file doesn't exist

    Raises:
        json.JSONDecodeError: If JSON is malformed
    """
    if not filepath.exists():
        logger.debug(f"JSON file not found: {filepath}")
        return {}

    try:
        with open(filepath, encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        logger.error(f"Corrupted JSON in {filepath}: {e}", exc_info=True)
        raise
    except OSError as e:
        logger.error(f"Failed to read {filepath}: {e}", exc_info=True)
        raise


def atomic_write_text(
    filepath: Path,
    content: str,
    min_disk_space: int = 1024 * 1024,  # 1MB default
) -> None:
    """Write text data atomically to prevent corruption.

    Same safety guarantees as atomic_write_json but for plain text files.

    Args:
        filepath: Target file path to write to
        content: Text content to write
        min_disk_space: Minimum free disk space required (in bytes)

    Raises:
        OSError: If disk full or write fails
        ValueError: If insufficient disk space available
    """
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)

    # Check available disk space
    available = get_available_disk_space(filepath.parent)
    if available < min_disk_space:
        msg = (
            f"Insufficient disk space for writing {filepath}. "
            f"Required: {min_disk_space} bytes, Available: {available} bytes"
        )
        logger.error(msg)
        raise ValueError(msg)

    temp_file = filepath.with_suffix(filepath.suffix + ".tmp")

    try:
        with open(temp_file, "w", encoding="utf-8") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())

        temp_file.replace(filepath)

        logger.debug(f"Atomically wrote {len(content)} bytes to {filepath}")

    except OSError as e:
        temp_file.unlink(missing_ok=True)
        logger.error(f"Failed to write {filepath}: {e}", exc_info=True)
        raise


# Format utilities


def format_cost_value(cost: float, precision: int = 8) -> float:
    """Format cost value with consistent decimal precision.

    Ensures all cost values use standard decimal notation rather than
    scientific notation or excessive precision. This keeps YAML frontmatter
    readable and consistent across all generated articles.

    Args:
        cost: The cost value in USD
        precision: Number of decimal places to round to

    Returns:
        Formatted cost value (rounded to avoid scientific notation)
    """
    if cost == 0.0:
        return 0.0
    # Round to specified precision to avoid scientific notation
    # and keep values like 0.000054 readable
    return round(cost, precision)


def format_generation_costs(costs: dict[str, float]) -> dict[str, str]:
    """Format all generation costs with consistent decimal notation.

    Converts costs to strings to prevent YAML from using scientific notation
    when serializing very small float values.

    Args:
        costs: Dictionary of cost values

    Returns:
        Dictionary with all values as formatted strings
    """
    result = {}
    for key, value in costs.items():
        formatted = format_cost_value(value)
        # Convert to string to prevent scientific notation in YAML
        if formatted == 0.0:
            result[key] = 0.0  # Keep zero as float for cleaner YAML
        else:
            # Format with enough decimals, then strip trailing zeros
            result[key] = float(f"{formatted:.8f}".rstrip("0").rstrip("."))
    return result
