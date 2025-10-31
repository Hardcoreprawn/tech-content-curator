#!/usr/bin/env python3
"""
Setup check: imports, config, and basic Mastodon collection.
"""

from rich.console import Console

from src.config import get_config
from src.collectors import collect_from_mastodon

console = Console()


def check_imports() -> bool:
    """Test that key imports work."""
    console.print("[blue]Testing imports...[/blue]")
    try:
        import importlib.util

        assert importlib.util.find_spec("src.collect") is not None
        assert importlib.util.find_spec("src.models") is not None
        console.print("[green]✓[/green] All imports successful")
        return True
    except Exception as e:  # noqa: BLE001 - show any error clearly to user
        console.print(f"[red]✗[/red] Import failed: {e}")
        return False


def check_config() -> bool:
    """Test configuration loading."""
    console.print("[blue]Testing configuration...[/blue]")
    try:
        import os

        os.environ.setdefault("OPENAI_API_KEY", "test-key-for-validation")
        config = get_config()
        instance = (config.mastodon_instances[0] if config.mastodon_instances else "<none>")
        console.print(f"[green]✓[/green] Config loaded: mastodon instance {instance}")
        return True
    except Exception as e:  # noqa: BLE001 - show any error clearly to user
        console.print(f"[red]✗[/red] Config failed: {e}")
        return False


def check_mastodon_connection() -> bool:
    """Test basic Mastodon connection (no auth needed for public timeline)."""
    console.print("[blue]Testing Mastodon connection...[/blue]")
    try:
        import os

        os.environ.setdefault("OPENAI_API_KEY", "test-key")
        config = get_config()
        items = collect_from_mastodon(config, limit=2)
        if items:
            console.print(f"[green]✓[/green] Successfully collected {len(items)} items")
            console.print(f"[dim]Sample item: {items[0].title[:50]}...[/dim]")
            return True
        console.print("[yellow]⚠[/yellow] No items collected (may be normal)")
        return True
    except Exception as e:  # noqa: BLE001
        console.print(f"[red]✗[/red] Mastodon connection failed: {e}")
        return False


if __name__ == "__main__":
    console.print("[bold]Content Curator - Setup Check[/bold]\n")
    tests = [
        ("Imports", check_imports),
        ("Configuration", check_config),
        ("Mastodon Connection", check_mastodon_connection),
    ]

    results: list[tuple[str, bool]] = []
    for name, test_func in tests:
        console.print(f"\n[bold]{name}[/bold]")
        success = test_func()
        results.append((name, success))

    console.print("\n[bold]Test Results:[/bold]")
    for name, success in results:
        status = "[green]PASS[/green]" if success else "[red]FAIL[/red]"
        console.print(f"  {name}: {status}")

    if all(success for _, success in results):
        console.print("\n[bold green]🎉 All checks passed![/bold green]")
    else:
        console.print("\n[bold red]❌ Some checks failed. See errors above.[/bold red]")
