"""Tag normalization and canonicalization system.

This module ensures consistent tagging by:
1. Mapping variations to canonical tags (e.g., "AI" -> "artificial intelligence")
2. Limiting tags to a curated taxonomy
3. Providing fuzzy matching for close variants
4. Enforcing max 5 tags per article

Design Principles:
- Prefer specificity over generality (e.g., "rust" over "programming")
- Use lowercase with hyphens (e.g., "machine-learning")
- Avoid redundancy (don't include both "AI" and "artificial intelligence")
- Balance SEO value with user utility
"""

from __future__ import annotations

from difflib import get_close_matches

from ..utils.logging import get_logger

logger = get_logger(__name__)


# Canonical tag taxonomy (50-100 core tags)
CANONICAL_TAGS = {
    # Programming Languages
    "python",
    "javascript",
    "typescript",
    "rust",
    "go",
    "java",
    "c",
    "c++",
    "ruby",
    "php",
    # Web Development
    "web-development",
    "frontend",
    "backend",
    "full-stack",
    "html",
    "css",
    "react",
    "vue",
    "angular",
    # Infrastructure & DevOps
    "devops",
    "kubernetes",
    "docker",
    "ci-cd",
    "cloud-computing",
    "aws",
    "azure",
    "gcp",
    "infrastructure",
    "monitoring",
    # Data & AI
    "artificial-intelligence",
    "machine-learning",
    "data-science",
    "deep-learning",
    "neural-networks",
    "nlp",
    "computer-vision",
    "data-engineering",
    "big-data",
    # Security
    "cybersecurity",
    "security",
    "privacy",
    "encryption",
    "authentication",
    "vulnerabilities",
    # Databases
    "databases",
    "sql",
    "nosql",
    "postgresql",
    "mongodb",
    "redis",
    # Operating Systems
    "linux",
    "windows",
    "macos",
    "unix",
    "bsd",
    # Development Practices
    "software-engineering",
    "testing",
    "debugging",
    "performance",
    "architecture",
    "design-patterns",
    "code-quality",
    "refactoring",
    # Tools & Technologies
    "git",
    "github",
    "vscode",
    "vim",
    "containers",
    "microservices",
    "api",
    "graphql",
    "rest",
    # Mobile
    "mobile-development",
    "ios",
    "android",
    "react-native",
    "flutter",
    # Emerging Tech
    "blockchain",
    "web3",
    "iot",
    "edge-computing",
    "quantum-computing",
    # Self-Hosting & Open Source
    "self-hosting",
    "open-source",
    "foss",
    "homelab",
    # Other
    "networking",
    "system-administration",
    "automation",
    "productivity",
    "career",
    "tutorial",
    "news",
}


# Tag mapping: variations -> canonical tag
TAG_MAPPINGS = {
    # AI/ML variations
    "ai": "artificial-intelligence",
    "a.i.": "artificial-intelligence",
    "artificial intelligence": "artificial-intelligence",
    "ai adoption": "artificial-intelligence",
    "ai features": "artificial-intelligence",
    "ai workflows": "artificial-intelligence",
    "ai infrastructure": "artificial-intelligence",
    "genai": "artificial-intelligence",
    "generative ai": "artificial-intelligence",
    "ml": "machine-learning",
    "m.l.": "machine-learning",
    "machine learning": "machine-learning",
    "machine learning models": "machine-learning",
    "deep learning": "deep-learning",
    "neural networks": "neural-networks",
    "neural network": "neural-networks",
    "nlp": "nlp",
    "natural language processing": "nlp",
    "computer vision": "computer-vision",
    "data science": "data-science",
    # Programming languages
    "python programming": "python",
    "python development": "python",
    "javascript programming": "javascript",
    "js": "javascript",
    "typescript": "typescript",
    "ts": "typescript",
    "rust programming": "rust",
    "rust language": "rust",
    "golang": "go",
    "go language": "go",
    "java programming": "java",
    "c programming": "c",
    "c++": "c++",
    "cpp": "c++",
    # Web development
    "web dev": "web-development",
    "web development": "web-development",
    "frontend development": "frontend",
    "front-end": "frontend",
    "backend development": "backend",
    "back-end": "backend",
    "fullstack": "full-stack",
    "full stack": "full-stack",
    # DevOps/Infrastructure
    "dev ops": "devops",
    "kubernetes": "kubernetes",
    "k8s": "kubernetes",
    "docker containers": "docker",
    "containerization": "containers",
    "ci/cd": "ci-cd",
    "continuous integration": "ci-cd",
    "cloud": "cloud-computing",
    "cloud services": "cloud-computing",
    "amazon web services": "aws",
    "google cloud": "gcp",
    "google cloud platform": "gcp",
    # Security
    "cyber security": "cybersecurity",
    "information security": "security",
    "security practices": "security",
    "privacy protection": "privacy",
    "data privacy": "privacy",
    # Databases
    "database": "databases",
    "database management": "databases",
    "relational databases": "sql",
    "postgres": "postgresql",
    "mongo": "mongodb",
    # Operating systems
    "gnu/linux": "linux",
    "unix": "unix",
    "bsd": "bsd",
    "freebsd": "bsd",
    "windows os": "windows",
    "macos": "macos",
    "mac os": "macos",
    # Development practices
    "software development": "software-engineering",
    "software engineering": "software-engineering",
    "unit testing": "testing",
    "test-driven development": "testing",
    "debugging": "debugging",
    "performance optimization": "performance",
    "system architecture": "architecture",
    "design patterns": "design-patterns",
    "code quality": "code-quality",
    # Tools
    "version control": "git",
    "source control": "git",
    "visual studio code": "vscode",
    "vs code": "vscode",
    "microservices": "microservices",
    "microservice architecture": "microservices",
    "apis": "api",
    "rest api": "rest",
    "restful": "rest",
    "graphql api": "graphql",
    # Mobile
    "mobile dev": "mobile-development",
    "mobile development": "mobile-development",
    "ios development": "ios",
    "android development": "android",
    # Self-hosting
    "self-hosted": "self-hosting",
    "self hosted": "self-hosting",
    "self hosting": "self-hosting",
    "home lab": "homelab",
    "home server": "homelab",
    "open source software": "open-source",
    "oss": "open-source",
    "foss": "foss",
    "free software": "foss",
    # Other
    "networking": "networking",
    "network": "networking",
    "sysadmin": "system-administration",
    "system admin": "system-administration",
    "automation": "automation",
    "workflow automation": "automation",
    "productivity tools": "productivity",
    "career development": "career",
    "tutorials": "tutorial",
    "how-to": "tutorial",
    "tech news": "news",
}


