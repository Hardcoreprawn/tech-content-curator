"""General article generator for standard technical content."""

from rich.console import Console

from ..models import EnrichedItem
from ..pipeline.quality_feedback import get_quality_prompt_enhancements
from ..utils.logging import get_logger
from .base import BaseGenerator
from .prompt_templates import build_enhanced_prompt, detect_content_type

logger = get_logger(__name__)
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
        - Uses voice-specific personality if available

        Args:
            item: The enriched item with all context

        Returns:
            Tuple of (article content as markdown string, input tokens, output tokens)
        """
        if not self.client:
            raise ValueError("OpenAI client not initialized")

        # Detect content type and build specialized prompt
        content_type = detect_content_type(item)
        logger.debug(f"Detected content type: {content_type}")
        console.print(f"  Content type detected: {content_type}")

        # Build base prompt
        prompt = build_enhanced_prompt(item, content_type)

        # Add quality enhancements to guide generation
        # Note: difficulty_level is optional at enrichment stage,
        # will be set during categorization after generation
        difficulty_level = getattr(item, "difficulty_level", None) or "intermediate"
        quality_guidance = get_quality_prompt_enhancements(
            difficulty_level, content_type
        )
        prompt += "\n" + quality_guidance

        # Inject voice personality if voice_profile is specified
        # (set during orchestrator's voice selection)
        voice_id = getattr(item, "voice_profile", None)
        system_message = None
        temperature = 0.6  # Default temperature

        if voice_id and voice_id != "default":
            try:
                from .voices.prompts import build_voice_system_prompt

                # Get voice-specific system prompt
                system_message = build_voice_system_prompt(voice_id, content_type)
                logger.debug(f"Injected voice: {voice_id}")
                console.print(f"  [dim]Injected voice: {voice_id}[/dim]")
            except (ImportError, ValueError, KeyError) as e:
                logger.debug(f"Voice injection skipped: {type(e).__name__}: {e}")
                console.print(f"  [dim]Voice injection skipped: {e}[/dim]")

        try:
            # Build messages with voice-aware system prompt if available
            messages = []
            if system_message:
                messages.append({"role": "system", "content": system_message})
            messages.append({"role": "user", "content": prompt})

            logger.debug(
                f"Calling OpenAI API for article generation (temperature={temperature})"
            )
            # Get model from config
            from ..config import get_config

            config = get_config()

            response = self.client.chat.completions.create(
                model=config.content_model,
                messages=messages,
                temperature=temperature,  # Use voice-specific temperature if injected
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

            logger.info(
                f"Article generated successfully: {len(content.split())} words, tokens: {input_tokens}/{output_tokens}"
            )
            return content.strip(), input_tokens, output_tokens

        except Exception as e:
            logger.error(f"Article generation failed: {type(e).__name__}: {e}")
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
