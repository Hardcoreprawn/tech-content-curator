"""Build or refresh the abstract image library."""

from rich.console import Console

from src.images.library import build_gradient_library_if_empty

console = Console()


def main() -> None:
    paths = build_gradient_library_if_empty()
    console.print(f"[green]✓[/green] Library ready with {len(paths)} images")
    for p in paths:
        console.print(f"  • {p.name}")


if __name__ == "__main__":
    main()
