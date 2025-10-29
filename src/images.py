"""Featured image generation for articles using OpenAI DALL-E 3.

Simple workflow:
1. Generate a 1024x1024 square image (cheaper at $0.020)
2. Download and process locally with Pillow
3. Create wide hero (1792x1024) by resizing
4. Create icon (512x512 center crop)
5. Return paths for both hero and icon
"""

from io import BytesIO
from pathlib import Path

import httpx
from openai import OpenAI
from PIL import Image
from rich.console import Console

from .config import get_project_root

console = Console()


def get_images_dir() -> Path:
    """Get the static images directory, creating it if needed."""
    images_dir = get_project_root() / "site" / "static" / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    return images_dir


def generate_featured_image(
    title: str, summary: str, slug: str, api_key: str
) -> tuple[str, str] | None:
    """Generate a featured image and icon for an article using DALL-E 3.

    Args:
        title: Article title
        summary: Brief article summary
        slug: URL-friendly slug for filename
        api_key: OpenAI API key

    Returns:
        Tuple of (hero_path, icon_path) like ("/images/slug.png", "/images/slug-icon.png")
        or None if generation fails
    """
    try:
        client = OpenAI(api_key=api_key)

        # Create a concise prompt for DALL-E 3
        # Focus on abstract, professional tech imagery
        prompt = f"""Create a modern, abstract hero image for a tech blog article titled "{title}".

Style: Clean, professional, minimalist with a tech aesthetic. Use gradients, geometric shapes, 
or abstract representations. Avoid literal interpretations, text, or specific brands.

Theme: {summary[:200]}

The image should work well as a blog header - wide format, visually appealing, not too busy."""

        console.print("[blue]Generating featured image...[/blue]")

        response = client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            size="1024x1024",  # Square format - we'll crop to wide locally
            quality="standard",  # Standard is fine for blog images ($0.020 vs $0.040)
            n=1,
        )

        if not response.data:
            console.print("[yellow]⚠[/yellow] No image data returned")
            return None
        
        image_url = response.data[0].url
        if not image_url:
            console.print("[yellow]⚠[/yellow] No image URL returned")
            return None

        # Download the image
        console.print(f"[blue]Downloading image from OpenAI...[/blue]")
        with httpx.Client(timeout=30.0) as http_client:
            img_response = http_client.get(image_url)
            img_response.raise_for_status()

        # Process the square image into hero (wide) and icon formats
        images_dir = get_images_dir()
        
        # Open the downloaded square image
        with Image.open(BytesIO(img_response.content)) as img:
            # Create wide hero image (1792x1024) by resizing from square
            width, height = img.size  # Should be 1024x1024
            
            # Hero: Resize to wide format (1792x1024)
            hero = img.resize((1792, 1024), Image.Resampling.LANCZOS)
            
            hero_filename = f"{slug}.png"
            hero_filepath = images_dir / hero_filename
            hero.save(hero_filepath, "PNG")
            console.print(f"[green]✓[/green] Created hero image at {hero_filename}")
            
            # Icon: 512x512 center crop from original square
            crop_size = min(width, height)
            left = (width - crop_size) // 2
            top = (height - crop_size) // 2
            right = left + crop_size
            bottom = top + crop_size
            
            icon = img.crop((left, top, right, bottom))
            icon = icon.resize((512, 512), Image.Resampling.LANCZOS)
            
            icon_filename = f"{slug}-icon.png"
            icon_filepath = images_dir / icon_filename
            icon.save(icon_filepath, "PNG")
            console.print(f"[green]✓[/green] Created icon at {icon_filename}")

        # Return relative paths for Hugo
        return (f"/images/{hero_filename}", f"/images/{icon_filename}")

    except Exception as e:
        console.print(f"[yellow]⚠[/yellow] Image generation failed: {e}")
        console.print("[yellow]Continuing without featured image[/yellow]")
        return None