def normalize_tag(tag: str | None) -> str | None:
    """Normalize a single tag to its canonical form.

    Args:
        tag: Raw tag string from AI extraction

    Returns:
        Canonical tag string, or None if tag should be discarded
    """
    if not tag or not isinstance(tag, str):
        return None

    # Clean up
    tag_clean = tag.lower().strip()
    tag_clean = tag_clean.replace("_", "-")

    # Remove leading articles/prepositions
    for prefix in ["the ", "a ", "an ", "in ", "on ", "at "]:
        if tag_clean.startswith(prefix):
            tag_clean = tag_clean[len(prefix) :]

    # Direct mapping
    if tag_clean in TAG_MAPPINGS:
        canonical = TAG_MAPPINGS[tag_clean]
        logger.debug(f"Mapped '{tag}' -> '{canonical}'")
        return canonical

    # Already canonical
    if tag_clean in CANONICAL_TAGS:
        logger.debug(f"Tag '{tag}' is already canonical")
        return tag_clean

    # Fuzzy match to canonical tags (80% similarity threshold)
    matches = get_close_matches(tag_clean, CANONICAL_TAGS, n=1, cutoff=0.80)
    if matches:
        canonical = matches[0]
        logger.debug(f"Fuzzy matched '{tag}' -> '{canonical}'")
        return canonical

    # No match - discard tag
    logger.debug(f"Tag '{tag}' not recognized, discarding")
    return None


def normalize_tags(tags: list[str] | None, max_tags: int = 5) -> list[str]:
    """Normalize a list of tags and limit to max_tags.

    Args:
        tags: Raw tag list from AI extraction
        max_tags: Maximum number of tags to return (default: 5)

    Returns:
        List of normalized canonical tags (deduplicated, max 5)
    """
    if not tags:
        return []

    normalized = []
    seen = set()

    for tag in tags:
        canonical = normalize_tag(tag)
        if canonical and canonical not in seen:
            normalized.append(canonical)
            seen.add(canonical)

            # Stop once we hit max_tags
            if len(normalized) >= max_tags:
                break

    if len(normalized) < len(tags):
        logger.info(f"Normalized {len(tags)} tags -> {len(normalized)} canonical tags")

    return normalized


def get_canonical_tags() -> set[str]:
    """Get the full set of canonical tags.

    Returns:
        Set of all valid canonical tag strings
    """
    return CANONICAL_TAGS.copy()


def suggest_canonical_tag(tag: str) -> list[str]:
    """Get suggestions for canonical tags similar to the input.

    Useful for debugging or suggesting tags to users.

    Args:
        tag: Tag string to find matches for

    Returns:
        List of up to 5 similar canonical tags
    """
    tag_clean = tag.lower().strip().replace("_", "-")
    matches = get_close_matches(tag_clean, CANONICAL_TAGS, n=5, cutoff=0.60)
    return matches
