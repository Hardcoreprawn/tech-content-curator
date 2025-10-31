"""GitHub trending repositories collector.

Collects trending repos from GitHub.
GitHub is TIER_3 source - shows what's hot in open source.
"""

from datetime import UTC, datetime

import httpx
from rich.console import Console

from ..models import CollectedItem, SourceType

console = Console()


def collect_from_github_trending(
    language: str | None = None, limit: int = 20
) -> list[CollectedItem]:
    """Collect trending repositories from GitHub.

    GitHub trending is S-tier: shows what's hot in open source.

    Args:
        language: Filter by programming language (None = all languages)
        limit: Maximum number of repos to collect

    Returns:
        List of collected items from GitHub Trending
    """
    console.print(
        f"[blue]Collecting from GitHub Trending{f' ({language})' if language else ''}...[/blue]"
    )

    items = []

    try:
        # GitHub trending doesn't have an official API, but we can use search
        with httpx.Client(timeout=30.0) as client:
            # Search for recently starred repos
            params = {
                "q": "stars:>100 pushed:>2025-10-01",  # Active repos with good engagement
                "sort": "stars",
                "order": "desc",
                "per_page": limit,
            }

            if language:
                params["q"] += f" language:{language}"

            response = client.get(
                "https://api.github.com/search/repositories",
                params=params,
                headers={"Accept": "application/vnd.github.v3+json"},
            )

            if response.status_code == 403:
                console.print("[yellow]⚠[/yellow] GitHub API rate limit hit, skipping")
                return []

            response.raise_for_status()
            data = response.json()

            repos = data.get("items", [])[:limit]
            console.print(f"  Found {len(repos)} trending repositories...")

            for repo in repos:
                try:
                    # Build content from repo description
                    content = (
                        f"{repo['name']}\n\n{repo.get('description', 'No description')}"
                    )

                    item = CollectedItem(
                        id=f"github_{repo['id']}",
                        title=f"{repo['full_name']}: {repo.get('description', '')[:100]}",
                        content=content,
                        source=SourceType.GITHUB,
                        url=repo["html_url"],
                        author=repo["owner"]["login"],
                        collected_at=datetime.now(UTC),
                        metadata={
                            "stars": repo["stargazers_count"],
                            "forks": repo["forks_count"],
                            "watchers": repo["watchers_count"],
                            "language": repo.get("language"),
                            "topics": repo.get("topics", []),
                            "source_name": "github_trending",
                            "open_issues": repo.get("open_issues_count", 0),
                        },
                    )
                    items.append(item)

                except Exception as e:
                    console.print(
                        f"[yellow]⚠[/yellow] Failed to process GitHub repo: {e}"
                    )
                    continue

    except Exception as e:
        console.print(f"[red]✗[/red] GitHub trending collection failed: {e}")
        return []

    console.print(f"[green]✓[/green] Collected {len(items)} trending repos from GitHub")
    return items
