"""General article generator for standard technical content."""

from rich.console import Console

from ..models import EnrichedItem
from ..pipeline.quality_feedback import get_quality_prompt_enhancements
from .base import BaseGenerator
from .prompt_templates import build_enhanced_prompt, detect_content_type

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

        # Detect content type and build specialized prompt
        content_type = detect_content_type(item)
        console.print(f"  Content type detected: {content_type}")

        # Build base prompt
        prompt = build_enhanced_prompt(item, content_type)

        # Add quality enhancements to guide generation
        difficulty_level = item.difficulty_level or "intermediate"
        quality_guidance = get_quality_prompt_enhancements(
            difficulty_level, content_type
        )
        prompt += "\n" + quality_guidance

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

            # Remove any top-level heading (#) from the beginning of generated content
            # Despite instructions not to include one, GPT sometimes does
            lines = content.split("\n")
            start_idx = 0

            # Skip leading blank lines and attribution-like blocks
            while start_idx < len(lines):
                line = lines[start_idx].strip()
                # Skip blank lines, blockquotes (>), and top-level headings (#)
                if (
                    not line
                    or line.startswith(">")
                    or (line.startswith("#") and not line.startswith("##"))
                ):
                    start_idx += 1
                else:
                    break

            if start_idx > 0 and start_idx < len(lines):
                content = "\n".join(lines[start_idx:])

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
