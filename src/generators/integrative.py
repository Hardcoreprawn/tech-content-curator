"""Integrative guide generator for curated lists and listicles."""

import re

from rich.console import Console

from ..models import EnrichedItem
from .base import BaseGenerator

console = Console()


class IntegrativeListGenerator(BaseGenerator):
    """Generator for transforming curated lists into integrative guides."""

    @property
    def name(self) -> str:
        return "Integrative List Generator"

    @property
    def priority(self) -> int:
        return 50  # Higher priority than general, check before fallback

    def can_handle(self, item: EnrichedItem) -> bool:
        """Detect if the source content is a curated list/listicle.

        Signals: 'awesome' repos, 'list of', 'top N', heavy bulleting/numbering.
        """
        title = item.original.title.lower()
        content = item.original.content
        content_lower = content.lower()

        awesome_indicators = [
            "awesome ",
            "awesome-",
            "awesome\n",
            "free-programming-books",
            "awesome-selfhosted",
            "build-your-own-x",
            "build your own",
            "developer-roadmap",
            "list of",
            "top ",
            "curated list",
        ]
        if any(ind in title or ind in content_lower for ind in awesome_indicators):
            return True

        # Bullet/numbered list density
        lines = content.splitlines()
        bullet_lines = sum(1 for ln in lines if re.match(r"^\s*([-*]|\d+\.)\s+", ln))
        return bullet_lines >= 5

    def generate_content(self, item: EnrichedItem) -> tuple[str, int, int]:
        """Transform a curated list into an integrative, comparative guide.

        Focus on why the category matters, how items fit together, and concrete stacks.

        Args:
            item: The enriched item with list-style content

        Returns:
            Tuple of (article content as markdown string, input tokens, output tokens)
        """
        if not self.client:
            raise ValueError("OpenAI client not initialized")

        prompt = f"""
    You're writing an in-depth integrative guide based on a curated list-style source. Do NOT just reproduce a list.

    CONTEXT FROM SOURCE:
    TITLE: {item.original.title}
    CONTENT (excerpt): {item.original.content[:800]}
    SOURCE URL: {item.original.url}
    TOPICS: {", ".join(item.topics)}

    WRITE A COMPREHENSIVE GUIDE THAT:
    - Opens with why this problem space matters and the value these tools provide
    - Includes a short "Key Takeaways" bullet list (3–5 bullets) after the introduction
    - Groups tools into a clear taxonomy (3-5 categories) with substantial explanation for each
    - For each category, pick 2-4 representative tools and explain:
      * What problem they solve specifically
      * Key features and trade-offs
      * When to choose one over another
      * Include direct links to official project sites/repos (e.g., https://github.com/project/name)
    - Proposes 2-3 concrete example stacks for common use-cases with detailed rationale
    - Describes integration points and data flow between components
    - Lists practical evaluation criteria to help readers choose
    - Includes an ASCII diagram showing architecture and component relationships
    - Offers a realistic 'getting started' section with configuration examples (Docker Compose snippets, etc.)
    - IMPORTANT: Close with proper attribution - "Inspired by [awesome-selfhosted](source_url)" or similar

        DEPTH REQUIREMENTS:
    - 1200-1500 words minimum - provide real substance and context
    - Each tool mention should include 2-3 sentences of explanation minimum
    - Include practical examples and real-world usage patterns
        - Explain non-mainstream terms and acronyms inline the first time; add brief background callouts when optional using blockquotes in the form:
            > Background: one-sentence explanation
    - Use markdown links for all tool names pointing to their official sites
    - Structure with clear ## and ### headings for readability

    ATTRIBUTION:
    - End with a dedicated "## Further Resources" section
    - Credit the original curator/author: "This guide was inspired by [{item.original.title}]({item.original.url}) curated by @{item.original.author}"
    - Encourage readers to check the original list for comprehensive options

    FORMAT:
    - Full markdown with proper ## headings
    - Include an "Integration Architecture" section with ASCII diagram
        - Include "Example Stacks" section with 2-3 detailed use-cases
    - Include "Getting Started" with practical configuration snippets
    """

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.5,
                max_tokens=2500,  # Allow for longer, more detailed content
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
            console.print(
                f"[yellow]⚠[/yellow] Integrative list article generation failed: {e}"
            )
            fallback = """
## Understanding the Landscape

This guide summarizes a category of tools and how they fit together into practical stacks. Instead of listing every option, it explains the roles, trade-offs, and integration points that matter.

### Use-case Stacks (Examples)
- Starter: Tool A + Tool B (simple, easy to maintain)
- Pro: Tool C + Tool D + Tool E (more features, more moving parts)

### Integration Map (ASCII)
Internet -> Edge/Proxy -> Core Service -> Storage/DB
                     -> Auth -> Monitoring
"""
            return fallback, 0, 0
