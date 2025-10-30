"""Generate default social share image for the site.

Loads OPENAI_API_KEY from environment or from a local .env file if present.
"""

import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.images import generate_featured_image
from pathlib import Path
from typing import Optional

def load_env_from_dotenv() -> None:
    """Attempt to load environment variables from a .env file if available."""
    try:
        from dotenv import load_dotenv
    except Exception:
        return

    # Try project root .env
    project_root = Path(__file__).resolve().parents[1]
    env_path = project_root / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
from rich.console import Console

console = Console()


def main() -> None:
    """Generate a default social image for the site."""
    load_env_from_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        console.print("[red]Error:[/red] OPENAI_API_KEY not found in environment")
        console.print("Set it in your environment or create a .env file with:\nOPENAI_API_KEY=sk-...\n")
        sys.exit(1)

    console.print("[bold blue]Generating default social share image...[/bold blue]")
    console.print()

    title = "Tech Content Curator"
    summary = """A curated collection of quality tech articles from HackerNews, GitHub Trending, 
    Reddit, and Mastodon. Discover the latest in software development, open source, AI, 
    infrastructure, and developer tools. Daily updates with well-researched, insightful content."""

    result = generate_featured_image(
        title=title,
        summary=summary,
        slug="default-social",
        openai_api_key=api_key,
        base_url="",
    )

    if result:
        hero_path, icon_path = result
        console.print()
        console.print("[green]✓[/green] Successfully generated default social image!")
        console.print(f"  Hero: {hero_path}")
        console.print(f"  Icon: {icon_path}")
        console.print()
        console.print("[dim]Note: The hero image (default-social.png) will be used as the default OpenGraph/Twitter card image for pages without a specific image.[/dim]")
    else:
        console.print("[red]✗[/red] Failed to generate image")
        sys.exit(1)


if __name__ == "__main__":
    main()
