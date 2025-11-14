"""Specialized prompt templates for different content types.

This module provides content-type-aware prompt generation that tailors
article structure and requirements based on the detected content type.
"""

from ..models import EnrichedItem
from ..utils.logging import get_logger

logger = get_logger(__name__)

# Keywords that indicate different content types
CONTENT_TYPE_DETECTION = {
    "commentary": [
        "wrote about",
        "published article",
        "obituary for",
        "essay on",
        "piece about",
        "analysis of",
        "thread on",
        "new post",
        "just published",
        "wrote",
        "obituary",
    ],
    "tutorial": [
        "how to",
        "guide",
        "tutorial",
        "step by step",
        "walkthrough",
        "getting started",
        "setup",
        "installation",
    ],
    "news": [
        "announced",
        "released",
        "launched",
        "breaking",
        "new version",
        "just released",
        "now available",
        "shipped",
    ],
    "analysis": [
        "deep dive",
        "analysis",
        "comparison",
        "review",
        "benchmark",
        "vs.",
        "versus",
        "trade-offs",
    ],
    "research": [
        "study",
        "research",
        "paper",
        "findings",
        "methodology",
        "academic",
        "scientific",
        "results",
    ],
}


def detect_content_type(item: EnrichedItem) -> str:
    """Detect content type from title, topics, and research summary.

    Args:
        item: The enriched item to analyze

    Returns:
        Content type string: 'commentary', 'tutorial', 'news', 'analysis', 'research', or 'general'
    """
    # Include research summary for better meta-content detection
    text = (
        item.original.title
        + " "
        + item.original.content[:200]
        + " "
        + " ".join(item.topics)
        + " "
        + item.research_summary[:200]
    ).lower()

    # Check commentary FIRST (most specific, should take precedence)
    for content_type, keywords in CONTENT_TYPE_DETECTION.items():
        if any(keyword in text for keyword in keywords):
            logger.debug(f"Content type detected: {content_type}")
            return content_type

    logger.debug("Content type: general (no specific keywords matched)")
    return "general"


# Specialized prompt enhancements by content type
PROMPT_ENHANCEMENTS = {
    "commentary": """
COMMENTARY-SPECIFIC REQUIREMENTS:
- Open with what the original source ACTUALLY says (not meta-discussion about writing)
- Include 3-5 direct quotes or specific paraphrases from the source material
- Structure: What they said → Why it matters → Broader implications
- Use "According to [Author]...", "[Author] wrote:", "[Author] argues that..." with actual content
- Avoid generic meta-discussion about journalism or writing practices
- Focus on the SPECIFIC arguments, claims, or points made in the source
- If discussing controversial content, include the actual controversial statements
- Example BAD: "This article discusses the challenges of obituary writing..."
- Example GOOD: "Begley wrote: '[actual quote]', highlighting Watson's [specific claim]..."
- Ground your analysis in concrete details from the source, not abstractions
- Use the research context to inform what specifics to highlight
""",
    "tutorial": """
TUTORIAL-SPECIFIC REQUIREMENTS:
- Start with clear prerequisites (what readers need to know before starting)
- Use numbered steps for the main process (1, 2, 3, etc.)
- Include 4-6 code examples with inline comments explaining key lines
- Add a "Common Pitfalls" or "Troubleshooting" section
- End with "Next Steps" or "Further Learning" recommendations
- Use second-person voice ("you will", "let's", "you can")
- Estimate time required to complete each section
- Provide expected output or results after each major step
""",
    "news": """
NEWS-SPECIFIC REQUIREMENTS:
- Lead with the most important information (inverted pyramid style)
- Clearly answer: What happened? When? Why does it matter?
- Include quotes or official statements if available
- Add context: How does this compare to previous versions or competitors?
- Keep timeline clear with specific dates
- End with "What This Means For [Developers/Users/Industry]" section
- Maintain neutral, fact-focused tone
- Link to official announcements or release notes when relevant
""",
    "analysis": """
ANALYSIS-SPECIFIC REQUIREMENTS:
- Start with a clear thesis statement: What's your main argument?
- Compare/contrast at least 2-3 alternatives or approaches
- Use data tables or bullet-point comparisons where appropriate
- Include "Trade-offs" section discussing pros and cons of each option
- Provide "When to Use" recommendations with specific scenarios
- Back up claims with 5-7 citations to credible sources
- Discuss real-world performance metrics or benchmarks
- Explain the reasoning behind your recommendations
""",
    "research": """
RESEARCH-SPECIFIC REQUIREMENTS:
- Start with clear research question or hypothesis
- Describe methodology in accessible terms
- Present findings with supporting data
- Discuss limitations and caveats
- Compare results to related work with 5-7 citations
- Explain implications for the field
- Suggest future research directions
- Balance technical depth with readability
""",
    "general": """
GENERAL ARTICLE REQUIREMENTS:
- Clear, engaging introduction with a hook
- 2-3 concrete examples or real-world use cases
- Mix of explanation and practical insights
- 3-5 academic or authoritative citations
- Clear takeaways or actionable recommendations for readers
- Professional but accessible tone
- Logical flow from concepts to applications
""",
}


