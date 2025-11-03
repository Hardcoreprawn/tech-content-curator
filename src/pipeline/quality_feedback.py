"""Quality feedback system for article improvement.

This module provides feedback mechanisms to improve article generation
based on quality analysis results.
"""

from ..config import QUALITY_THRESHOLDS


def generate_quality_feedback(
    quality_metrics: dict,
    difficulty_level: str,
    content_type: str,
) -> str:
    """Generate actionable feedback to improve article quality.

    Args:
        quality_metrics: Quality analysis results from analyze_article_quality
        difficulty_level: Target difficulty level
        content_type: Type of content (tutorial, news, etc.)

    Returns:
        Formatted feedback string to append to generation prompt
    """
    feedback_parts = []

    # Get thresholds for this difficulty level
    thresholds = QUALITY_THRESHOLDS.get(
        difficulty_level, QUALITY_THRESHOLDS["intermediate"]
    )

    # Readability feedback
    readability_score = quality_metrics.get("readability_score", 0)
    grade_level = quality_metrics.get("grade_level", 0)

    if not quality_metrics.get("matches_target", True):
        feedback_parts.append("\n## Content Readability Guidelines")

        if readability_score < thresholds["min_flesch_ease"]:
            feedback_parts.append(
                f"- Make the text MORE READABLE (current: {readability_score:.1f}, "
                f"target: {thresholds['min_flesch_ease']} or higher)"
            )
            feedback_parts.append("  * Use shorter sentences (aim for 15-20 words)")
            feedback_parts.append("  * Choose simpler words where possible")
            feedback_parts.append("  * Break complex ideas into multiple sentences")

        if grade_level > thresholds["max_grade_level"]:
            feedback_parts.append(
                f"- Lower the GRADE LEVEL (current: {grade_level:.1f}, "
                f"target: ≤{thresholds['max_grade_level']})"
            )
            feedback_parts.append("  * Simplify technical jargon")
            feedback_parts.append("  * Use concrete examples")
            feedback_parts.append("  * Explain concepts in plain language first")

    # Content-type specific feedback
    if content_type == "tutorial":
        feedback_parts.append("\n## Tutorial Requirements")
        feedback_parts.append("- Include step-by-step instructions")
        feedback_parts.append("- Provide working code examples")
        feedback_parts.append("- Add expected outputs or results")
        feedback_parts.append("- Include common pitfalls and solutions")

    elif content_type == "research":
        feedback_parts.append("\n## Research Article Requirements")
        feedback_parts.append("- Cite all sources properly")
        feedback_parts.append("- Present methodology clearly")
        feedback_parts.append("- Include data or evidence")
        feedback_parts.append("- Discuss implications and limitations")

    # Recommendations from readability analysis
    recommendations = quality_metrics.get("recommendations", [])
    if recommendations:
        feedback_parts.append("\n## Specific Improvements Needed")
        for rec in recommendations:
            feedback_parts.append(f"- {rec}")

    if not feedback_parts:
        return ""

    return "\n".join(feedback_parts)


def build_improvement_prompt(
    original_content: str,
    quality_metrics: dict,
    difficulty_level: str,
    content_type: str,
) -> str:
    """Build a prompt to regenerate content with quality improvements.

    Args:
        original_content: The original article content
        quality_metrics: Quality analysis results
        difficulty_level: Target difficulty level
        content_type: Type of content

    Returns:
        Prompt for content regeneration
    """
    feedback = generate_quality_feedback(
        quality_metrics, difficulty_level, content_type
    )

    prompt = f"""Improve the following article to meet quality standards.

ORIGINAL ARTICLE:
{original_content}

QUALITY ISSUES IDENTIFIED:
{quality_metrics.get("match_explanation", "Quality below threshold")}

IMPROVEMENT GUIDELINES:
{feedback}

Please rewrite the article addressing all the issues above while:
1. Maintaining the core message and key points
2. Keeping all technical accuracy
3. Preserving any code examples (but improve explanations)
4. Following the readability guidelines for {difficulty_level} level

Return ONLY the improved article in markdown format, without any meta-commentary.
"""

    return prompt


def should_regenerate_article(
    quality_metrics: dict,
    auto_improve: bool = False,
) -> bool:
    """Determine if an article should be regenerated for quality.

    Args:
        quality_metrics: Quality analysis results
        auto_improve: Whether to automatically regenerate low-quality articles

    Returns:
        True if article should be regenerated
    """
    if not auto_improve:
        return False

    # Only regenerate if significantly below threshold
    passed = quality_metrics.get("passed_threshold", True)
    readability_score = quality_metrics.get("readability_score", 100)

    # Regenerate if failed and score is very low (< 30 = very hard to read)
    return not passed and readability_score < 30


def get_quality_prompt_enhancements(
    difficulty_level: str,
    content_type: str,
) -> str:
    """Get prompt enhancements to preemptively guide quality.

    This should be included in the initial generation prompt to help
    produce higher quality content from the start.

    Args:
        difficulty_level: Target difficulty level
        content_type: Type of content

    Returns:
        Prompt enhancement text
    """
    thresholds = QUALITY_THRESHOLDS.get(
        difficulty_level, QUALITY_THRESHOLDS["intermediate"]
    )

    enhancements = [
        "\n## Writing Quality Guidelines",
        f"Target audience: {difficulty_level.title()} level",
        f"Readability target: Flesch Reading Ease of {thresholds['min_flesch_ease']} or higher",
        f"Grade level target: {thresholds['max_grade_level']} or below",
        "",
        "Writing style:",
        "- Use clear, concise sentences (15-20 words average)",
        "- Choose simple words over complex ones",
        "- Break down complex concepts into digestible parts",
        "- Use active voice predominantly",
        "- Include concrete examples",
    ]

    if difficulty_level == "beginner":
        enhancements.extend(
            [
                "- Explain all technical terms",
                "- Assume no prior knowledge",
                "- Use analogies to familiar concepts",
            ]
        )
    elif difficulty_level == "advanced":
        enhancements.extend(
            [
                "- Technical precision is important",
                "- You can use domain-specific terminology",
                "- Focus on depth and nuance",
            ]
        )

    return "\n".join(enhancements)
