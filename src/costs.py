"""
Cost tracking for article generation and duplicate waste.

Tracks:
1. Successful article generation costs
2. Wasted generation costs (duplicates detected post-generation)
3. Savings from pre-generation duplicate detection
4. Historical cost data for analysis

See: docs/ADR-004-ADAPTIVE-DEDUPLICATION.md
"""

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from rich.console import Console
from rich.table import Table

console = Console()


@dataclass
class GenerationCostEntry:
    """Single article generation cost record."""

    timestamp: str
    article_title: str
    article_filename: str
    content_cost: float
    title_cost: float
    slug_cost: float
    image_cost: float
    total_cost: float
    status: Literal["saved", "rejected_duplicate", "rejected_pre_gen"]
    duplicate_of: str | None = None  # Filename of article it duplicated


@dataclass
class CostSummary:
    """Summary of generation costs."""

    total_spent: float
    successful_articles: int
    successful_cost: float
    wasted_duplicates: int
    wasted_cost: float
    pre_gen_rejections: int
    estimated_savings: float  # How much we saved by catching pre-gen
    efficiency_rate: float  # Percentage of cost that produced useful articles


class CostTracker:
    """
    Track costs of article generation including waste from duplicates.

    This helps:
    1. Understand true cost per article
    2. Quantify waste from duplicate generation
    3. Measure effectiveness of pre-generation filtering
    4. Justify improvements to dedup systems
    """

    def __init__(self, data_file: Path = Path("data/generation_costs.json")):
        """
        Initialize cost tracker.

        Args:
            data_file: Path to cost tracking JSON file
        """
        self.data_file = data_file
        self.data_file.parent.mkdir(parents=True, exist_ok=True)
        self.entries: list[GenerationCostEntry] = []
        self.load()

    def load(self):
        """Load historical cost data."""
        if self.data_file.exists():
            try:
                with open(self.data_file, encoding="utf-8") as f:
                    data = json.load(f)
                    self.entries = [GenerationCostEntry(**entry) for entry in data]
            except Exception as e:
                console.print(
                    f"[yellow]Warning: Could not load cost data: {e}[/yellow]"
                )
                self.entries = []

    def save(self):
        """Save cost data to file."""
        try:
            with open(self.data_file, "w", encoding="utf-8") as f:
                json.dump(
                    [asdict(entry) for entry in self.entries],
                    f,
                    indent=2,
                    default=str,
                )
        except Exception as e:
            console.print(f"[red]Error saving cost data: {e}[/red]")

    def record_successful_generation(
        self,
        article_title: str,
        article_filename: str,
        generation_costs: dict[str, float],
    ):
        """
        Record costs for a successfully saved article.

        Args:
            article_title: Title of generated article
            article_filename: Filename of saved article
            generation_costs: Dict with content_generation, title_generation, etc.
        """
        entry = GenerationCostEntry(
            timestamp=datetime.now(UTC).isoformat(),
            article_title=article_title,
            article_filename=article_filename,
            content_cost=generation_costs.get("content_generation", 0.0),
            title_cost=generation_costs.get("title_generation", 0.0),
            slug_cost=generation_costs.get("slug_generation", 0.0),
            image_cost=generation_costs.get("image_generation", 0.0)
            + generation_costs.get("icon_generation", 0.0),
            total_cost=sum(generation_costs.values()),
            status="saved",
        )
        self.entries.append(entry)
        self.save()

    def record_rejected_duplicate(
        self,
        article_title: str,
        generation_costs: dict[str, float],
        duplicate_of: str | None = None,
    ):
        """
        Record costs for an article rejected as duplicate AFTER generation.

        This is wasted cost that could have been avoided with better pre-filtering.

        Args:
            article_title: Title of rejected article
            generation_costs: Costs already spent
            duplicate_of: Filename of article it duplicated
        """
        entry = GenerationCostEntry(
            timestamp=datetime.now(UTC).isoformat(),
            article_title=article_title,
            article_filename="",  # Not saved
            content_cost=generation_costs.get("content_generation", 0.0),
            title_cost=generation_costs.get("title_generation", 0.0),
            slug_cost=generation_costs.get("slug_generation", 0.0),
            image_cost=generation_costs.get("image_generation", 0.0)
            + generation_costs.get("icon_generation", 0.0),
            total_cost=sum(generation_costs.values()),
            status="rejected_duplicate",
            duplicate_of=duplicate_of,
        )
        self.entries.append(entry)
        self.save()

        console.print(
            f"[red]💸 Wasted ${entry.total_cost:.4f} on duplicate article[/red]"
        )

    def record_pre_gen_rejection(
        self, article_title: str, estimated_cost: float = 0.002
    ):
        """
        Record that we rejected a candidate BEFORE generation (saved cost).

        Args:
            article_title: Title that would have been generated
            estimated_cost: Estimated cost we saved (default: $0.002 avg)
        """
        entry = GenerationCostEntry(
            timestamp=datetime.now(UTC).isoformat(),
            article_title=article_title,
            article_filename="",
            content_cost=estimated_cost,
            title_cost=0.0,
            slug_cost=0.0,
            image_cost=0.0,
            total_cost=estimated_cost,
            status="rejected_pre_gen",
        )
        self.entries.append(entry)
        self.save()

    def get_summary(self, days: int = 30) -> CostSummary:
        """
        Get cost summary for the last N days.

        Args:
            days: Number of days to include (default: 30)

        Returns:
            CostSummary with statistics
        """
        from datetime import timedelta

        cutoff = datetime.now(UTC) - timedelta(days=days)
        recent = [
            e
            for e in self.entries
            if datetime.fromisoformat(e.timestamp.replace("Z", "+00:00")) >= cutoff
        ]

        saved = [e for e in recent if e.status == "saved"]
        rejected_post = [e for e in recent if e.status == "rejected_duplicate"]
        rejected_pre = [e for e in recent if e.status == "rejected_pre_gen"]

        successful_cost = sum(e.total_cost for e in saved)
        wasted_cost = sum(e.total_cost for e in rejected_post)
        estimated_savings = sum(e.total_cost for e in rejected_pre)
        total_spent = successful_cost + wasted_cost

        efficiency = (successful_cost / total_spent * 100) if total_spent > 0 else 100.0

        return CostSummary(
            total_spent=total_spent,
            successful_articles=len(saved),
            successful_cost=successful_cost,
            wasted_duplicates=len(rejected_post),
            wasted_cost=wasted_cost,
            pre_gen_rejections=len(rejected_pre),
            estimated_savings=estimated_savings,
            efficiency_rate=efficiency,
        )

    def print_summary(self, days: int = 30):
        """Print a formatted cost summary."""
        summary = self.get_summary(days)

        console.print(
            f"\n[bold cyan]💰 Generation Cost Summary (Last {days} Days)[/bold cyan]\n"
        )

        table = Table(show_header=True, header_style="bold")
        table.add_column("Metric")
        table.add_column("Count", justify="right")
        table.add_column("Cost (USD)", justify="right")

        table.add_row(
            "[green]Successful Articles[/green]",
            str(summary.successful_articles),
            f"${summary.successful_cost:.4f}",
        )
        table.add_row(
            "[red]Wasted on Duplicates[/red]",
            str(summary.wasted_duplicates),
            f"${summary.wasted_cost:.4f}",
        )
        table.add_row(
            "[yellow]Pre-Gen Rejections[/yellow]",
            str(summary.pre_gen_rejections),
            f"${summary.estimated_savings:.4f} saved",
        )
        table.add_row(
            "[bold]Total Spent[/bold]",
            str(summary.successful_articles + summary.wasted_duplicates),
            f"[bold]${summary.total_spent:.4f}[/bold]",
        )

        console.print(table)

        # Efficiency metrics
        console.print(f"\n[bold]Efficiency Rate:[/bold] {summary.efficiency_rate:.1f}%")

        if summary.wasted_cost > 0:
            waste_pct = summary.wasted_cost / summary.total_spent * 100
            console.print(
                f"[red]⚠ Waste:[/red] ${summary.wasted_cost:.4f} ({waste_pct:.1f}% of total)"
            )

        if summary.estimated_savings > 0:
            console.print(
                f"[green]✓ Savings from pre-gen filtering:[/green] ${summary.estimated_savings:.4f}"
            )

    def get_waste_patterns(self) -> list[tuple[str, int, float]]:
        """
        Analyze what types of articles are being wasted.

        Returns:
            List of (duplicate_of, count, total_waste) tuples
        """
        from collections import defaultdict

        waste_by_source = defaultdict(lambda: {"count": 0, "cost": 0.0})

        for entry in self.entries:
            if entry.status == "rejected_duplicate" and entry.duplicate_of:
                waste_by_source[entry.duplicate_of]["count"] += 1
                waste_by_source[entry.duplicate_of]["cost"] += entry.total_cost

        # Sort by total cost (highest waste first)
        patterns = [
            (source, data["count"], data["cost"])
            for source, data in waste_by_source.items()
        ]
        patterns.sort(key=lambda x: x[2], reverse=True)

        return patterns
