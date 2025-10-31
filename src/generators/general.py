"""General article generator for standard technical content."""

from rich.console import Console

from ..models import EnrichedItem
from .base import BaseGenerator

console = Console()


class GeneralArticleGenerator(BaseGenerator):
    """Standard article generator for most technical content."""

    @property
    def name(self) -> str:
        return "General Article Generator"

    @property
    def priority(self) -> int:
        return 0  # Lowest priority - this is the fallback

    def can_handle(self, item: EnrichedItem) -> bool:
        """Can handle any item - this is the fallback generator."""
        return True

    def generate_content(self, item: EnrichedItem) -> tuple[str, int, int]:
        """Generate a standard technical article.

        This creates a comprehensive blog article that:
        - Expands on the original social media post
        - Incorporates the research summary
        - Maintains a professional, informative tone
        - Includes proper markdown formatting
        - Is 1200-1600 words for depth

        Args:
            item: The enriched item with all context

        Returns:
            Tuple of (article content as markdown string, input tokens, output tokens)
        """
        if not self.client:
            raise ValueError("OpenAI client not initialized")

        prompt = f"""
    Write a comprehensive tech blog article based on this social media post and research.

    ORIGINAL POST:
    "{item.original.content}"
    Source: {item.original.source} by @{item.original.author}
    URL: {item.original.url}

    TOPICS: {", ".join(item.topics)}

    RESEARCH CONTEXT:
    {item.research_summary}

    ARTICLE REQUIREMENTS:
    - 1200-1600 words
    - Professional, informative tone
    - Use markdown formatting (## headings, **bold**, `code`, etc.)
    - Structure: Introduction, 2-3 main sections, conclusion
    - Include practical insights and takeaways
    - Include a short "Key Takeaways" bullet list (3–5 bullets) near the top after the introduction
    - Explain non-mainstream terms and acronyms the first time they appear; if optional background, add a brief blockquote callout using the format:
      > Background: one-sentence explanation
    - Credit the original source appropriately
    - Focus on value for tech professionals/developers

    ACADEMIC CITATION REQUIREMENT:
    - When you reference research, studies, or papers, include author names with publication years
    - Proper citation format: "Author (Year)" or "Author et al. (Year)"
    - Examples of good citations:
      * "Recent research by Lentink (2014) established foundational principles..."
      * "Jones et al. (2023) discovered that..."
      * "Studies like Brown et al. (2022) demonstrate..."
    - Include 3-5 academic citations naturally throughout the article
    - Only cite research you are confident about (don't invent citations)
    - Citations will be automatically linked to DOI/arXiv by the publication engine
    - If unsure of exact year, make reasonable estimate based on recency

    ARTICLE STRUCTURE:
    1. **Introduction**: Hook + context + what readers will learn (include 1 citation if relevant)
    2. **Main sections**: Deep dive into the key concepts (use ## headings, include 2-3 citations naturally)
    3. **Practical implications**: What this means for readers
    4. **Conclusion**: Key takeaways + call to action (1-2 citations if relevant)
    5. **Source attribution**: Credit original post and author

    Write engaging, substantive content that goes beyond the original post.
    Use the research context to add depth and technical accuracy.
    DO NOT include a title - the article content should start directly with the introduction.
    """

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",  # Better for long-form content
                messages=[{"role": "user", "content": prompt}],
                temperature=0.6,  # More creative for article writing
                max_tokens=2000,  # Allow for longer articles
            )

            content = response.choices[0].message.content
            if not content:
                raise ValueError("Empty response from OpenAI")

            # Extract actual token usage
            usage = response.usage
            input_tokens = usage.prompt_tokens if usage else 0
            output_tokens = usage.completion_tokens if usage else 0

            return content.strip(), input_tokens, output_tokens

        except Exception as e:
            console.print(f"[yellow]⚠[/yellow] Article generation failed: {e}")
            # Create basic fallback article
            fallback = f"""Based on a social media post discussing {", ".join(item.topics[:3])}.

## Overview

{item.research_summary[:500]}

## Key Points

The original discussion highlighted several important aspects:

{item.original.content[:300]}

## Conclusion

This topic deserves further exploration and discussion in the tech community.

---

*Based on a post by @{item.original.author} on {item.original.source}*
*Original source: {item.original.url}*
"""
            return fallback, 0, 0
