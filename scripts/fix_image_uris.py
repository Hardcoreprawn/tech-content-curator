#!/usr/bin/env python3
"""Fix broken image URIs in old markdown files.

This script updates image paths from relative /images/... to full base URLs.
It handles both cover.image and images array fields in frontmatter.

Usage:
    uv run python -m scripts.fix_image_uris
"""

import re
from pathlib import Path

import frontmatter
from rich.console import Console

console = Console()

# Hugo base URL from configuration
HUGO_BASE_URL = "https://hardcoreprawn.github.io/tech-content-curator"


def fix_image_path(image_path: str) -> str:
    """Convert relative image path to full URL.
    
    Args:
        image_path: Image path like '/images/filename.png' or already a full URL
        
    Returns:
        Full image URL
    """
    if not image_path:
        return image_path
    
    # If already a full URL, return as-is
    if image_path.startswith("http://") or image_path.startswith("https://"):
        return image_path
    
    # If relative path starting with /, convert to full URL
    if image_path.startswith("/"):
        return f"{HUGO_BASE_URL}{image_path}"
    
    # Otherwise return as-is (might be a relative path without leading /)
    return image_path


def fix_markdown_file(filepath: Path) -> bool:
    """Fix image URIs in a single markdown file.
    
    Args:
        filepath: Path to the markdown file
        
    Returns:
        True if file was modified, False otherwise
    """
    try:
        # Parse the markdown file
        with open(filepath, "r", encoding="utf-8") as f:
            post = frontmatter.load(f)
        
        modified = False
        
        # Fix cover.image
        if "cover" in post.metadata and isinstance(post.metadata["cover"], dict):
            if "image" in post.metadata["cover"]:
                old_image = post.metadata["cover"]["image"]
                new_image = fix_image_path(old_image)
                if old_image != new_image:
                    post.metadata["cover"]["image"] = new_image
                    modified = True
        
        # Fix images array
        if "images" in post.metadata and isinstance(post.metadata["images"], list):
            new_images = []
            for img in post.metadata["images"]:
                new_img = fix_image_path(img)
                if img != new_img:
                    modified = True
                new_images.append(new_img)
            if modified:
                post.metadata["images"] = new_images
        
        # Fix icon field
        if "icon" in post.metadata:
            old_icon = post.metadata["icon"]
            new_icon = fix_image_path(old_icon)
            if old_icon != new_icon:
                post.metadata["icon"] = new_icon
                modified = True
        
        # Save if modified
        if modified:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(frontmatter.dumps(post))
            return True
        
        return False
        
    except Exception as e:
        console.print(f"[red]Error processing {filepath}: {e}[/red]")
        return False


def main():
    """Fix all markdown files in content/posts/."""
    project_root = Path(__file__).parent.parent
    posts_dir = project_root / "content" / "posts"
    
    if not posts_dir.exists():
        console.print(f"[red]Posts directory not found: {posts_dir}[/red]")
        return
    
    # Find all markdown files
    md_files = sorted(posts_dir.glob("*.md"))
    
    if not md_files:
        console.print(f"[yellow]No markdown files found in {posts_dir}[/yellow]")
        return
    
    console.print(f"[bold blue]Scanning {len(md_files)} markdown files...[/bold blue]")
    
    modified_count = 0
    for filepath in md_files:
        if fix_markdown_file(filepath):
            console.print(f"[green]✓[/green] Fixed {filepath.name}")
            modified_count += 1
        else:
            console.print(f"[dim]  {filepath.name}[/dim]")
    
    console.print(f"\n[bold green]Done![/bold green] Modified {modified_count}/{len(md_files)} files.")


if __name__ == "__main__":
    main()
