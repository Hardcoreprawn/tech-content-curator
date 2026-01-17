"""Specialized prompt templates for different content types.

This module provides content-type-aware prompt generation that tailors
article structure and requirements based on the detected content type.
"""

import hashlib

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
- Open with the core claim or idea (topic-first, not meta-discussion about writing)
- Include 3-5 direct quotes or paraphrases ONLY if present in the provided sources
- Structure: Core claim → Why it matters → Broader implications
- Avoid repeated references to a "post" / "thread" / "source post"
- Focus on the SPECIFIC arguments, claims, or points made in the sources
- If discussing controversial content, include the actual statements (with citations)
- Example BAD: "This article discusses the challenges of obituary writing..."
- Example GOOD: "The claim is that [specific claim], supported by [quote]..."
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
- Back up claims with 5-7 citations using URLs from the EVIDENCE PACK
- Discuss real-world performance metrics or benchmarks
- Explain the reasoning behind your recommendations
""",
    "research": """
RESEARCH-SPECIFIC REQUIREMENTS:
- Start with clear research question or hypothesis
- Describe methodology in accessible terms
- Present findings with supporting data
- Discuss limitations and caveats
- Compare results to related work with 5-7 citations using URLs from the EVIDENCE PACK
- Explain implications for the field
- Suggest future research directions
- Balance technical depth with readability
""",
    "general": """
GENERAL ARTICLE REQUIREMENTS:
- Clear, engaging introduction with a hook
- 2-3 concrete examples or real-world use cases
- Mix of explanation and practical insights
- 3-5 citations using URLs from the EVIDENCE PACK
- Clear takeaways or actionable recommendations for readers
- Professional but accessible tone
- Logical flow from concepts to applications
""",
}


# Structure templates for each content type (dynamic pools)
STRUCTURE_POOLS = {
    "commentary": [
        """
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
        """
RECOMMENDED STRUCTURE FOR COMMENTARY (ALT):
Use ## for all section headings (not bold text):
## Opening Summary
## What the Source Claims
## Evidence & Context
## Critical Analysis
## Counterpoints
## Practical Implications
## Conclusion
""",
    ],
    "tutorial": [
        """
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
        """
RECOMMENDED STRUCTURE FOR TUTORIAL (ALT):
Use ## for all section headings (not bold text):
## Overview
## Requirements
## Quick Start
## Detailed Walkthrough
## Verification & Expected Output
## Troubleshooting
## Further Learning
""",
    ],
    "news": [
        """
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
        """
RECOMMENDED STRUCTURE FOR NEWS (ALT):
Use ## for all section headings (not bold text):
## What Happened
## Why It Matters
## Technical Summary
## Timeline
## Stakeholders & Impact
## What to Watch Next
""",
    ],
    "analysis": [
        """
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
        """
RECOMMENDED STRUCTURE FOR ANALYSIS (ALT):
Use ## for all section headings (not bold text):
## Thesis
## Context
## Alternatives Compared
## Evidence & Benchmarks
## Trade-offs
## Recommendations
## Conclusion
""",
    ],
    "research": [
        """
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
        """
RECOMMENDED STRUCTURE FOR RESEARCH (ALT):
Use ## for all section headings (not bold text):
## Research Question
## Background
## Methodology
## Results
## Interpretation
## Limitations
## Future Work
""",
    ],
    "general": [
        """
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
        """
RECOMMENDED STRUCTURE FOR GENERAL ARTICLE (ALT):
Use ## for all section headings (not bold text):
## Overview
## Context
## Key Concepts
## Practical Examples
## Risks & Trade-offs
## Actionable Takeaways
## Conclusion
""",
    ],
}


def _select_structure_template(item: EnrichedItem, content_type: str) -> str:
    pool = STRUCTURE_POOLS.get(content_type, STRUCTURE_POOLS["general"])
    seed = f"{item.original.url}-{content_type}".encode()
    idx = int(hashlib.sha256(seed).hexdigest(), 16) % len(pool)
    return pool[idx]


def _build_evidence_pack(item: EnrichedItem) -> str:
    sources = [str(item.original.url)]
    sources.extend(str(src) for src in item.related_sources)
    sources = [s for s in sources if s]

    lines = ["EVIDENCE PACK (use ONLY these sources for factual claims):"]
    if sources:
        lines.append(f"Primary source: {sources[0]}")
        if len(sources) > 1:
            lines.append("Related sources:")
            for src in sources[1:]:
                lines.append(f"- {src}")
    else:
        lines.append("Primary source: (none provided)")
    return "\n".join(lines)


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
Write a comprehensive tech blog article about the TOPIC and evidence below.
Treat the source as evidence, not as the subject. The article should stand alone.

SOURCE MATERIAL (for evidence only):
"{item.original.content}"
Author: @{item.original.author}
Primary URL: {item.original.url}

TOPICS: {", ".join(item.topics)}

RESEARCH CONTEXT:
{item.research_summary}

{_build_evidence_pack(item)}

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
- Do NOT frame the article as commentary on a post/thread/article
- Avoid phrases like "this post" / "the thread" / "the source post"
- If attribution is needed, include a single short attribution line at the end
- Include 3-7 citations as inline links to URLs in the EVIDENCE PACK
- NO title in output - content starts directly with introduction
- Avoid first-person claims of actions you did not perform (no "I inspected", "I benchmarked")

EVIDENCE RULES:
- Use ONLY sources in the EVIDENCE PACK for factual claims and quotes
- If evidence is limited, say so explicitly and narrow claims
- Do not invent quotes, metrics, timelines, or benchmarks
- Distinguish fact vs interpretation ("Fact:" / "Interpretation:") when needed

TERMINOLOGY GUIDELINES:
- Avoid anthropomorphizing AI (don't use "hallucination" - say "ungrounded output", "false generation", or "confabulation")
- Don't attribute human qualities to AI systems (understanding, thinking, knowing)
- Use precise technical terms: "generates", "predicts", "outputs" rather than "thinks", "believes", "understands"

SOURCE LINKING RULES:
- Link citations directly to source URLs (markdown links)
- Use the source domain to add context (e.g., "According to QuestDB...")
- If you can't support a claim with a source link, omit it

"""

    # Add structure guidance
    base_prompt += "STRUCTURE GUIDANCE FOR " + content_type.upper() + ":\n"
    base_prompt += _select_structure_template(item, content_type)

    return base_prompt
