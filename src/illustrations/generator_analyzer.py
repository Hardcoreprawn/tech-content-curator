"""Generator awareness module for preventing duplicate visual content.

Identifies which generators already provide visual content and prevents
redundant illustration generation.
"""

from ..utils.logging import get_logger

logger = get_logger(__name__)


import re

VISUAL_AWARE_GENERATORS = {
    "Integrative List Generator": {
        "provides": [],
        "skip_illustration": False,
        "reason": "Text-only output, benefits from visual enhancements for concepts like network_topology and data_flow",
    },
    "General Article Generator": {
        "provides": [],
        "skip_illustration": False,
        "reason": "Text-only output, benefits from visual enhancements",
    },
    "Scientific Article Generator": {
        "provides": [],
        "skip_illustration": False,
        "reason": "Scientific content benefits from diagrams and visualizations",
    },
}


def has_existing_visuals(content: str) -> bool:
    """Detect if content already has visual elements.

    Checks for code blocks, ASCII art, images, and other visual indicators.

    Args:
        content: Article markdown content to analyze

    Returns:
        True if content already contains visual elements, False otherwise
    """
    logger.debug("Checking for existing visual elements")
    # Indicators of existing visual content
    indicators = [
        r"```",  # Code blocks
        r"    \+[-\+]",  # ASCII box drawing
        r"    \|",  # ASCII vertical lines
        r"!\[.*?\]",  # Markdown images
        r"<svg",  # Embedded SVG
        r"<img",  # HTML images
        r"mermaid",  # Mermaid diagram indicators
    ]

    for pattern in indicators:
        if re.search(pattern, content, re.MULTILINE):
            logger.debug(f"Found existing visual element matching pattern: {pattern}")
            return True

    return False


def generator_includes_visuals(generator_name: str) -> bool:
    """Check if a generator type already provides visual content.

    Args:
        generator_name: Name of the generator (should match BaseGenerator.name property)

    Returns:
        True if the generator already includes visuals, False otherwise
    """
    # Normalize generator name for lookup
    gen_config = VISUAL_AWARE_GENERATORS.get(generator_name)

    if gen_config:
        return gen_config["skip_illustration"]

    # Unknown generator - check content for existing visuals (fallback)
    return False


def should_add_illustrations(generator_name: str, content: str) -> bool:
    """Determine if illustrations should be added based on generator type and content.

    This is the main decision function for whether to proceed with illustration generation.
    It prevents duplicate visuals while ensuring all articles that need illustrations get them.

    Args:
        generator_name: Name of the generator that created the article
        content: The generated article content to analyze

    Returns:
        True if illustrations should be added, False otherwise
    """
    logger.debug(f"Evaluating illustration addition for generator: {generator_name}")
    # First, check if this generator type already provides visuals
    if generator_includes_visuals(generator_name):
        logger.info(
            f"Skipping illustrations: {generator_name} already provides visuals"
        )
        return False

    # Otherwise, illustrations would add value
    # NOTE: Temporarily disabled has_existing_visuals check to allow testing
    # of AI-generated illustrations alongside any existing visuals
    logger.info(f"Proceeding with illustration generation for {generator_name}")
    return True


def get_generator_config(generator_name: str) -> dict | None:
    """Get configuration for a specific generator.

    Args:
        generator_name: Name of the generator

    Returns:
        Generator configuration dict, or None if not found
    """
    return VISUAL_AWARE_GENERATORS.get(generator_name)