# Structure templates for each content type
STRUCTURE_TEMPLATES = {
    "commentary": """
RECOMMENDED STRUCTURE FOR COMMENTARY:
Use ## for all section headings (not bold text):
## Introduction
## Main Arguments
## Key Points
## Analysis
## Context & Background
## Implications
## Conclusion
""",
    "tutorial": """
RECOMMENDED STRUCTURE FOR TUTORIAL:
Use ## for all section headings (not bold text):
## Introduction
## Prerequisites
## Setup/Installation
## Step-by-step Instructions
## Common Issues & Solutions
## Next Steps
## Additional Resources
""",
    "news": """
RECOMMENDED STRUCTURE FOR NEWS:
Use ## for all section headings (not bold text):
## Lead/Headline Info
## Impact & Significance
## Technical Details
## Background Context
## Availability & Timeline
## What This Means
## Related News
""",
    "analysis": """
RECOMMENDED STRUCTURE FOR ANALYSIS:
Use ## for all section headings (not bold text):
## Introduction
## Background & Context
## Detailed Comparison
## Performance Metrics
## Trade-offs
## Decision Matrix
## Conclusion
""",
    "research": """
RECOMMENDED STRUCTURE FOR RESEARCH:
Use ## for all section headings (not bold text):
## Introduction & Background
## Methods/Approach
## Key Findings
## Technical Details
## Implications
## Limitations
## Conclusion & Future Work
""",
    "general": """
RECOMMENDED STRUCTURE FOR GENERAL ARTICLE:
Use ## for all section headings (not bold text):
## Introduction
## Background
## Main Content
## Examples/Applications
## Best Practices
## Implications
## Conclusion
""",
}


def build_enhanced_prompt(item: EnrichedItem, content_type: str) -> str:
    """Build specialized prompt based on detected content type.

    Args:
        item: The enriched item to generate content for
        content_type: The type of content (tutorial, news, analysis, research, general)

    Returns:
        Complete prompt string for the LLM
    """
    logger.debug(f"Building enhanced prompt for {content_type} content")
    base_prompt = f"""
Write a comprehensive tech blog article based on this social media post and research.

ORIGINAL POST:
"{item.original.content}"
Source: {item.original.source} by @{item.original.author}
URL: {item.original.url}

TOPICS: {", ".join(item.topics)}

RESEARCH CONTEXT:
{item.research_summary}

CONTENT TYPE: {content_type.upper()}

"""

    # Add type-specific requirements
    base_prompt += PROMPT_ENHANCEMENTS.get(content_type, PROMPT_ENHANCEMENTS["general"])

    # Add universal requirements
    base_prompt += """

UNIVERSAL REQUIREMENTS:
- 1200-1600 words (1400-1600 for analysis/research, 1000-1400 for news/tutorial)
- Professional, engaging tone
- Use markdown formatting (## headings, **bold**, `code`, etc.)
- Include "Key Takeaways" bullet list (3-5 points) after introduction
- Explain acronyms and technical terms on first use
- Add background callouts for optional context using this format:
  > Background: one-sentence explanation
- Credit original source appropriately
- Include 3-7 citations naturally integrated (Author et al., Year format)
- NO title in output - content starts directly with introduction
- When referencing academic work, use format: "Author et al. (Year)" or "Author (Year)"

TERMINOLOGY GUIDELINES:
- Avoid anthropomorphizing AI (don't use "hallucination" - say "ungrounded output", "false generation", or "confabulation")
- Don't attribute human qualities to AI systems (understanding, thinking, knowing)
- Use precise technical terms: "generates", "predicts", "outputs" rather than "thinks", "believes", "understands"

ACADEMIC CITATION QUALITY RULES:
- Only cite research you are confident about (don't invent citations)
- For recent developments, estimate years based on recency context
- Integrate citations naturally into sentences, not as footnotes
- Use citations to support specific claims, not just for length
- Examples of good integration:
  * "Research by Smith et al. (2023) shows that..."
  * "According to Jones (2022), the approach involves..."
  * "The methodology, as described in Brown et al. (2021), requires..."

"""

    # Add structure guidance
    base_prompt += "STRUCTURE GUIDANCE FOR " + content_type.upper() + ":\n"
    base_prompt += STRUCTURE_TEMPLATES.get(content_type, STRUCTURE_TEMPLATES["general"])

    return base_prompt
